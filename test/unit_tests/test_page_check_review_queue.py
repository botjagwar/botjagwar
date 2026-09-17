"""Tests for the dedicated page-check review RabbitMQ transport."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pika
import pytest

from api.services.page_check_review_queue import (
    PAGE_CHECK_REVIEW_KIND,
    PageCheckReviewQueueError,
    RabbitMqPageCheckReviewQueue,
    build_page_check_review_message,
    validate_page_check_review_message,
)


class FakeConfig:
    """Return fixed non-secret RabbitMQ test settings."""

    def get(self, key: str, section: str = "global") -> str:
        """Return one configured value."""
        assert section == "rabbitmq"
        return {
            "host": "rabbit.test",
            "username": "reviewer",
            "password": "secret",
            "virtual_host": "botjagwar",
        }[key]


class FakeChannel:
    """Capture RabbitMQ channel operations."""

    def __init__(self) -> None:
        """Initialize captured operations and an empty basic-get response."""
        self.declarations: list[dict[str, Any]] = []
        self.published: list[dict[str, Any]] = []
        self.acknowledged: list[int] = []
        self.rejected: list[tuple[int, bool]] = []
        self.get_response: tuple[Any, Any, Any] = (None, None, None)
        self.confirmed = False
        self.is_open = True

    def queue_declare(self, **kwargs: Any) -> None:
        """Capture a queue declaration."""
        self.declarations.append(kwargs)

    def confirm_delivery(self) -> None:
        """Capture publisher-confirm activation."""
        self.confirmed = True

    def basic_publish(self, **kwargs: Any) -> bool:
        """Capture a published message and confirm it."""
        self.published.append(kwargs)
        return True

    def basic_get(self, **_kwargs: Any) -> tuple[Any, Any, Any]:
        """Return the configured basic-get response."""
        return self.get_response

    def basic_ack(self, delivery_tag: int) -> None:
        """Capture a message acknowledgement."""
        self.acknowledged.append(delivery_tag)

    def basic_nack(self, delivery_tag: int, requeue: bool) -> None:
        """Capture a rejected message."""
        self.rejected.append((delivery_tag, requeue))


class FakeConnection:
    """Expose one fake channel and capture closure."""

    def __init__(
        self, channel: FakeChannel, close_error: Exception | None = None
    ) -> None:
        """Initialize an open fake connection."""
        self._channel = channel
        self.is_open = True
        self.close_error = close_error
        self.close_calls = 0

    def channel(self) -> FakeChannel:
        """Return the fake channel."""
        return self._channel

    def close(self) -> None:
        """Close the fake connection."""
        self.close_calls += 1
        if self.close_error is not None:
            raise self.close_error
        self.is_open = False


def review_job(status: str = "unverifiable") -> dict[str, Any]:
    """Return one terminal page-check job fixture."""
    return {
        "job_id": "job-1",
        "language": "mg",
        "titles": ["alika"],
        "status": "done",
        "results": [
            {
                "word": "alika",
                "status": status,
                "message": "Needs a human review.",
                "source_language": "en",
                "source_title": "dog",
                "issues": [
                    {"type": "definition", "description": "Meaning differs."}
                ],
                "mg_entry": {"entry": "alika"},
            }
        ],
    }


def build_queue(channel: FakeChannel) -> tuple[RabbitMqPageCheckReviewQueue, FakeConnection]:
    """Build a queue around one fake RabbitMQ connection."""
    connection = FakeConnection(channel)
    queue = RabbitMqPageCheckReviewQueue(
        config=FakeConfig(),  # type: ignore[arg-type]
        connection_factory=lambda _parameters: connection,
    )
    return queue, connection


def test_build_review_message_uses_stable_bounded_contract() -> None:
    """Review messages identify the source job without resembling wiki edits."""
    message = build_page_check_review_message(review_job(), queued_at=12.5)

    assert message == {
        "kind": PAGE_CHECK_REVIEW_KIND,
        "schema_version": 1,
        "event_id": "page-check:job-1",
        "job_id": "job-1",
        "queued_at": 12.5,
        "language": "mg",
        "title": "alika",
        "outcome": "unverifiable",
        "message": "Needs a human review.",
        "source_language": "en",
        "source_title": "dog",
        "issues": [{"type": "definition", "description": "Meaning differs."}],
        "mg_entry": {"entry": "alika"},
    }
    assert "content" not in message
    assert "summary" not in message


def test_build_review_message_rejects_assessable_outcome() -> None:
    """Good and automatically fixed pages never enter manual review."""
    with pytest.raises(PageCheckReviewQueueError, match="does not require"):
        build_page_check_review_message(review_job("good"))


@pytest.mark.parametrize(
    "updates,message",
    [
        ({"job_id": ""}, "job ID"),
        ({"language": None}, "language"),
        ({"titles": []}, "exactly one title"),
        ({"status": "done", "results": []}, "exactly one result"),
    ],
)
def test_build_review_message_rejects_incomplete_jobs(
    updates: dict[str, Any], message: str
) -> None:
    """Only complete one-page terminal jobs can become review events."""
    job = review_job()
    job.update(updates)

    with pytest.raises(PageCheckReviewQueueError, match=message):
        build_page_check_review_message(job)


def test_build_review_message_serialises_terminal_job_error() -> None:
    """A job-level failure remains reviewable without a page-check result."""
    job = review_job()
    job.update({"status": "error", "error": "worker failed", "results": None})

    message = build_page_check_review_message(job, queued_at=20)

    assert message["outcome"] == "error"
    assert message["message"] == "worker failed"
    assert message["source_title"] is None
    assert message["mg_entry"] is None


def test_build_review_message_bounds_optional_evidence() -> None:
    """Producer-side evidence is compact and JSON-safe."""
    job = review_job()
    result = job["results"][0]
    result.update(
        {
            "message": "x" * 5_000,
            "source_language": None,
            "source_title": "x" * 600,
            "issues": ["invalid", {"type": "x" * 200, "description": "y" * 3_000}],
            "mg_entry": {"invalid": {1, 2}},
        }
    )

    message = build_page_check_review_message(job)

    assert len(message["message"]) == 1_000
    assert message["source_language"] is None
    assert message["source_title"] is None
    assert message["issues"] == [
        {"type": "x" * 128, "description": "y" * 1_000}
    ]
    assert message["mg_entry"] is None


def test_build_review_message_omits_malformed_optional_source_title() -> None:
    """Untrusted optional source metadata cannot suppress a review event."""
    job = review_job()
    job["results"][0]["source_title"] = "dog\nforged"

    message = build_page_check_review_message(job)

    assert message["source_title"] is None
    assert message["event_id"] == "page-check:job-1"


def test_publish_job_declares_durable_queue_and_uses_confirms() -> None:
    """Publish a persistent versioned message to the dedicated queue."""
    channel = FakeChannel()
    queue, connection = build_queue(channel)

    assert queue.publish_job(review_job()) == "page-check:job-1"

    assert channel.declarations == [{"queue": "page-check-review", "durable": True}]
    assert channel.confirmed is True
    published = channel.published[0]
    assert published["routing_key"] == "page-check-review"
    assert published["mandatory"] is True
    assert json.loads(published["body"].decode("utf-8"))["title"] == "alika"
    assert published["properties"].delivery_mode == 2
    assert published["properties"].message_id == "page-check:job-1"
    assert connection.is_open is False


def test_publish_message_preserves_prebuilt_event_bytes() -> None:
    channel = FakeChannel()
    queue, _connection = build_queue(channel)
    message = build_page_check_review_message(review_job(), queued_at=12.5)

    assert queue.publish_message(message) == "page-check:job-1"

    assert json.loads(channel.published[0]["body"].decode("utf-8")) == message


def test_confirmed_publish_ignores_connection_close_failure() -> None:
    """Cleanup cannot turn broker-confirmed publication into a false failure."""
    channel = FakeChannel()
    connection = FakeConnection(channel, OSError("close failed"))
    queue = RabbitMqPageCheckReviewQueue(
        config=FakeConfig(),  # type: ignore[arg-type]
        connection_factory=lambda _parameters: connection,
    )

    assert queue.publish_job(review_job()) == "page-check:job-1"
    assert connection.close_calls == 1


def test_queue_validates_name_and_exposes_it() -> None:
    """Only bounded AMQP queue identifiers are accepted."""
    channel = FakeChannel()
    queue, _connection = build_queue(channel)

    assert queue.queue_name == "page-check-review"
    with pytest.raises(ValueError, match="queue name is invalid"):
        RabbitMqPageCheckReviewQueue("invalid queue", config=FakeConfig())  # type: ignore[arg-type]


def test_publish_job_requires_broker_confirmation() -> None:
    """An unconfirmed publish is reported as a failed durable handoff."""
    channel = FakeChannel()
    channel.basic_publish = MagicMock(  # type: ignore[method-assign]
        side_effect=pika.exceptions.NackError([])
    )
    queue, _connection = build_queue(channel)

    with pytest.raises(PageCheckReviewQueueError, match="could not be queued"):
        queue.publish_job(review_job())


def test_publish_job_wraps_broker_connection_failure() -> None:
    """Transport details do not leak through the review queue boundary."""
    queue = RabbitMqPageCheckReviewQueue(
        config=FakeConfig(),  # type: ignore[arg-type]
        connection_factory=lambda _parameters: (_ for _ in ()).throw(
            OSError("connection details")
        ),
    )

    with pytest.raises(PageCheckReviewQueueError, match="could not be queued"):
        queue.publish_job(review_job())


def test_transfer_next_persists_before_acknowledging() -> None:
    """RabbitMQ is acknowledged only after the caller's durable acceptance succeeds."""
    channel = FakeChannel()
    channel.get_response = (
        SimpleNamespace(delivery_tag=17),
        None,
        json.dumps(build_page_check_review_message(review_job())).encode("utf-8"),
    )
    queue, connection = build_queue(channel)
    accepted: list[str] = []

    result = queue.transfer_next(
        lambda message: accepted.append(message["event_id"]) or message["title"]
    )

    assert result == "alika"
    assert accepted == ["page-check:job-1"]
    assert channel.acknowledged == [17]
    assert channel.rejected == []
    assert connection.is_open is False


def test_transfer_next_reports_empty_queue() -> None:
    """An empty review queue is a normal non-error result."""
    channel = FakeChannel()
    queue, connection = build_queue(channel)

    assert queue.transfer_next(lambda message: message) is None
    assert connection.is_open is False


def test_transfer_next_wraps_broker_connection_failure() -> None:
    """Review consumption reports a bounded transport error."""
    queue = RabbitMqPageCheckReviewQueue(
        config=FakeConfig(),  # type: ignore[arg-type]
        connection_factory=lambda _parameters: (_ for _ in ()).throw(
            OSError("connection details")
        ),
    )

    with pytest.raises(PageCheckReviewQueueError, match="could not be read"):
        queue.transfer_next(lambda message: message)


def test_transfer_next_requeues_unacknowledged_delivery() -> None:
    """A transport failure while acknowledging leaves the event recoverable."""

    class FailingAckChannel(FakeChannel):
        def basic_ack(self, delivery_tag: int) -> None:
            raise OSError(f"ack failed for {delivery_tag}")

    channel = FailingAckChannel()
    channel.get_response = (
        SimpleNamespace(delivery_tag=21),
        None,
        json.dumps(build_page_check_review_message(review_job())).encode("utf-8"),
    )
    queue, _connection = build_queue(channel)

    with pytest.raises(PageCheckReviewQueueError, match="could not be read"):
        queue.transfer_next(lambda message: message)

    assert channel.rejected == [(21, True)]


def test_transfer_next_closes_connection_when_fallback_nack_fails() -> None:
    """Connection closure still makes an unacknowledged delivery recoverable."""

    class FailingDispositionChannel(FakeChannel):
        def basic_ack(self, delivery_tag: int) -> None:
            raise OSError(f"ack failed for {delivery_tag}")

        def basic_nack(self, delivery_tag: int, requeue: bool) -> None:
            raise OSError(f"nack failed for {delivery_tag}:{requeue}")

    channel = FailingDispositionChannel()
    channel.get_response = (
        SimpleNamespace(delivery_tag=23),
        None,
        json.dumps(build_page_check_review_message(review_job())).encode("utf-8"),
    )
    queue, connection = build_queue(channel)

    with pytest.raises(PageCheckReviewQueueError, match="could not be read"):
        queue.transfer_next(lambda message: message)

    assert connection.close_calls == 1
    assert connection.is_open is False


def test_transfer_next_preserves_accept_error_when_cleanup_fails() -> None:
    """Cleanup exceptions must not replace the durable-store failure."""

    class FailingNackChannel(FakeChannel):
        def basic_nack(self, delivery_tag: int, requeue: bool) -> None:
            raise OSError(f"nack failed for {delivery_tag}:{requeue}")

    channel = FailingNackChannel()
    channel.get_response = (
        SimpleNamespace(delivery_tag=24),
        None,
        json.dumps(build_page_check_review_message(review_job())).encode("utf-8"),
    )
    connection = FakeConnection(channel, OSError("close failed"))
    queue = RabbitMqPageCheckReviewQueue(
        config=FakeConfig(),  # type: ignore[arg-type]
        connection_factory=lambda _parameters: connection,
    )

    def conflict(_message: dict[str, Any]) -> None:
        raise PageCheckReviewQueueError("conflicting event")

    with pytest.raises(PageCheckReviewQueueError, match="conflicting event"):
        queue.transfer_next(conflict)

    assert connection.close_calls == 1


def test_transfer_next_requeues_when_durable_acceptance_fails() -> None:
    """A local storage failure leaves the review event available in RabbitMQ."""
    channel = FakeChannel()
    channel.get_response = (
        SimpleNamespace(delivery_tag=18),
        None,
        json.dumps(build_page_check_review_message(review_job())).encode("utf-8"),
    )
    queue, _connection = build_queue(channel)

    def fail(_message: dict[str, Any]) -> None:
        raise RuntimeError("disk full")

    with pytest.raises(RuntimeError, match="disk full"):
        queue.transfer_next(fail)

    assert channel.acknowledged == []
    assert channel.rejected == [(18, True)]


def test_transfer_next_discards_conflicting_event_identity() -> None:
    channel = FakeChannel()
    channel.get_response = (
        SimpleNamespace(delivery_tag=22),
        None,
        json.dumps(build_page_check_review_message(review_job())).encode("utf-8"),
    )
    queue, _connection = build_queue(channel)

    def conflict(_message: dict[str, Any]) -> None:
        raise PageCheckReviewQueueError("conflicting event")

    with pytest.raises(PageCheckReviewQueueError, match="conflicting"):
        queue.transfer_next(conflict)

    assert channel.acknowledged == []
    assert channel.rejected == [(22, False)]


def test_transfer_next_discards_invalid_review_shape() -> None:
    """An invalid poison message is rejected instead of blocking the queue forever."""
    channel = FakeChannel()
    channel.get_response = (
        SimpleNamespace(delivery_tag=19),
        None,
        b'{"kind":"not-a-review"}',
    )
    queue, _connection = build_queue(channel)

    with pytest.raises(PageCheckReviewQueueError, match="invalid"):
        queue.transfer_next(lambda _message: None)

    assert channel.acknowledged == []
    assert channel.rejected == [(19, False)]


@pytest.mark.parametrize(
    "body",
    [
        b"x" * 32_001,
        ("[" * 2_000 + "0" + "]" * 2_000).encode(),
    ],
)
def test_transfer_next_discards_oversized_and_deep_messages(body: bytes) -> None:
    channel = FakeChannel()
    channel.get_response = (SimpleNamespace(delivery_tag=25), None, body)
    queue, _connection = build_queue(channel)

    with pytest.raises(PageCheckReviewQueueError, match="invalid"):
        queue.transfer_next(lambda _message: None)

    assert channel.acknowledged == []
    assert channel.rejected == [(25, False)]


@pytest.mark.parametrize(
    "field,value",
    [
        ("queued_at", float("nan")),
        ("message", "x" * 1_001),
        ("issues", [{"type": "definition", "description": "x", "extra": "x"}]),
        ("title", "alika\nforged-diff-header"),
        ("source_title", " dog "),
    ],
)
def test_validate_review_message_rejects_unbounded_fields(
    field: str, value: Any
) -> None:
    """Queue consumers reject data outside the producer's bounded contract."""
    message = build_page_check_review_message(review_job(), queued_at=12.5)
    message[field] = value

    with pytest.raises(PageCheckReviewQueueError, match="invalid"):
        validate_page_check_review_message(message)


def test_validate_review_message_rejects_non_object_and_oversized_entry() -> None:
    """The consumer validates the outer type and compact-entry bound."""
    with pytest.raises(PageCheckReviewQueueError, match="must be an object"):
        validate_page_check_review_message([])

    message = build_page_check_review_message(review_job(), queued_at=12.5)
    message["mg_entry"] = {"content": "x" * 70_000}
    with pytest.raises(PageCheckReviewQueueError, match="invalid"):
        validate_page_check_review_message(message)
