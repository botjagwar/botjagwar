"""RabbitMQ transport for page-check results that require manual review."""

from __future__ import annotations

import json
import logging
import math
import re
import time
from typing import Any, Callable, Collection, Dict, TypeVar

import pika

from api.config import BotjagwarConfig

log = logging.getLogger(__name__)


PAGE_CHECK_REVIEW_KIND = "page-check-review"
PAGE_CHECK_REVIEW_SCHEMA_VERSION = 1
DEFAULT_PAGE_CHECK_REVIEW_QUEUE = "page-check-review"
REVIEWABLE_PAGE_CHECK_OUTCOMES = frozenset({"unverifiable", "error"})
_MAX_REVIEW_MESSAGE_BYTES = 32_000
_MAX_REVIEW_MESSAGE_LENGTH = 1_000
_MAX_REVIEW_ISSUES = 8
_MAX_REVIEW_ISSUE_DESCRIPTION_LENGTH = 1_000
_MAX_REVIEW_ENTRY_BYTES = 8_000
_QUEUE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,255}$")
_Transferred = TypeVar("_Transferred")


class PageCheckReviewQueueError(RuntimeError):
    """Raised when a page-check review message cannot be transferred safely."""


def _valid_page_title(value: Any) -> bool:
    """Return whether review evidence contains one canonical display-safe title."""
    return (
        isinstance(value, str)
        and bool(value)
        and value == value.strip()
        and len(value) <= 512
        and not any(ord(character) < 32 for character in value)
    )


def validate_review_queue_separation(
    review_queue_name: str,
    executable_queue_names: Collection[str],
) -> None:
    """Reject a review inbox that could be consumed as an executable edit queue."""
    if not _QUEUE_NAME_PATTERN.fullmatch(review_queue_name):
        raise ValueError("The page-check review queue name is invalid.")
    if review_queue_name in executable_queue_names:
        raise ValueError(
            "The page-check review queue must differ from every publication queue."
        )


def build_page_check_review_message(
    job: Dict[str, Any],
    *,
    queued_at: float | None = None,
) -> Dict[str, Any]:
    """Build one bounded, versioned review event from a terminal page-check job."""
    job_id = job.get("job_id")
    language = job.get("language")
    titles = job.get("titles")
    if not isinstance(job_id, str) or not job_id:
        raise PageCheckReviewQueueError("Page-check review jobs require a job ID.")
    if not isinstance(language, str) or not language:
        raise PageCheckReviewQueueError("Page-check review jobs require a language.")
    if (
        not isinstance(titles, list)
        or len(titles) != 1
        or not _valid_page_title(titles[0])
    ):
        raise PageCheckReviewQueueError(
            "Page-check review jobs must identify exactly one title."
        )

    result = _review_result(job, titles[0])
    outcome = result["status"]
    if outcome not in REVIEWABLE_PAGE_CHECK_OUTCOMES:
        raise PageCheckReviewQueueError(
            f"Page-check outcome '{outcome}' does not require manual review."
        )

    message: Dict[str, Any] = {
        "kind": PAGE_CHECK_REVIEW_KIND,
        "schema_version": PAGE_CHECK_REVIEW_SCHEMA_VERSION,
        "event_id": f"page-check:{job_id}",
        "job_id": job_id,
        "queued_at": time.time() if queued_at is None else queued_at,
        "language": language,
        "title": titles[0],
        "outcome": outcome,
        "message": _bounded_text(result.get("message")),
        "source_language": _bounded_optional_text(result.get("source_language"), 32),
        "source_title": _bounded_optional_page_title(result.get("source_title")),
        "issues": _bounded_issues(result.get("issues")),
        "mg_entry": _bounded_entry(result.get("mg_entry")),
    }
    encoded = _encode_message(message)
    if len(encoded) > _MAX_REVIEW_MESSAGE_BYTES:
        raise PageCheckReviewQueueError("Page-check review message is too large.")
    return validate_page_check_review_message(message)


def validate_page_check_review_message(message: Any) -> Dict[str, Any]:
    """Validate a review event received from RabbitMQ and return a safe copy."""
    if not isinstance(message, dict):
        raise PageCheckReviewQueueError("Page-check review message must be an object.")
    required = {
        "kind",
        "schema_version",
        "event_id",
        "job_id",
        "queued_at",
        "language",
        "title",
        "outcome",
        "message",
        "source_language",
        "source_title",
        "issues",
        "mg_entry",
    }
    if set(message) != required:
        raise PageCheckReviewQueueError("Page-check review message has an invalid shape.")
    if (
        message["kind"] != PAGE_CHECK_REVIEW_KIND
        or message["schema_version"] != PAGE_CHECK_REVIEW_SCHEMA_VERSION
        or not isinstance(message["event_id"], str)
        or not message["event_id"].startswith("page-check:")
        or not isinstance(message["job_id"], str)
        or not message["job_id"]
        or len(message["job_id"]) > 512
        or message["event_id"] != f"page-check:{message['job_id']}"
        or not isinstance(message["queued_at"], (int, float))
        or isinstance(message["queued_at"], bool)
        or not math.isfinite(message["queued_at"])
        or not isinstance(message["language"], str)
        or not message["language"]
        or len(message["language"]) > 32
        or not _valid_page_title(message["title"])
        or message["outcome"] not in REVIEWABLE_PAGE_CHECK_OUTCOMES
        or not isinstance(message["message"], str)
        or len(message["message"]) > _MAX_REVIEW_MESSAGE_LENGTH
        or not isinstance(message["issues"], list)
        or not _valid_issues(message["issues"])
        or message["source_language"] is not None
        and (
            not isinstance(message["source_language"], str)
            or len(message["source_language"]) > 32
        )
        or message["source_title"] is not None
        and not _valid_page_title(message["source_title"])
        or message["mg_entry"] is not None
        and _bounded_entry(message["mg_entry"]) is None
    ):
        raise PageCheckReviewQueueError("Page-check review message is invalid.")
    if len(_encode_message(message)) > _MAX_REVIEW_MESSAGE_BYTES:
        raise PageCheckReviewQueueError("Page-check review message is too large.")
    return dict(message)


class RabbitMqPageCheckReviewQueue:
    """Publish and durably transfer page-check review events through RabbitMQ."""

    def __init__(
        self,
        queue_name: str = DEFAULT_PAGE_CHECK_REVIEW_QUEUE,
        *,
        config: BotjagwarConfig | None = None,
        connection_factory: Callable[[pika.ConnectionParameters], Any] | None = None,
    ) -> None:
        """Initialize a lazy queue connection using protected Botjagwar settings."""
        if not _QUEUE_NAME_PATTERN.fullmatch(queue_name):
            raise ValueError("The page-check review queue name is invalid.")
        settings = config or BotjagwarConfig()
        credentials = pika.PlainCredentials(
            settings.get("username", "rabbitmq"),
            settings.get("password", "rabbitmq"),
        )
        self._parameters = pika.ConnectionParameters(
            host=settings.get("host", "rabbitmq"),
            virtual_host=settings.get("virtual_host", "rabbitmq"),
            credentials=credentials,
            heartbeat=60,
            blocked_connection_timeout=30,
        )
        self._queue_name = queue_name
        self._connection_factory = connection_factory or pika.BlockingConnection

    @property
    def queue_name(self) -> str:
        """Return the dedicated review queue name."""
        return self._queue_name

    def publish_job(self, job: Dict[str, Any]) -> str:
        """Publish one terminal reviewable job and return its stable event ID."""
        return self.publish_message(build_page_check_review_message(job))

    def publish_message(self, message: Dict[str, Any]) -> str:
        """Publish one already-persisted review event without rebuilding it."""
        message = validate_page_check_review_message(message)
        connection = None
        try:
            connection = self._connection_factory(self._parameters)
            channel = connection.channel()
            channel.queue_declare(queue=self._queue_name, durable=True)
            channel.confirm_delivery()
            channel.basic_publish(
                exchange="",
                routing_key=self._queue_name,
                body=_encode_message(message),
                mandatory=True,
                properties=pika.BasicProperties(
                    content_type="application/json",
                    delivery_mode=2,
                    message_id=message["event_id"],
                    type=PAGE_CHECK_REVIEW_KIND,
                ),
            )
        except PageCheckReviewQueueError:
            raise
        except (OSError, pika.exceptions.AMQPError) as exc:
            raise PageCheckReviewQueueError(
                "Page-check review message could not be queued."
            ) from exc
        finally:
            self._close_connection_quietly(connection)
        return message["event_id"]

    def transfer_next(
        self,
        accept: Callable[[Dict[str, Any]], _Transferred],
    ) -> _Transferred | None:
        """Move one queue message into a durable caller store before acknowledging it."""
        connection = None
        channel = None
        delivery_tag = None
        cleanup_requeue = True
        try:
            connection = self._connection_factory(self._parameters)
            channel = connection.channel()
            channel.queue_declare(queue=self._queue_name, durable=True)
            method, _properties, body = channel.basic_get(
                queue=self._queue_name,
                auto_ack=False,
            )
            if method is None:
                return None
            delivery_tag = method.delivery_tag
            try:
                if not isinstance(body, bytes) or len(body) > _MAX_REVIEW_MESSAGE_BYTES:
                    raise PageCheckReviewQueueError(
                        "Page-check review message is too large."
                    )
                decoded = json.loads(body.decode("utf-8"))
                message = validate_page_check_review_message(decoded)
            except (
                AttributeError,
                RecursionError,
                UnicodeDecodeError,
                json.JSONDecodeError,
                PageCheckReviewQueueError,
            ) as exc:
                cleanup_requeue = False
                raise PageCheckReviewQueueError(
                    "RabbitMQ returned an invalid page-check review message."
                ) from exc
            try:
                transferred = accept(message)
            except PageCheckReviewQueueError:
                cleanup_requeue = False
                raise
            except Exception:
                raise
            channel.basic_ack(delivery_tag=delivery_tag)
            delivery_tag = None
            return transferred
        except PageCheckReviewQueueError:
            raise
        except (OSError, pika.exceptions.AMQPError) as exc:
            raise PageCheckReviewQueueError(
                "Page-check review queue could not be read."
            ) from exc
        finally:
            try:
                if (
                    delivery_tag is not None
                    and channel is not None
                    and connection is not None
                    and bool(getattr(channel, "is_open", True))
                    and bool(getattr(connection, "is_open", True))
                ):
                    try:
                        channel.basic_nack(
                            delivery_tag=delivery_tag,
                            requeue=cleanup_requeue,
                        )
                    except (OSError, pika.exceptions.AMQPError) as exc:
                        log.warning(
                            "Could not dispose page-check review delivery during cleanup: %s",
                            exc,
                        )
            finally:
                self._close_connection_quietly(connection)

    @staticmethod
    def _close_connection_quietly(connection: Any) -> None:
        """Close a RabbitMQ connection without masking the operation outcome."""
        if connection is None or not bool(getattr(connection, "is_open", True)):
            return
        try:
            connection.close()
        except (OSError, pika.exceptions.AMQPError) as exc:
            log.warning("Could not close page-check review queue connection: %s", exc)


def _review_result(job: Dict[str, Any], title: str) -> Dict[str, Any]:
    """Return the one result represented by a terminal review job."""
    if job.get("status") == "error":
        return {
            "word": title,
            "status": "error",
            "message": str(job.get("error") or "The page check job failed."),
            "source_language": None,
            "source_title": None,
            "issues": [],
            "mg_entry": None,
        }
    results = job.get("results")
    if not isinstance(results, list) or len(results) != 1 or not isinstance(results[0], dict):
        raise PageCheckReviewQueueError(
            "Completed page-check review jobs require exactly one result."
        )
    return results[0]


def _bounded_text(value: Any, maximum: int = _MAX_REVIEW_MESSAGE_LENGTH) -> str:
    """Return bounded text for an untrusted review field."""
    return str(value or "")[:maximum]


def _bounded_optional_text(value: Any, maximum: int) -> str | None:
    """Return bounded optional text for an untrusted review field."""
    if value is None:
        return None
    return _bounded_text(value, maximum)


def _bounded_optional_page_title(value: Any) -> str | None:
    """Return valid optional page evidence, omitting malformed untrusted titles."""
    return value if _valid_page_title(value) else None


def _bounded_issues(value: Any) -> list[Dict[str, str]]:
    """Return the bounded issue fields needed for manual review."""
    if not isinstance(value, list):
        return []
    issues: list[Dict[str, str]] = []
    for issue in value[:_MAX_REVIEW_ISSUES]:
        if not isinstance(issue, dict):
            continue
        issues.append(
            {
                "type": _bounded_text(issue.get("type"), 128),
                "description": _bounded_text(
                    issue.get("description"),
                    _MAX_REVIEW_ISSUE_DESCRIPTION_LENGTH,
                ),
            }
        )
    return issues


def _valid_issues(value: list[Any]) -> bool:
    """Return whether received issues match the bounded producer contract."""
    if len(value) > _MAX_REVIEW_ISSUES:
        return False
    return all(
        isinstance(issue, dict)
        and set(issue) == {"type", "description"}
        and isinstance(issue["type"], str)
        and len(issue["type"]) <= 128
        and isinstance(issue["description"], str)
        and len(issue["description"]) <= _MAX_REVIEW_ISSUE_DESCRIPTION_LENGTH
        for issue in value
    )


def _bounded_entry(value: Any) -> Dict[str, Any] | None:
    """Return a compact entry only when it remains safely below the queue bound."""
    if not isinstance(value, dict):
        return None
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError):
        return None
    return dict(value) if len(encoded) <= _MAX_REVIEW_ENTRY_BYTES else None


def _encode_message(message: Dict[str, Any]) -> bytes:
    """Encode a review event deterministically for RabbitMQ."""
    try:
        return json.dumps(
            message,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PageCheckReviewQueueError(
            "Page-check review message is not JSON serializable."
        ) from exc
