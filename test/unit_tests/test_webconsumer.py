"""Tests for confirmed RabbitMQ gateway publication."""

from __future__ import annotations

import time
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

import webconsumer
from api.services.rabbitmq_gateway_auth import (
    RABBITMQ_GATEWAY_TIMESTAMP_HEADER,
    SqliteRabbitMqGatewayReplayStore,
    rabbitmq_gateway_auth_headers,
)

GATEWAY_SECRET = "test-only-gateway-hmac-secret-1234567890"


@pytest.fixture(autouse=True)
def _configure_gateway_auth(monkeypatch: Any) -> None:
    monkeypatch.setattr(webconsumer, "RABBITMQ_GATEWAY_HMAC_SECRET", GATEWAY_SECRET)
    monkeypatch.setattr(webconsumer, "_GATEWAY_REPLAY_STORE", DummyReplayStore())


def _gateway_headers(queue: str, message: Any) -> dict[str, str]:
    """Sign one test request for its exact executable queue."""
    return rabbitmq_gateway_auth_headers(
        message,
        GATEWAY_SECRET,
        expected_queue=queue,
    )


class DummyReplayStore:
    """Atomically remember request nonces for gateway route tests."""

    def __init__(self) -> None:
        self.nonces: set[str] = set()

    def claim(self, nonce: str, _expires_at: float) -> bool:
        if nonce in self.nonces:
            return False
        self.nonces.add(nonce)
        return True


class DummyChannel:
    """Capture gateway broker operations."""

    def __init__(self, publish_error: Exception | None = None) -> None:
        self.publish_error = publish_error
        self.declarations: list[dict[str, Any]] = []
        self.messages: list[dict[str, Any]] = []
        self.confirmed = False

    def queue_declare(self, **kwargs: Any) -> None:
        self.declarations.append(kwargs)

    def confirm_delivery(self) -> None:
        self.confirmed = True

    def basic_publish(self, **kwargs: Any) -> None:
        self.messages.append(kwargs)
        if self.publish_error is not None:
            raise self.publish_error


class DummyConnection:
    """Capture gateway connection cleanup."""

    def __init__(self, close_error: Exception | None = None) -> None:
        self.is_open = True
        self.close_error = close_error

    def close(self) -> None:
        self.is_open = False
        if self.close_error is not None:
            raise self.close_error


def test_push_declares_durable_queue_and_requires_confirmation(monkeypatch: Any) -> None:
    channel = DummyChannel()
    connection = DummyConnection()
    monkeypatch.setattr(webconsumer, "make_channel", lambda: (connection, channel))

    webconsumer.push("translated", '{"page":"saka"}')

    assert channel.declarations == [{"queue": "translated", "durable": True}]
    assert channel.confirmed is True
    assert channel.messages[0]["routing_key"] == "translated"
    assert channel.messages[0]["mandatory"] is True
    assert channel.messages[0]["properties"].delivery_mode == 2
    assert channel.messages[0]["properties"].content_type == "application/json"
    assert connection.is_open is False


def test_push_closes_connection_when_confirmed_publish_fails(
    monkeypatch: Any,
) -> None:
    channel = DummyChannel(publish_error=RuntimeError("broker nack"))
    connection = DummyConnection()
    monkeypatch.setattr(webconsumer, "make_channel", lambda: (connection, channel))

    with pytest.raises(RuntimeError, match="broker nack"):
        webconsumer.push("translated", "{}")

    assert connection.is_open is False


def test_push_preserves_confirmed_publish_when_connection_cleanup_fails(
    monkeypatch: Any,
) -> None:
    channel = DummyChannel()
    connection = DummyConnection(OSError("connection dropped"))
    monkeypatch.setattr(webconsumer, "make_channel", lambda: (connection, channel))

    webconsumer.push("translated", '{"page":"saka"}')

    assert len(channel.messages) == 1
    assert connection.is_open is False


def test_gateway_has_no_queue_draining_get_routes(monkeypatch: Any) -> None:
    make_channel = pytest.fail
    monkeypatch.setattr(webconsumer, "make_channel", make_channel)
    client = webconsumer.app.test_client()

    assert client.get("/translated/next").status_code == 404
    assert client.get("/translated").status_code == 405


def test_gateway_requires_absolute_production_replay_ledger(monkeypatch: Any) -> None:
    monkeypatch.setattr(webconsumer, "TEST_MODE", False)
    monkeypatch.setattr(webconsumer, "GATEWAY_REPLAY_LEDGER_PATH", "relative.sqlite3")

    with pytest.raises(RuntimeError, match="must be absolute"):
        webconsumer._validate_gateway_configuration()  # pylint: disable=protected-access


def test_send_validates_payload_before_queueing(monkeypatch: Any) -> None:
    queued: list[tuple[str, str]] = []
    monkeypatch.setattr(
        webconsumer, "push", lambda queue, body: queued.append((queue, body))
    )
    client = webconsumer.app.test_client()

    invalid_message = {"page": "saka"}
    valid_message = {
            "language": "mg",
            "site": "wiktionary",
            "page": "saka",
            "content": "content",
            "summary": "summary",
            "minor": False,
            "expected_content_sha256": "a" * 64,
        }
    invalid = client.post(
        "/translated",
        json=invalid_message,
        headers=_gateway_headers("translated", invalid_message),
    )
    valid = client.post(
        "/translated",
        json=valid_message,
        headers=_gateway_headers("translated", valid_message),
    )

    assert invalid.status_code == 400
    assert valid.status_code == 204
    assert queued[0][0] == "translated"
    assert "expected_content_sha256" in queued[0][1]


def test_send_rejects_invalid_json_types_and_hashes() -> None:
    client = webconsumer.app.test_client()
    invalid_message = {
            "language": "mg",
            "site": "wiktionary",
            "page": "saka",
            "content": "content",
            "summary": "summary",
            "minor": False,
            "expected_content_sha256": None,
        }
    invalid_hash = client.post(
        "/translated",
        json=invalid_message,
        headers=_gateway_headers("translated", invalid_message),
    )

    assert client.post("/translated", json=[]).status_code == 400
    assert invalid_hash.status_code == 400


def test_send_rejects_http_delete_action() -> None:
    client = webconsumer.app.test_client()

    message = {
            "language": "mg",
            "site": "wiktionary",
            "page": "saka",
            "content": "",
            "summary": "delete",
            "minor": False,
            "action": "delete",
        }
    response = client.post(
        "/translated",
        json=message,
        headers=_gateway_headers("translated", message),
    )

    assert response.status_code == 400


def test_send_requires_queue_bound_gateway_authentication() -> None:
    client = webconsumer.app.test_client()
    message = {
        "language": "mg",
        "site": "wiktionary",
        "page": "saka",
        "content": "content",
        "summary": "summary",
        "minor": False,
    }

    missing = client.post("/translated", json=message)
    wrong_queue = client.post(
        "/translated",
        json=message,
        headers=_gateway_headers("botjagwar", message),
    )

    assert missing.status_code == 401
    assert wrong_queue.status_code == 401


def test_send_rejects_stale_and_replayed_gateway_requests(
    monkeypatch: Any,
) -> None:
    queued: list[str] = []
    monkeypatch.setattr(
        webconsumer,
        "push",
        lambda _queue, body: queued.append(body),
    )
    message = {
        "language": "mg",
        "site": "wiktionary",
        "page": "saka",
        "content": "content",
        "summary": "summary",
        "minor": False,
    }
    headers = _gateway_headers("translated", message)
    stale_headers = rabbitmq_gateway_auth_headers(
        message,
        GATEWAY_SECRET,
        expected_queue="translated",
        issued_at=int(time.time()) - 301,
        nonce="a" * 64,
    )
    client = webconsumer.app.test_client()

    accepted = client.post("/translated", json=message, headers=headers)
    replayed = client.post("/translated", json=message, headers=headers)
    stale = client.post("/translated", json=message, headers=stale_headers)

    assert accepted.status_code == 204
    assert replayed.status_code == 409
    assert stale.status_code == 401
    assert len(queued) == 1


def test_gateway_limits_unauthenticated_request_bodies(monkeypatch: Any) -> None:
    monkeypatch.setitem(webconsumer.app.config, "MAX_CONTENT_LENGTH", 128)

    response = webconsumer.app.test_client().post(
        "/translated",
        data='{"content":"' + "x" * 256 + '"}',
        content_type="application/json",
    )

    assert response.status_code == 413


def test_gateway_limits_chunked_request_bodies(monkeypatch: Any) -> None:
    monkeypatch.setitem(webconsumer.app.config, "MAX_CONTENT_LENGTH", 128)
    body = ('{"content":"' + "x" * 256 + '"}').encode()

    response = webconsumer.app.test_client().open(
        "/translated",
        method="POST",
        input_stream=BytesIO(body),
        content_type="application/json",
        environ_overrides={"CONTENT_LENGTH": "", "wsgi.input_terminated": True},
    )

    assert response.status_code == 413


def test_gateway_rejects_deep_json_and_oversized_timestamp() -> None:
    client = webconsumer.app.test_client()
    deep_json = "[" * 2_000 + "0" + "]" * 2_000
    message = {
        "language": "mg",
        "site": "wiktionary",
        "page": "saka",
        "content": "content",
        "summary": "summary",
        "minor": False,
    }
    headers = _gateway_headers("translated", message)
    headers[RABBITMQ_GATEWAY_TIMESTAMP_HEADER] = "9" * 5_000

    nested = client.post(
        "/translated",
        data=deep_json,
        content_type="application/json",
    )
    oversized_timestamp = client.post(
        "/translated",
        json=message,
        headers=headers,
    )

    assert nested.status_code == 400
    assert oversized_timestamp.status_code == 401


def test_gateway_replay_store_persists_nonces(tmp_path: Path) -> None:
    path = tmp_path / "gateway-replays.sqlite3"
    first = SqliteRabbitMqGatewayReplayStore(path)

    assert first.claim("a" * 64, 2_000, now=1_000) is True
    assert SqliteRabbitMqGatewayReplayStore(path).claim(
        "a" * 64,
        2_000,
        now=1_001,
    ) is False


def test_send_reports_unconfirmed_broker_failure(monkeypatch: Any) -> None:
    def fail(_queue: str, _body: str) -> None:
        raise OSError("broker offline")

    monkeypatch.setattr(webconsumer, "push", fail)
    client = webconsumer.app.test_client()

    message = {
            "language": "mg",
            "site": "wiktionary",
            "page": "saka",
            "content": "content",
            "summary": "summary",
            "minor": False,
        }
    response = client.post(
        "/translated",
        json=message,
        headers=_gateway_headers("translated", message),
    )

    assert response.status_code == 502
    assert response.json == {"error": "RabbitMQ could not confirm the message."}
