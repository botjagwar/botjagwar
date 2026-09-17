#!/usr/bin/env python3
"""Keep the English Wiktionary Redis page cache aligned with IRC changes."""

from __future__ import annotations

import logging
import random
import re
from dataclasses import dataclass
from queue import Empty, Full, Queue
from threading import Event, Lock, Thread, current_thread
from typing import Any, Callable, Literal

import irc.bot

from redis_wikicache import NoPage, RedisPage, RedisSite


LOGGER = logging.getLogger(__name__)
IRC_FORMATTING_RE = re.compile(
    r"\x03(?:\d{1,2}(?:,\d{1,2})?)?|[\x02\x0f\x16\x1d\x1f]"
)
ORIGIN_RE = re.compile(r"https?://([a-z-]+)\.wiktionary\.org/")
LOG_ACTION_RE = re.compile(r"^\[\[Special:Log/(delete|move)\]\]\s+(\S+)", re.IGNORECASE)
LINK_RE = re.compile(r"\[\[([^\[\]]+)\]\]")
CACHE_QUEUE_SIZE = 5000
CACHE_UPDATE_MAX_RETRIES = 5


@dataclass(frozen=True)
class CacheEvent:
    """Describe one ordered mutation to the English Wiktionary page cache."""

    action: Literal["edit", "delete", "move"]
    title: str
    new_title: str | None = None


def parse_cache_event(message: str) -> CacheEvent | None:
    """Parse one English Wiktionary IRC message into a supported cache event."""
    clean_message = IRC_FORMATTING_RE.sub("", message)
    origin = ORIGIN_RE.search(clean_message)
    if origin is None or origin.group(1).casefold() != "en":
        return None

    links = [title.strip() for title in LINK_RE.findall(clean_message)]
    if not links or not links[0]:
        raise ValueError("IRC recent change does not contain a page title.")

    log_action = LOG_ACTION_RE.match(clean_message)
    if log_action is None:
        if links[0].casefold().startswith("special:log/"):
            return None
        return CacheEvent("edit", links[0])

    log_type, action = (value.casefold() for value in log_action.groups())
    if action != log_type:
        return None
    if log_type == "delete":
        if len(links) < 2 or not links[1]:
            raise ValueError("IRC delete event does not contain the deleted page title.")
        return CacheEvent("delete", links[1])
    if len(links) < 3 or not links[1] or not links[2]:
        raise ValueError("IRC move event does not contain both page titles.")
    return CacheEvent("move", links[1], links[2])


class EnglishWiktionaryCache:
    """Apply English Wiktionary page changes to the local Redis cache."""

    def __init__(
        self,
        site: RedisSite | None = None,
        page_factory: Callable[[RedisSite, str], Any] = RedisPage,
    ) -> None:
        self.site = site or RedisSite("en", "wiktionary")
        self._page_factory = page_factory

    def apply(self, event: CacheEvent) -> None:
        """Apply one parsed event without mutating Wiktionary itself."""
        if event.action == "edit":
            self.refresh(event.title)
        elif event.action == "delete":
            self.delete(event.title)
        elif event.new_title is not None:
            self.move(event.title, event.new_title)

    def refresh(self, title: str) -> None:
        """Fetch current wikitext and create or replace its Redis value."""
        try:
            content = self._page_factory(self.site, title).get(force_refresh=True)
        except NoPage:
            # The page may have disappeared between its IRC event and this fetch.
            self.delete(title)
            return
        # RedisPage populates the cache, while this strict write ensures failures
        # reach the worker and are retried instead of being silently ignored.
        self.site.instance.set(self._key(title), content)

    def delete(self, title: str) -> None:
        """Remove one page from the Redis cache."""
        self.site.instance.delete(self._key(title))

    def move(self, old_title: str, new_title: str) -> None:
        """Rename a cached page, fetching the destination if the source is absent."""
        old_key = self._key(old_title)
        if self.site.instance.exists(old_key):
            self.site.instance.rename(old_key, self._key(new_title))
            return
        self.refresh(new_title)

    def _key(self, title: str) -> str:
        """Return the existing Redis key format for an English Wiktionary page."""
        return f"{self.site.wiki}.{self.site.language}/{title}"


class CacheUpdateWorker:
    """Apply cache events sequentially outside the IRC reactor thread."""

    def __init__(
        self,
        cache: EnglishWiktionaryCache,
        event_queue: Queue[CacheEvent] | None = None,
        stop_event: Event | None = None,
    ) -> None:
        self.cache = cache
        self.queue = event_queue or Queue(maxsize=CACHE_QUEUE_SIZE)
        self._stop_event = stop_event or Event()
        self._thread: Thread | None = None
        self._thread_lock = Lock()

    def enqueue(self, event: CacheEvent) -> bool:
        """Queue one event without blocking the IRC callback."""
        try:
            self.queue.put_nowait(event)
        except Full:
            LOGGER.error("English Wiktionary cache queue is full; dropping %r.", event)
            return False
        return True

    def start(self) -> None:
        """Start the cache consumer if it is not already running."""
        with self._thread_lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = Thread(
                target=self.run,
                name="english-wiktionary-cache",
                daemon=True,
            )
            self._thread.start()

    def stop(self, wait: bool = True) -> None:
        """Signal the cache consumer to stop and optionally wait for it."""
        self._stop_event.set()
        thread = self._thread
        if wait and thread is not None and thread.is_alive() and thread is not current_thread():
            thread.join(timeout=5)

    def run(self) -> None:
        """Consume queued events in IRC order with bounded transient retries."""
        while not self._stop_event.is_set():
            try:
                event = self.queue.get(timeout=0.25)
            except Empty:
                continue
            try:
                self._apply_with_retries(event)
            finally:
                self.queue.task_done()

    def _apply_with_retries(self, event: CacheEvent) -> bool:
        """Apply an event, retaining ordering while retrying failures."""
        for attempt in range(CACHE_UPDATE_MAX_RETRIES + 1):
            try:
                self.cache.apply(event)
                return True
            except Exception:  # pylint: disable=broad-exception-caught
                if attempt == CACHE_UPDATE_MAX_RETRIES:
                    LOGGER.exception(
                        "Dropping English Wiktionary cache event after %d retries: %r",
                        CACHE_UPDATE_MAX_RETRIES,
                        event,
                    )
                    return False
                delay = min(2**attempt, 30)
                LOGGER.warning(
                    "Retrying English Wiktionary cache event in %d seconds: %r",
                    delay,
                    event,
                    exc_info=True,
                )
                if self._stop_event.wait(delay):
                    return False
        return False


class EnglishWiktionaryCacheBot(irc.bot.SingleServerIRCBot):
    """Subscribe only to English Wiktionary and enqueue supported cache changes."""

    recent_change_server = ("irc.wikimedia.org", 6667)
    channel = "#en.wiktionary"

    def __init__(
        self,
        cache: EnglishWiktionaryCache | None = None,
        event_queue: Queue[CacheEvent] | None = None,
        nick_prefix: str = "botjagwar-cache",
    ) -> None:
        suffix = random.randint(36**3, 36**4 - 1)
        nickname = f"{nick_prefix}-{suffix:x}"
        super().__init__(
            [self.recent_change_server],
            nickname,
            "Bot-Jagwar English Wiktionary cache monitor.",
        )
        self.worker = CacheUpdateWorker(
            cache or EnglishWiktionaryCache(),
            event_queue=event_queue,
        )
        self.errors = 0

    def on_welcome(self, server: Any, _event: Any) -> None:
        """Join the English Wiktionary recent-changes channel."""
        server.join(self.channel)

    def on_kick(self, server: Any, event: Any) -> None:
        """Rejoin the English Wiktionary channel after a kick."""
        self.on_welcome(server, event)

    def on_pubmsg(self, _server: Any, event: Any) -> None:
        """Parse and enqueue one recent change without network or Redis I/O."""
        try:
            if not getattr(event, "arguments", None):
                raise ValueError("IRC event has no message body.")
            message = event.arguments[0]
            if not isinstance(message, str):
                raise ValueError("IRC event message must be text.")
            cache_event = parse_cache_event(message)
            if cache_event is not None and not self.worker.enqueue(cache_event):
                self.errors += 1
        except Exception:  # pylint: disable=broad-exception-caught
            self.errors += 1
            LOGGER.exception("Unable to process English Wiktionary IRC event.")

    def die(self, msg: str = "Bye") -> None:
        """Stop the cache worker before disconnecting from IRC."""
        self.worker.stop(wait=False)
        super().die(msg)


def main() -> None:
    """Run the English Wiktionary cache monitor until it is stopped."""
    logging.basicConfig(level=logging.INFO)
    bot = EnglishWiktionaryCacheBot()
    bot.worker.start()
    try:
        bot.start()
    except KeyboardInterrupt:
        bot.die()
    finally:
        bot.worker.stop(wait=False)


if __name__ == "__main__":
    main()
