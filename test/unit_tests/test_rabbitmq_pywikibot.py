"""Tests for conditional RabbitMQ Wiktionary publication."""

from __future__ import annotations

import hashlib
import io
import json
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, call

from pywikibot.exceptions import EditConflictError
import pytest

import rabbitmq_pywikibot as worker
from api.wikimedia_rate_limiter import WikimediaRateLimitError


def _install_page(
    monkeypatch: pytest.MonkeyPatch, current_content: str
) -> MagicMock:
    """Install a fake Pywikibot page containing the supplied live content."""
    page = MagicMock()
    page.get.return_value = current_content
    monkeypatch.setattr(worker, "Site", MagicMock(return_value=object()))
    monkeypatch.setattr(worker, "Page", MagicMock(return_value=page))
    return page


def _message(**updates: object) -> bytes:
    """Return one valid queued Wiktionary edit."""
    message = {
        "language": "mg",
        "site": "wiktionary",
        "page": "alika",
        "content": "new content",
        "summary": "fanitsiana famaritana",
        "minor": False,
    }
    message.update(updates)
    return json.dumps(message).encode("utf-8")


def _disable_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(worker.time, "sleep", MagicMock())
    monkeypatch.setattr(worker, "get_sleep_time", MagicMock(return_value=0))


def test_conditional_edit_saves_when_live_content_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page = _install_page(monkeypatch, "original content")
    expected_hash = hashlib.sha256(b"original content").hexdigest()

    saved = worker.save_to_wiki(
        "alika",
        "new content",
        "fanitsiana famaritana",
        "edit",
        expected_content_sha256=expected_hash,
    )

    assert saved is True
    page.get.assert_called_once_with(force_refresh=True)
    page.put.assert_called_once_with(
        "new content",
        "fanitsiana famaritana",
        force=True,
        minor=False,
        nocreate=True,
        recreate=False,
    )


def test_conditional_edit_drops_stale_full_page_replacement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page = _install_page(monkeypatch, "concurrent edit")

    saved = worker.save_to_wiki(
        "alika",
        "obsolete content",
        "fanitsiana",
        "edit",
        expected_content_sha256=hashlib.sha256(b"original content").hexdigest(),
    )

    assert saved is False
    page.put.assert_not_called()


def test_conditional_edit_treats_deleted_page_as_stale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page = _install_page(monkeypatch, "unused")
    page.get.side_effect = worker.NoPage("page disappeared")

    saved = worker.save_to_wiki(
        "alika",
        "obsolete content",
        "fanitsiana",
        "edit",
        expected_content_sha256="a" * 64,
    )

    assert saved is False
    page.put.assert_not_called()


def test_conditional_edit_propagates_ambiguous_write_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page = _install_page(monkeypatch, "old content")
    exception_page = SimpleNamespace(
        title=lambda **_kwargs: "alika",
        site="mg.wiktionary",
    )
    page.put.side_effect = EditConflictError(exception_page)

    with pytest.raises(EditConflictError):
        worker.save_to_wiki(
            "alika",
            "new content",
            "fanitsiana",
            "edit",
            expected_content_sha256=hashlib.sha256(b"old content").hexdigest(),
        )


def test_save_preserves_leading_newline_and_minor_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page = _install_page(monkeypatch, "original content")

    worker.save_to_wiki(
        "alika",
        "\nexact content",
        "fanitsiana",
        "edit",
        minor=True,
    )

    page.put.assert_called_once_with(
        "\nexact content", "fanitsiana", force=True, minor=True
    )


def test_callback_forwards_the_standard_page_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    save = MagicMock(return_value=True)
    channel = MagicMock()
    method = SimpleNamespace(delivery_tag="delivery")
    expected_hash = hashlib.sha256(b"original content").hexdigest()
    monkeypatch.setattr(worker, "save_to_wiki", save)
    _disable_sleep(monkeypatch)

    worker.callback(
        channel,
        method,
        None,
        _message(expected_content_sha256=expected_hash),
    )

    save.assert_called_once_with(
        "alika",
        "new content",
        "fanitsiana famaritana",
        "edit",
        expected_content_sha256=expected_hash,
        minor=False,
    )
    channel.basic_ack.assert_called_once_with(delivery_tag="delivery")


@pytest.mark.parametrize(
    ("redelivered", "should_requeue"),
    [(False, True), (True, False)],
)
def test_callback_retries_a_save_failure_once(
    monkeypatch: pytest.MonkeyPatch,
    redelivered: bool,
    should_requeue: bool,
) -> None:
    channel = MagicMock()
    method = SimpleNamespace(delivery_tag="delivery", redelivered=redelivered)
    monkeypatch.setattr(
        worker,
        "save_to_wiki",
        MagicMock(side_effect=RuntimeError("temporary wiki failure")),
    )
    _disable_sleep(monkeypatch)

    worker.callback(channel, method, None, _message())

    channel.basic_nack.assert_called_once_with(
        delivery_tag="delivery", requeue=should_requeue
    )


def test_unicode_save_error_is_logged_with_latin1_process_locale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    channel = MagicMock()
    method = SimpleNamespace(delivery_tag="delivery", redelivered=False)
    output_bytes = io.BytesIO()
    output = io.TextIOWrapper(output_bytes, encoding="latin-1")
    monkeypatch.setattr(sys, "stdout", output)
    monkeypatch.setattr(
        sys,
        "stderr",
        io.TextIOWrapper(io.BytesIO(), encoding="latin-1"),
    )
    monkeypatch.setattr(
        worker,
        "save_to_wiki",
        MagicMock(side_effect=RuntimeError("temporary wiki failure")),
    )
    consume = MagicMock()
    monkeypatch.setattr(worker, "consume_wiki_messages", consume)
    _disable_sleep(monkeypatch)

    worker.main()
    worker.callback(channel, method, None, _message(page="tēst"))
    output.flush()

    consume.assert_called_once_with()
    assert "Error saving page tēst" in output_bytes.getvalue().decode("utf-8")
    channel.basic_nack.assert_called_once_with(
        delivery_tag="delivery", requeue=True
    )


def test_callback_preserves_edit_during_rate_limiter_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    channel = MagicMock()
    method = SimpleNamespace(delivery_tag="delivery", redelivered=True)
    monkeypatch.setattr(
        worker,
        "save_to_wiki",
        MagicMock(side_effect=WikimediaRateLimitError("Redis unavailable")),
    )
    _disable_sleep(monkeypatch)

    worker.callback(channel, method, None, _message())

    channel.basic_nack.assert_called_once_with(delivery_tag="delivery", requeue=True)


@pytest.mark.parametrize("body", [b"not-json", b"[]", _message(minor="false")])
def test_callback_discards_malformed_message(
    monkeypatch: pytest.MonkeyPatch, body: bytes
) -> None:
    channel = MagicMock()
    _disable_sleep(monkeypatch)

    worker.callback(channel, SimpleNamespace(delivery_tag="delivery"), None, body)

    channel.basic_nack.assert_called_once_with(
        delivery_tag="delivery", requeue=False
    )


def test_callback_discards_oversized_and_deep_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(worker, "MAX_QUEUED_WIKITEXT_MESSAGE_BYTES", 8)
    _disable_sleep(monkeypatch)
    channel = MagicMock()

    worker.callback(
        channel,
        SimpleNamespace(delivery_tag="large"),
        None,
        b'{"content":"too large"}',
    )
    monkeypatch.setattr(worker, "MAX_QUEUED_WIKITEXT_MESSAGE_BYTES", 16_384)
    worker.callback(
        channel,
        SimpleNamespace(delivery_tag="deep"),
        None,
        ("[" * 2_000 + "0" + "]" * 2_000).encode(),
    )

    assert channel.basic_nack.call_args_list == [
        call(delivery_tag="large", requeue=False),
        call(delivery_tag="deep", requeue=False),
    ]


def test_consumer_rejects_only_the_non_executable_review_queue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(worker, "PAGE_CHECK_REVIEW_QUEUE", "page-check-review")
    monkeypatch.setattr(worker, "CONSUMER_QUEUE", "page-check-review")

    with pytest.raises(ValueError, match="protected queue"):
        worker._validate_consumer_configuration()  # pylint: disable=protected-access

    monkeypatch.setattr(worker, "CONSUMER_QUEUE", "translated")
    worker._validate_consumer_configuration()  # pylint: disable=protected-access
