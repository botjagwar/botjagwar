"""HTTP gateway that publishes validated messages with RabbitMQ confirms."""

import configparser
import json
import logging
import os
import re
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, Tuple

import pika
from flask import Flask, request

from api.config import BotjagwarConfig
from api.services.rabbitmq_gateway_auth import (
    RABBITMQ_GATEWAY_HMAC_HEADER,
    RABBITMQ_GATEWAY_NONCE_HEADER,
    RABBITMQ_GATEWAY_TIMESTAMP_HEADER,
    RabbitMqGatewayAuthError,
    SqliteRabbitMqGatewayReplayStore,
    verify_rabbitmq_gateway_hmac,
)

LOGGER = logging.getLogger(__name__)
PORT = 8443
MAX_GATEWAY_BODY_BYTES = 16 * 1024 * 1024
TEST_MODE = os.environ.get("TEST") == "1"
config = BotjagwarConfig()
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_GATEWAY_BODY_BYTES


# RabbitMQ connection parameters
RABBITMQ_HOST = config.get("host", "rabbitmq")
RABBITMQ_USERNAME = config.get("username", "rabbitmq")
RABBITMQ_PASSWORD = config.get("password", "rabbitmq")
RABBITMQ_VIRTUAL_HOST = config.get("virtual_host", "rabbitmq")


def _optional_config(key: str, section: str, default: str) -> str:
    """Read optional configuration without weakening strict queue validation."""
    try:
        value = config.get(key, section)
    except (configparser.Error, KeyError, ValueError):
        return default
    return value.strip() or default


PAGE_CHECK_REVIEW_QUEUE = os.environ.get(
    "BOTJAGWAR_PAGE_CHECK_REVIEW_QUEUE"
) or _optional_config("page_check_review_queue", "rabbitmq", "page-check-review")
RABBITMQ_GATEWAY_HMAC_SECRET = os.environ.get(
    "BOTJAGWAR_RABBITMQ_GATEWAY_HMAC_SECRET"
) or _optional_config("gateway_hmac_secret", "rabbitmq", "")
GATEWAY_REPLAY_LEDGER_PATH = os.environ.get(
    "BOTJAGWAR_RABBITMQ_GATEWAY_REPLAY_LEDGER"
) or _optional_config(
    "gateway_replay_ledger",
    "rabbitmq",
    (
        "user_data/rabbitmq-gateway-replays.sqlite3"
        if TEST_MODE
        else "/var/lib/botjagwar/user_data/rabbitmq-gateway-replays.sqlite3"
    ),
)
_GATEWAY_REPLAY_STORE_LOCK = threading.Lock()
_GATEWAY_REPLAY_STORE: SqliteRabbitMqGatewayReplayStore | None = None


def _validate_gateway_configuration() -> None:
    """Reject invalid replay storage before any executable route is served."""
    if not TEST_MODE and not Path(GATEWAY_REPLAY_LEDGER_PATH).expanduser().is_absolute():
        raise RuntimeError("Gateway replay ledger path must be absolute in production.")


_validate_gateway_configuration()

#
MANDATORY_FIELDS = {
    "default": ["language", "site", "page", "content", "summary", "minor"],
    "edit": [
        "site",
        "title",
        "user",
    ],
}
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
QUEUE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,255}$")


def make_channel() -> Tuple[Any, Any]:
    """Open one RabbitMQ connection and channel."""
    credentials = pika.PlainCredentials(RABBITMQ_USERNAME, RABBITMQ_PASSWORD)
    parameters = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        virtual_host=RABBITMQ_VIRTUAL_HOST,
        credentials=credentials,
        heartbeat=60,
        blocked_connection_timeout=20,
    )
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    return connection, channel


def _get_gateway_replay_store() -> SqliteRabbitMqGatewayReplayStore:
    """Return the process-local handle for the durable gateway replay store."""
    global _GATEWAY_REPLAY_STORE  # pylint: disable=global-statement
    if _GATEWAY_REPLAY_STORE is None:
        with _GATEWAY_REPLAY_STORE_LOCK:
            if _GATEWAY_REPLAY_STORE is None:
                _GATEWAY_REPLAY_STORE = SqliteRabbitMqGatewayReplayStore(
                    Path(GATEWAY_REPLAY_LEDGER_PATH).expanduser()
                )
    return _GATEWAY_REPLAY_STORE


def push(
    queue_name: str,
    message: str,
) -> None:
    """Publish one persistent message only after broker confirmation."""
    connection, channel = make_channel()
    try:
        channel.queue_declare(queue=queue_name, durable=True)
        channel.confirm_delivery()
        channel.basic_publish(
            exchange="",
            routing_key=queue_name,
            body=message,
            mandatory=True,
            properties=pika.BasicProperties(
                content_type="application/json",
                delivery_mode=2,
            ),
        )
    finally:
        if connection.is_open:
            try:
                connection.close()
            except Exception:  # pylint: disable=broad-exception-caught
                LOGGER.warning("RabbitMQ connection cleanup failed.", exc_info=True)


@app.route("/<user>", methods=["POST"])
def send(user: str) -> tuple[Dict[str, str], int]:
    """Validate and confirm one HTTP-to-RabbitMQ publication."""
    if not QUEUE_NAME_PATTERN.fullmatch(user):
        return {"error": "Queue name is invalid."}, 400
    if user == PAGE_CHECK_REVIEW_QUEUE:
        return {"error": "Executable edits cannot target the review inbox."}, 400
    if (
        request.content_length is not None
        and request.content_length > app.config["MAX_CONTENT_LENGTH"]
    ):
        return {"error": "Request body is too large."}, 413
    if not request.is_json:
        return {"error": "Request body must be a JSON object."}, 400
    try:
        encoded_data = request.environ["wsgi.input"].read(
            app.config["MAX_CONTENT_LENGTH"] + 1
        )
        if len(encoded_data) > app.config["MAX_CONTENT_LENGTH"]:
            return {"error": "Request body is too large."}, 413
        data = json.loads(encoded_data)
    except (OSError, RecursionError, UnicodeDecodeError, json.JSONDecodeError):
        return {"error": "Request body must be a JSON object."}, 400
    if not isinstance(data, dict):
        return {"error": "Request body must be a JSON object."}, 400
    if not RABBITMQ_GATEWAY_HMAC_SECRET:
        return {"error": "Gateway authentication is not configured."}, 503
    try:
        gateway_nonce, gateway_expires_at = verify_rabbitmq_gateway_hmac(
            data,
            request.headers.get(RABBITMQ_GATEWAY_HMAC_HEADER),
            RABBITMQ_GATEWAY_HMAC_SECRET,
            expected_queue=user,
            issued_at=request.headers.get(RABBITMQ_GATEWAY_TIMESTAMP_HEADER),
            nonce=request.headers.get(RABBITMQ_GATEWAY_NONCE_HEADER),
        )
    except RabbitMqGatewayAuthError:
        return {"error": "Gateway authentication is invalid."}, 401
    mandatory_fields = (
        MANDATORY_FIELDS[user]
        if user in MANDATORY_FIELDS
        else MANDATORY_FIELDS["default"]
    )

    for mandatory_field in mandatory_fields:
        if mandatory_field not in data:
            return {"error": f"[{mandatory_field}] field is mandatory."}, 400

    if user != "edit":
        if (
            data["language"] != "mg"
            or data["site"] != "wiktionary"
            or not isinstance(data["page"], str)
            or not data["page"]
            or not isinstance(data["content"], str)
            or not isinstance(data["summary"], str)
            or not isinstance(data["minor"], bool)
            or data.get("action", "edit") != "edit"
            or "expected_content_sha256" in data
            and (
                not isinstance(data["expected_content_sha256"], str)
                or not SHA256_PATTERN.fullmatch(data["expected_content_sha256"])
            )
        ):
            return {"error": "Queued Wiktionary message is invalid."}, 400
    try:
        payload = json.dumps(
            data,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
    except (TypeError, ValueError):
        return {"error": "Request body is not JSON serializable."}, 400
    try:
        if not _get_gateway_replay_store().claim(
            gateway_nonce,
            gateway_expires_at,
        ):
            return {"error": "Gateway request has already been used."}, 409
    except (OSError, sqlite3.Error):
        return {"error": "Gateway replay protection is unavailable."}, 503
    try:
        push(user, payload)
    except (OSError, pika.exceptions.AMQPError):
        return {"error": "RabbitMQ could not confirm the message."}, 502
    return {"message": "message sent."}, 204

if __name__ == "__main__":
    HOST = "0.0.0.0"
    app.run(HOST, PORT)
