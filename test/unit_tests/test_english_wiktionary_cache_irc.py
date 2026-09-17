"""Offline tests for the English Wiktionary IRC cache monitor."""

from __future__ import annotations

from queue import Queue
from types import SimpleNamespace
from typing import Any

import pytest

from english_wiktionary_cache_irc import (
    CacheEvent,
    CacheUpdateWorker,
    EnglishWiktionaryCache,
    EnglishWiktionaryCacheBot,
    parse_cache_event,
)
from redis_wikicache import NoPage


def irc_edit(title: str, language: str = "en") -> str:
    """Build a representative formatted page-edit event."""
    return (
        f"\x0314[[\x0307{title}\x0314]]\x034 M\x0310 "
        f"https://{language}.wiktionary.org/w/index.php?diff=2&oldid=1 "
        "\x035*\x03 \x0303Editor\x03 \x035*\x03 (+12) update"
    )


def irc_log(log_type: str, action: str, details: str) -> str:
    """Build a representative English Wiktionary log event."""
    return (
        f"[[Special:Log/{log_type}]] {action} "
        "https://en.wiktionary.org/wiki/Special:Log "
        f"* Administrator * {details}"
    )


class FakeRedis:
    """Implement the Redis page operations used by the cache synchronizer."""

    def __init__(self, values: dict[str, str] | None = None) -> None:
        self.values = values or {}

    def set(self, key: str, value: str) -> None:
        """Create or replace one value."""
        self.values[key] = value

    def delete(self, key: str) -> None:
        """Delete one value if present."""
        self.values.pop(key, None)

    def exists(self, key: str) -> bool:
        """Return whether a value exists."""
        return key in self.values

    def rename(self, old_key: str, new_key: str) -> None:
        """Atomically move one value in the fake keyspace."""
        self.values[new_key] = self.values.pop(old_key)


class FakePage:
    """Return configured current wikitext without network access."""

    def __init__(self, _site: Any, title: str, pages: dict[str, str]) -> None:
        self.title = title
        self.pages = pages

    def get(self, force_refresh: bool = False) -> str:
        """Return current text or model a page that no longer exists."""
        assert force_refresh is True
        if self.title not in self.pages:
            raise NoPage(self.title)
        return self.pages[self.title]


def build_cache(
    redis_client: FakeRedis,
    pages: dict[str, str],
) -> EnglishWiktionaryCache:
    """Build a synchronizer with local Redis and Wiktionary doubles."""
    site = SimpleNamespace(
        wiki="wiktionary",
        language="en",
        instance=redis_client,
    )
    return EnglishWiktionaryCache(
        site=site,  # type: ignore[arg-type]
        page_factory=lambda fake_site, title: FakePage(fake_site, title, pages),
    )


def test_parser_classifies_edits_deletes_and_moves() -> None:
    """Supported English events retain their exact source and destination titles."""
    assert parse_cache_event(irc_edit("new entry")) == CacheEvent("edit", "new entry")
    assert parse_cache_event(
        irc_log("delete", "delete", 'deleted page "[[obsolete entry]]": reason')
    ) == CacheEvent("delete", "obsolete entry")
    assert parse_cache_event(
        irc_log("move", "move", "moved [[old title]] to [[new title]]: reason")
    ) == CacheEvent("move", "old title", "new title")


def test_parser_ignores_other_wikis_and_unsupported_log_actions() -> None:
    """Only English page changes requested by the cache contract are emitted."""
    assert parse_cache_event(irc_edit("maison", language="fr")) is None
    assert (
        parse_cache_event(
            irc_log("delete", "restore", "restored page [[restored entry]]")
        )
        is None
    )


def test_edit_refreshes_existing_and_new_cached_pages() -> None:
    """Edit events strictly replace stale text and create missing Redis keys."""
    redis_client = FakeRedis({"wiktionary.en/existing": "stale"})
    cache = build_cache(
        redis_client,
        {"existing": "current", "created": "new page text"},
    )

    cache.apply(CacheEvent("edit", "existing"))
    cache.apply(CacheEvent("edit", "created"))

    assert redis_client.values == {
        "wiktionary.en/existing": "current",
        "wiktionary.en/created": "new page text",
    }


def test_page_missing_during_edit_refresh_is_removed() -> None:
    """A delete racing an earlier edit cannot leave stale cached text behind."""
    redis_client = FakeRedis({"wiktionary.en/gone": "stale"})
    cache = build_cache(redis_client, {})

    cache.apply(CacheEvent("edit", "gone"))

    assert redis_client.values == {}


def test_delete_removes_page_from_cache() -> None:
    """Delete events evict exactly the corresponding English page key."""
    redis_client = FakeRedis(
        {
            "wiktionary.en/deleted": "old",
            "wiktionary.en/retained": "keep",
        }
    )
    cache = build_cache(redis_client, {})

    cache.apply(CacheEvent("delete", "deleted"))

    assert redis_client.values == {"wiktionary.en/retained": "keep"}


def test_move_renames_cached_page_key() -> None:
    """Move events preserve content while atomically replacing the page name."""
    redis_client = FakeRedis({"wiktionary.en/old": "page text"})
    cache = build_cache(redis_client, {})

    cache.apply(CacheEvent("move", "old", "new"))

    assert redis_client.values == {"wiktionary.en/new": "page text"}


def test_move_fetches_destination_when_source_was_not_cached() -> None:
    """A partial cache still gains the destination page after a move event."""
    redis_client = FakeRedis()
    cache = build_cache(redis_client, {"new": "current text"})

    cache.apply(CacheEvent("move", "old", "new"))

    assert redis_client.values == {"wiktionary.en/new": "current text"}


def test_worker_retries_in_place_before_processing_the_next_event() -> None:
    """Transient failures cannot reorder a later mutation ahead of an earlier one."""
    calls: list[CacheEvent] = []

    class FlakyCache:
        """Fail the first application only."""

        def apply(self, event: CacheEvent) -> None:
            calls.append(event)
            if len(calls) == 1:
                raise RuntimeError("temporary failure")

    stop_event = SimpleNamespace(wait=lambda _delay: False)
    worker = CacheUpdateWorker(
        FlakyCache(),  # type: ignore[arg-type]
        stop_event=stop_event,  # type: ignore[arg-type]
    )
    event = CacheEvent("edit", "entry")

    assert worker._apply_with_retries(event) is True
    assert calls == [event, event]


def test_bot_joins_only_english_and_queues_without_cache_io() -> None:
    """The IRC callback delegates an English edit to its dedicated worker."""
    events: Queue[CacheEvent] = Queue()
    cache = build_cache(FakeRedis(), {})
    bot = EnglishWiktionaryCacheBot(cache=cache, event_queue=events)
    server = SimpleNamespace(joined=[], join=lambda channel: server.joined.append(channel))

    bot.on_welcome(server, None)
    bot.on_pubmsg(None, SimpleNamespace(arguments=[irc_edit("entry")]))

    assert server.joined == ["#en.wiktionary"]
    assert events.get_nowait() == CacheEvent("edit", "entry")
    assert bot.errors == 0


@pytest.mark.parametrize(
    "message",
    [
        irc_log("delete", "delete", "deleted a revision"),
        irc_log("move", "move", "move details unavailable"),
    ],
)
def test_malformed_supported_log_events_are_rejected(message: str) -> None:
    """Incomplete destructive events cannot target a guessed cache key."""
    with pytest.raises(ValueError):
        parse_cache_event(message)
