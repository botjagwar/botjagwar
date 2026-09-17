"""HMAC authentication for executable HTTP-to-RabbitMQ publications."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any

RABBITMQ_GATEWAY_HMAC_HEADER = "X-Botjagwar-Gateway-HMAC"
RABBITMQ_GATEWAY_TIMESTAMP_HEADER = "X-Botjagwar-Gateway-Timestamp"
RABBITMQ_GATEWAY_NONCE_HEADER = "X-Botjagwar-Gateway-Nonce"
RABBITMQ_GATEWAY_MAX_AGE_SECONDS = 300
RABBITMQ_GATEWAY_FUTURE_SKEW_SECONDS = 30
_GATEWAY_HMAC_DOMAIN = b"botjagwar-rabbitmq-gateway-v2\0"
_QUEUE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,255}$")
_NONCE_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class RabbitMqGatewayAuthError(ValueError):
    """Raised when an executable gateway publication is not authenticated."""


def rabbitmq_gateway_hmac(
    message: Any,
    secret: str | None,
    *,
    expected_queue: str,
    issued_at: int,
    nonce: str,
) -> str:
    """Return a queue-, time-, and nonce-bound HMAC for one JSON message."""
    if not _QUEUE_NAME_PATTERN.fullmatch(expected_queue):
        raise RabbitMqGatewayAuthError("Gateway queue name is invalid.")
    if isinstance(issued_at, bool) or not isinstance(issued_at, int) or issued_at < 0:
        raise RabbitMqGatewayAuthError("Gateway request timestamp is invalid.")
    if not isinstance(nonce, str) or not _NONCE_PATTERN.fullmatch(nonce):
        raise RabbitMqGatewayAuthError("Gateway request nonce is invalid.")
    secret_bytes = _validate_secret(secret)
    try:
        canonical = json.dumps(
            message,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (RecursionError, TypeError, ValueError) as exc:
        raise RabbitMqGatewayAuthError(
            "Gateway message is not canonical JSON."
        ) from exc
    authenticated = (
        _GATEWAY_HMAC_DOMAIN
        + expected_queue.encode("ascii")
        + b"\0"
        + str(issued_at).encode("ascii")
        + b"\0"
        + nonce.encode("ascii")
        + b"\0"
        + canonical
    )
    return hmac.new(secret_bytes, authenticated, hashlib.sha256).hexdigest()


def rabbitmq_gateway_auth_headers(
    message: Any,
    secret: str | None,
    *,
    expected_queue: str,
    issued_at: int | None = None,
    nonce: str | None = None,
) -> dict[str, str]:
    """Create fresh authentication headers for one gateway request."""
    request_timestamp = int(time.time()) if issued_at is None else issued_at
    request_nonce = secrets.token_hex(32) if nonce is None else nonce
    signature = rabbitmq_gateway_hmac(
        message,
        secret,
        expected_queue=expected_queue,
        issued_at=request_timestamp,
        nonce=request_nonce,
    )
    return {
        RABBITMQ_GATEWAY_HMAC_HEADER: signature,
        RABBITMQ_GATEWAY_TIMESTAMP_HEADER: str(request_timestamp),
        RABBITMQ_GATEWAY_NONCE_HEADER: request_nonce,
    }


def verify_rabbitmq_gateway_hmac(
    message: Any,
    signature: Any,
    secret: str | None,
    *,
    expected_queue: str,
    issued_at: Any,
    nonce: Any,
    now: float | None = None,
) -> tuple[str, float]:
    """Verify a fresh gateway request and return its nonce and expiry time."""
    if not isinstance(signature, str) or not re.fullmatch(r"[0-9a-f]{64}", signature):
        raise RabbitMqGatewayAuthError("Gateway authentication is invalid.")
    if (
        not isinstance(issued_at, str)
        or len(issued_at) > 12
        or not re.fullmatch(r"0|[1-9][0-9]*", issued_at)
    ):
        raise RabbitMqGatewayAuthError("Gateway authentication is invalid.")
    if not isinstance(nonce, str) or not _NONCE_PATTERN.fullmatch(nonce):
        raise RabbitMqGatewayAuthError("Gateway authentication is invalid.")
    timestamp = int(issued_at)
    current_time = time.time() if now is None else now
    if (
        timestamp < current_time - RABBITMQ_GATEWAY_MAX_AGE_SECONDS
        or timestamp > current_time + RABBITMQ_GATEWAY_FUTURE_SKEW_SECONDS
    ):
        raise RabbitMqGatewayAuthError("Gateway authentication is invalid.")
    expected = rabbitmq_gateway_hmac(
        message,
        secret,
        expected_queue=expected_queue,
        issued_at=timestamp,
        nonce=nonce,
    )
    if not hmac.compare_digest(signature, expected):
        raise RabbitMqGatewayAuthError("Gateway authentication is invalid.")
    return nonce, timestamp + RABBITMQ_GATEWAY_MAX_AGE_SECONDS


class SqliteRabbitMqGatewayReplayStore:
    """Durably reject reuse of a fresh gateway request nonce."""

    def __init__(self, path: str | Path) -> None:
        """Initialize a replay store at a persistent path."""
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS rabbitmq_gateway_requests (
                    nonce TEXT PRIMARY KEY,
                    expires_at REAL NOT NULL
                )
                """
            )

    def claim(self, nonce: str, expires_at: float, *, now: float | None = None) -> bool:
        """Persist an unseen nonce atomically, returning false for a replay."""
        current_time = time.time() if now is None else now
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "DELETE FROM rabbitmq_gateway_requests WHERE expires_at < ?",
                (current_time,),
            )
            inserted = connection.execute(
                """
                INSERT OR IGNORE INTO rabbitmq_gateway_requests (nonce, expires_at)
                VALUES (?, ?)
                """,
                (nonce, expires_at),
            )
        return inserted.rowcount == 1

    def _connect(self) -> sqlite3.Connection:
        """Open one bounded SQLite connection for a replay-store operation."""
        return sqlite3.connect(self._path, timeout=10)


def _validate_secret(secret: str | None) -> bytes:
    """Return a sufficiently strong configured gateway secret."""
    if not isinstance(secret, str) or len(secret.encode("utf-8")) < 32:
        raise RabbitMqGatewayAuthError("Gateway authentication is not configured.")
    return secret.encode("utf-8")
