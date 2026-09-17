"""Tests for durable RabbitMQ forwarding between Botjagwar queues."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from api import rabbitmq
from api.http_client import DEFAULT_HTTP_TIMEOUT
from api.services.rabbitmq_gateway_auth import (
    RABBITMQ_GATEWAY_HMAC_HEADER,
    RABBITMQ_GATEWAY_NONCE_HEADER,
    RABBITMQ_GATEWAY_TIMESTAMP_HEADER,
)

GATEWAY_SECRET = "test-only-gateway-hmac-secret-1234567890"
GATEWAY_HEADERS = {
    RABBITMQ_GATEWAY_HMAC_HEADER: "a" * 64,
    RABBITMQ_GATEWAY_TIMESTAMP_HEADER: "1234567890",
    RABBITMQ_GATEWAY_NONCE_HEADER: "b" * 64,
}


class DummyChannel:
    """Capture producer queue and confirmation operations."""

    def __init__(self) -> None:
        self.declarations: list[dict[str, Any]] = []
        self.published: list[dict[str, Any]] = []
        self.confirmations = 0
        self.acks: list[str] = []
        self.nacks: list[dict[str, Any]] = []
        self.is_open = True

    def queue_declare(self, **kwargs: Any) -> None:
        self.declarations.append(kwargs)

    def confirm_delivery(self) -> None:
        self.confirmations += 1

    def basic_publish(self, **kwargs: Any) -> None:
        self.published.append(kwargs)

    def basic_ack(self, *, delivery_tag: str) -> None:
        self.acks.append(delivery_tag)

    def basic_nack(self, **kwargs: Any) -> None:
        self.nacks.append(kwargs)


class DummyConnection:
    """Expose a captured channel to the producer."""

    def __init__(
        self,
        channel: DummyChannel,
        process_error: Exception | None = None,
    ) -> None:
        self._channel = channel
        self._process_error = process_error
        self.is_open = True

    def channel(self) -> DummyChannel:
        return self._channel

    def close(self) -> None:
        self.is_open = False

    def process_data_events(self, time_limit: int = 0) -> None:
        if self._process_error is not None:
            raise self._process_error


def test_producer_uses_confirms_and_mandatory_routing(
    monkeypatch: Any,
) -> None:
    channel = DummyChannel()
    monkeypatch.setattr(
        rabbitmq.pika,
        "BlockingConnection",
        lambda _parameters: DummyConnection(channel),
    )

    producer = rabbitmq.RabbitMqProducer("botjagwar")
    producer.publish("{}")

    assert channel.confirmations == 1
    assert channel.published == [
        {
            "exchange": "",
            "routing_key": "botjagwar",
            "body": "{}",
            "properties": channel.published[0]["properties"],
            "mandatory": True,
        }
    ]
    assert channel.published[0]["properties"].delivery_mode == 2
    assert producer.parameters.heartbeat == 60
    assert producer.parameters.blocked_connection_timeout == 20


def test_producer_reconnects_before_publish_when_idle_connection_was_reset(
    monkeypatch: Any,
) -> None:
    """A heartbeat failure is safe to recover before sending the payload."""
    stale_channel = DummyChannel()
    fresh_channel = DummyChannel()
    connections = iter(
        [
            DummyConnection(
                stale_channel,
                rabbitmq.pika.exceptions.StreamLostError("connection reset"),
            ),
            DummyConnection(fresh_channel),
        ]
    )
    monkeypatch.setattr(
        rabbitmq.pika,
        "BlockingConnection",
        lambda _parameters: next(connections),
    )

    producer = rabbitmq.RabbitMqProducer("botjagwar")
    producer.publish("{}")

    assert stale_channel.published == []
    assert fresh_channel.published == [
        {
            "exchange": "",
            "routing_key": "botjagwar",
            "body": "{}",
            "properties": fresh_channel.published[0]["properties"],
            "mandatory": True,
        }
    ]


def test_consumer_discards_poison_message_without_stopping_callback(
    monkeypatch: Any,
) -> None:
    channel = DummyChannel()
    monkeypatch.setattr(
        rabbitmq.pika,
        "BlockingConnection",
        lambda _parameters: DummyConnection(channel),
    )
    callback = MagicMock()
    consumer = rabbitmq.RabbitMqConsumer("translated", callback)
    method = SimpleNamespace(delivery_tag="delivery", redelivered=False)

    consumer.callback(channel, method, None, b"not-json")

    callback.assert_not_called()
    assert channel.acks == []
    assert channel.nacks == [{"delivery_tag": "delivery", "requeue": False}]


def test_consumer_retries_callback_failure_once(monkeypatch: Any) -> None:
    channel = DummyChannel()
    monkeypatch.setattr(
        rabbitmq.pika,
        "BlockingConnection",
        lambda _parameters: DummyConnection(channel),
    )
    consumer = rabbitmq.RabbitMqConsumer(
        "translated", MagicMock(side_effect=RuntimeError("offline"))
    )

    consumer.callback(
        channel,
        SimpleNamespace(delivery_tag="first", redelivered=False),
        None,
        b'{"content":"value"}',
    )
    consumer.callback(
        channel,
        SimpleNamespace(delivery_tag="second", redelivered=True),
        None,
        b'{"content":"value"}',
    )

    assert channel.nacks == [
        {"delivery_tag": "first", "requeue": True},
        {"delivery_tag": "second", "requeue": False},
    ]


def test_generic_consumer_rejects_review_queue() -> None:
    with pytest.raises(rabbitmq.RabbitMqError, match="protected queue"):
        rabbitmq.RabbitMqConsumer("page-check-review", MagicMock())


def test_consumer_discards_oversized_and_deep_messages(monkeypatch: Any) -> None:
    channel = DummyChannel()
    monkeypatch.setattr(
        rabbitmq.pika,
        "BlockingConnection",
        lambda _parameters: DummyConnection(channel),
    )
    monkeypatch.setattr(rabbitmq, "MAX_RABBITMQ_MESSAGE_BYTES", 8)
    consumer = rabbitmq.RabbitMqConsumer("edit2", MagicMock())

    consumer.callback(
        channel,
        SimpleNamespace(delivery_tag="large"),
        None,
        b'{"content":"too large"}',
    )
    monkeypatch.setattr(rabbitmq, "MAX_RABBITMQ_MESSAGE_BYTES", 16_384)
    consumer.callback(
        channel,
        SimpleNamespace(delivery_tag="deep"),
        None,
        ("[" * 2_000 + "0" + "]" * 2_000).encode(),
    )

    assert channel.nacks == [
        {"delivery_tag": "large", "requeue": False},
        {"delivery_tag": "deep", "requeue": False},
    ]


def test_web_service_authenticates_queue_bound_message(monkeypatch: Any) -> None:
    response = SimpleNamespace(status_code=204)
    post = MagicMock(return_value=response)
    monkeypatch.setattr(rabbitmq.requests, "post", post)
    auth_headers = MagicMock(return_value=GATEWAY_HEADERS)
    monkeypatch.setattr(rabbitmq, "rabbitmq_gateway_auth_headers", auth_headers)
    publisher = rabbitmq.RabbitMqWebService(
        "translated", gateway_hmac_secret=GATEWAY_SECRET
    )
    publisher.service = "gateway"
    message = {"content": "value"}

    publisher.publish(message)

    post.assert_called_once_with(
        "http://gateway:8443/translated",
        json=message,
        timeout=DEFAULT_HTTP_TIMEOUT,
        headers=GATEWAY_HEADERS,
    )
    auth_headers.assert_called_once_with(
        message,
        GATEWAY_SECRET,
        expected_queue="translated",
    )


def test_web_service_uses_gateway_service_instead_of_amqp_host(
    monkeypatch: Any,
) -> None:
    values = {
        ("queue", "rabbitmq"): "botjagwar",
        ("service", "rabbitmq"): "gateway.example",
        ("host", "rabbitmq"): "broker.example",
    }
    monkeypatch.setattr(
        rabbitmq.config,
        "get",
        lambda key, section="global": values[(key, section)],
    )

    publisher = rabbitmq.RabbitMqWebService(gateway_hmac_secret=GATEWAY_SECRET)

    assert publisher.service == "gateway.example"


def test_web_service_falls_back_to_amqp_host_for_legacy_config(
    monkeypatch: Any,
) -> None:
    def get_config(key: str, section: str = "global") -> str:
        if (key, section) == ("service", "rabbitmq"):
            raise KeyError(key)
        return {
            ("queue", "rabbitmq"): "botjagwar",
            ("host", "rabbitmq"): "legacy.example",
        }[(key, section)]

    monkeypatch.setattr(rabbitmq.config, "get", get_config)

    publisher = rabbitmq.RabbitMqWebService(gateway_hmac_secret=GATEWAY_SECRET)

    assert publisher.service == "legacy.example"
