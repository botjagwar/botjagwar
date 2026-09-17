"""Tests for recent-change messages consumed from RabbitMQ."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

import rabbitmq_entry_translator as feeder
from redis_wikicache import NoPage


class FakeResponse:
    """Provide the asynchronous response protocol used by the feeder."""

    def __init__(self, data: dict[str, Any], status: int = 200) -> None:
        self.data = data
        self.status = status

    async def __aenter__(self) -> "FakeResponse":
        return self

    async def __aexit__(self, *_args: Any) -> None:
        return None

    async def json(self) -> dict[str, Any]:
        return self.data


class FakeSession:
    """Return configured queue depths and capture the submitted translation."""

    def __init__(self, job_counts: list[int]) -> None:
        self.job_counts = job_counts
        self.get_urls: list[str] = []
        self.posts: list[tuple[str, dict[str, Any]]] = []

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, *_args: Any) -> None:
        return None

    def get(self, url: str) -> FakeResponse:
        self.get_urls.append(url)
        return FakeResponse({"jobs": self.job_counts.pop(0)})

    def post(self, url: str, json: dict[str, Any]) -> FakeResponse:
        self.posts.append((url, json))
        return FakeResponse({"status": "queued"})


def delete_log(title: str, action: str = "delete", closed_link: bool = True) -> str:
    """Build the legacy color-coded log title found in the edit2 queue."""
    link_end = "\x0310]]\": reason" if closed_link else ""
    return (
        "Special:Log/delete\x0314]]"
        f"\x034 {action}\x0310 \x0302\x03 \x035*\x03 "
        "\x0303Administrator\x03 \x035*\x03  \x0310deleted \""
        f"[[\x0302{title}{link_end}"
    )


@pytest.mark.parametrize("closed_link", [True, False])
def test_extract_deleted_page_title_from_broker_log(closed_link: bool) -> None:
    """Formatting and the producer's occasionally-truncated link are accepted."""
    assert feeder.extract_deleted_page_title(
        delete_log("trano fonenana", closed_link=closed_link)
    ) == "trano fonenana"


@pytest.mark.parametrize("action", ["revision", "restore", "delete_redir"])
def test_extract_deleted_page_title_rejects_other_delete_log_actions(
    action: str,
) -> None:
    """Revision suppression, restoration and redirect overwrite are not deletion."""
    assert feeder.extract_deleted_page_title(delete_log("alika", action=action)) is None


def test_mark_page_for_deletion_updates_an_existing_malagasy_page() -> None:
    """An existing live page receives one standard deletion marker."""
    page = MagicMock()
    page.exists.return_value = True
    page.get.return_value = "=={{=en=}}==\ncontent"

    updated = feeder.mark_page_for_deletion("alika", lambda _title: page)

    assert updated is True
    page.get.assert_called_once_with(force_refresh=True)
    page.put.assert_called_once_with(
        "{{fafao}}\n\n=={{=en=}}==\ncontent",
        feeder.DELETE_SUMMARY,
        force=True,
        minor=False,
        nocreate=True,
    )


def test_mark_page_for_deletion_ignores_a_missing_malagasy_page() -> None:
    """A source deletion must never create a missing Malagasy page."""
    page = MagicMock()
    page.exists.return_value = False

    updated = feeder.mark_page_for_deletion("tsy-misy", lambda _title: page)

    assert updated is False
    page.get.assert_not_called()
    page.put.assert_not_called()


def test_mark_page_for_deletion_handles_a_stale_exists_result() -> None:
    """A forced live read prevents a stale cache hit from causing page creation."""
    page = MagicMock()
    page.exists.return_value = True
    page.get.side_effect = NoPage("missing")

    updated = feeder.mark_page_for_deletion("tsy-misy", lambda _title: page)

    assert updated is False
    page.put.assert_not_called()


def test_mark_page_for_deletion_is_idempotent() -> None:
    """An existing active deletion template is not duplicated."""
    page = MagicMock()
    page.exists.return_value = True
    page.get.return_value = "{{fafao|reason}}\ncontent"

    updated = feeder.mark_page_for_deletion("alika", lambda _title: page)

    assert updated is False
    page.put.assert_not_called()


def test_mark_page_for_deletion_does_not_treat_translation_d_as_delete() -> None:
    """The Malagasy translation template d does not suppress the deletion marker."""
    page = MagicMock()
    page.exists.return_value = True
    page.get.return_value = "{{d|en|dog}}\ncontent"

    updated = feeder.mark_page_for_deletion("alika", lambda _title: page)

    assert updated is True
    page.put.assert_called_once()


def test_delete_log_is_marked_without_translation_or_random_delay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The consumer diverts deletion logs before entering the translation path."""
    page = MagicMock()
    page.exists.return_value = True
    page.get.return_value = "content"
    monkeypatch.setattr(feeder, "RabbitMqConsumer", MagicMock())
    run = MagicMock()
    monkeypatch.setattr(feeder.asyncio, "run", run)
    client = feeder.SimpleEntryTranslatorClientFeeder(page_factory=lambda _title: page)

    client.on_page_edit(site="fr", title=delete_log("alika"))

    page.put.assert_called_once()
    run.assert_not_called()


def test_non_delete_action_in_deletion_log_is_ignored_without_translation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deletion-log actions without a deleted page are not translated."""
    monkeypatch.setattr(feeder, "RabbitMqConsumer", MagicMock())
    run = MagicMock()
    monkeypatch.setattr(feeder.asyncio, "run", run)
    client = feeder.SimpleEntryTranslatorClientFeeder()

    client.on_page_edit(title="Special:Log/delete\x0314]]\x034 revision\x0310")

    run.assert_not_called()


def test_translation_backoff_applies_only_above_thirty_jobs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Queue depth 30 proceeds, while a larger queue waits two seconds."""
    session = FakeSession([31, 30])
    monkeypatch.setattr(
        feeder.aiohttp,
        "ClientSession",
        lambda **_kwargs: session,
    )
    sleep = AsyncMock()
    monkeypatch.setattr(feeder.asyncio, "sleep", sleep)

    asyncio.run(
        feeder.SimpleEntryTranslatorClientFeeder.on_page_edit_async(
            context=SimpleNamespace(host="localhost", port=8000),
            site="en",
            title="word",
        )
    )

    assert session.get_urls == [
        "http://localhost:8000/jobs",
        "http://localhost:8000/jobs",
    ]
    sleep.assert_awaited_once_with(2)
    assert session.posts == [
        ("http://localhost:8000/wiktionary-pages/en/jobs", {"title": "word"})
    ]
