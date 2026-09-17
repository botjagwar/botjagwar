#!/usr/bin/python3
"""Consume Wiktionary recent changes and automate selected page checks."""

import logging as log
import random
import re
import time
import uuid
from queue import Empty, Full, Queue
from threading import Event, Lock, Thread, current_thread
from typing import Any, Callable, Optional, Protocol

import irc.bot
import requests
from requests import Response

from api.services.page_checker_settings import (
    PageCheckerSettings,
    PageCheckerSettingsStore,
    PageCheckerSettingsStoreError,
    normalize_username,
)
from api.servicemanager import EntryTranslatorServiceManager

log.basicConfig(filename="/opt/botjagwar/user_data/wiktionary_irc.log", level=log.DEBUG)
PAGE_CHECK_LANGUAGE = "mg"
PAGE_CHECK_QUEUE_SIZE = 1000
PAGE_CHECK_MAX_RETRIES = 5
SOURCE_TRANSLATION_QUEUE_SIZE = 1000
SOURCE_TRANSLATION_MAX_RETRIES = 5
SETTINGS_REFRESH_INTERVAL_SECONDS = 1.0
IRC_FORMATTING_RE = re.compile(r"\x03(?:\d{1,2}(?:,\d{1,2})?)?|[\x02\x0f\x16\x1d\x1f]")


class TranslatorManager(Protocol):  # pylint: disable=too-few-public-methods
    """Describe the HTTP methods used by the IRC listener and worker."""

    def post_once(self, route: str, **kwargs: Any) -> Response:
        """Send one POST request without transparent retries."""


class PageCheckerSettingsCache:
    """Provide non-blocking settings snapshots to the IRC event callback."""

    def __init__(self, loader: Callable[[], PageCheckerSettings]) -> None:
        """Initialize the cache with safe defaults and an authoritative loader."""
        self._loader = loader
        self._settings = PageCheckerSettings(
            watched_users=(),
            check_probability=0,
        )
        self._lock = Lock()
        self._load_failed = False

    def get(self) -> PageCheckerSettings:
        """Return the latest successful settings snapshot without I/O."""
        with self._lock:
            return self._settings

    def refresh(self) -> PageCheckerSettings:
        """Refresh from Redis, retaining the latest snapshot on failure."""
        try:
            settings = self._loader()
        except PageCheckerSettingsStoreError as error:
            with self._lock:
                if not self._load_failed:
                    log.warning("Unable to refresh page-checker settings: %s", error)
                self._load_failed = True
                return self._settings
        with self._lock:
            self._settings = settings
            self._load_failed = False
            return settings


class PageCheckQueueWorker:  # pylint: disable=too-many-instance-attributes
    """Submit queued page checks without blocking the IRC event callback."""

    def __init__(  # pylint: disable=too-many-arguments
        self,
        manager: TranslatorManager,
        settings_provider: Callable[[], PageCheckerSettings],
        page_queue: Optional[Queue[str]] = None,
        stop_event: Optional[Event] = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Initialize the worker with injectable queue, settings and timing."""
        self._manager = manager
        self._settings_provider = settings_provider
        self._queue = page_queue or Queue(maxsize=PAGE_CHECK_QUEUE_SIZE)
        self._stop_event = stop_event or Event()
        self._clock = clock
        self._last_submission_at: Optional[float] = None
        self._thread: Optional[Thread] = None
        self._thread_lock = Lock()
        self._queue_lock = Lock()
        self._queued_titles: set[str] = set()
        self._retry_counts: dict[str, int] = {}

    @property
    def queue(self) -> Queue[str]:
        """Return the page queue for diagnostics and deterministic tests."""
        return self._queue

    def enqueue(self, title: str) -> bool:
        """Add a unique title, returning false only when the queue is full."""
        with self._queue_lock:
            if title in self._queued_titles:
                return True
            try:
                self._queue.put_nowait(title)
            except Full:
                log.error("Page-check queue is full; dropping '%s'.", title)
                return False
            self._queued_titles.add(title)
        return True

    def start(self) -> None:
        """Start the single queue consumer if it is not already running."""
        with self._thread_lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = Thread(
                target=self.run,
                name="page-check-queue",
                daemon=True,
            )
            self._thread.start()

    def stop(self, wait: bool = True) -> None:
        """Signal the queue consumer to stop and optionally wait briefly for it."""
        self._stop_event.set()
        thread = self._thread
        if (
            wait
            and thread is not None
            and thread.is_alive()
            and thread is not current_thread()
        ):
            thread.join(timeout=5)

    def run(self) -> None:
        """Consume queued titles until shutdown is requested."""
        next_settings_refresh = 0.0
        while not self._stop_event.is_set():
            now = self._clock()
            if now >= next_settings_refresh:
                try:
                    self._settings_provider()
                except PageCheckerSettingsStoreError as error:
                    log.warning("Unable to refresh page-checker settings: %s", error)
                next_settings_refresh = now + SETTINGS_REFRESH_INTERVAL_SECONDS
            try:
                title = self._queue.get(timeout=0.25)
            except Empty:
                continue
            retry_scheduled = False
            try:
                self._submit(title)
            except (
                RetryablePageCheckError,
                PageCheckerSettingsStoreError,
                requests.ConnectionError,
            ) as error:
                retry_scheduled = self._retry(title, error)
            except Exception:  # pylint: disable=broad-exception-caught
                log.exception("Unable to queue automated page check for '%s'.", title)
            finally:
                if not retry_scheduled:
                    with self._queue_lock:
                        self._queued_titles.discard(title)
                        self._retry_counts.pop(title, None)
                self._queue.task_done()

    def _retry(self, title: str, error: Exception) -> bool:
        """Requeue an explicitly transient failure up to the bounded retry limit."""
        with self._queue_lock:
            attempts = self._retry_counts.get(title, 0) + 1
            if attempts > PAGE_CHECK_MAX_RETRIES:
                log.error(
                    "Dropping page check for '%s' after %d retries: %s",
                    title,
                    PAGE_CHECK_MAX_RETRIES,
                    error,
                )
                return False
            self._retry_counts[title] = attempts
        retry_delay = min(2 ** (attempts - 1), 30)
        if self._stop_event.wait(retry_delay):
            return False
        with self._queue_lock:
            try:
                self._queue.put_nowait(title)
            except Full:
                log.error("Page-check queue is full; cannot retry '%s'.", title)
                return False
        log.warning(
            "Retrying page check for '%s' after %d seconds (%d/%d): %s",
            title,
            retry_delay,
            attempts,
            PAGE_CHECK_MAX_RETRIES,
            error,
        )
        return True

    def _submit(self, title: str) -> bool:
        """Wait for the configured cooldown and submit one asynchronous check."""
        settings = self._settings_provider()
        while self._last_submission_at is not None:
            elapsed = self._clock() - self._last_submission_at
            remaining = max(0.0, float(settings.cooldown_seconds) - elapsed)
            if remaining <= 0:
                break
            wait_seconds = min(remaining, SETTINGS_REFRESH_INTERVAL_SECONDS)
            if self._stop_event.wait(wait_seconds):
                return False
            settings = self._settings_provider()
        if self._stop_event.is_set():
            return False

        self._last_submission_at = self._clock()
        response = self._manager.post_once(
            f"wiktionary-pages/{PAGE_CHECK_LANGUAGE}/check-jobs",
            json={"titles": [title]},
        )
        handle_page_check_response(response)
        log.info("Queued automated page check for '%s'.", title)
        return True


class SourceTranslationQueueWorker:  # pylint: disable=too-many-instance-attributes
    """Submit source translations without blocking the IRC event callback."""

    def __init__(  # pylint: disable=too-many-arguments
        self,
        manager: TranslatorManager,
        translation_queue: Optional[Queue[tuple[str, str]]] = None,
        stop_event: Optional[Event] = None,
        accepted_callback: Optional[Callable[[str, str], None]] = None,
        failure_callback: Optional[Callable[[str, str], None]] = None,
        request_id_factory: Callable[[], str] = lambda: str(uuid.uuid4()),
    ) -> None:
        """Initialize the worker with injectable queue and lifecycle hooks."""
        self._manager = manager
        self._queue = translation_queue or Queue(
            maxsize=SOURCE_TRANSLATION_QUEUE_SIZE
        )
        self._stop_event = stop_event or Event()
        self._accepted_callback = accepted_callback
        self._failure_callback = failure_callback
        self._request_id_factory = request_id_factory
        self._thread: Optional[Thread] = None
        self._thread_lock = Lock()
        self._queue_lock = Lock()
        self._queued_pages: set[tuple[str, str]] = set()
        self._retry_counts: dict[tuple[str, str], int] = {}
        self._request_ids: dict[tuple[str, str], str] = {}

    @property
    def queue(self) -> Queue[tuple[str, str]]:
        """Return the translation queue for diagnostics and deterministic tests."""
        return self._queue

    def enqueue(self, language: str, title: str) -> bool:
        """Add one exact source page, returning false when the queue is full."""
        page = (language, title)
        with self._queue_lock:
            if page in self._queued_pages:
                return True
            self._queued_pages.add(page)
            self._request_ids[page] = self._request_id_factory()
            try:
                self._queue.put_nowait(page)
            except Full:
                self._queued_pages.discard(page)
                self._request_ids.pop(page, None)
                log.error(
                    "Source-translation queue is full; dropping '%s:%s'.",
                    language,
                    title,
                )
                return False
        return True

    def start(self) -> None:
        """Start the single queue consumer if it is not already running."""
        with self._thread_lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = Thread(
                target=self.run,
                name="source-translation-queue",
                daemon=True,
            )
            self._thread.start()

    def stop(self, wait: bool = True) -> None:
        """Signal the queue consumer to stop and optionally wait briefly for it."""
        self._stop_event.set()
        thread = self._thread
        if (
            wait
            and thread is not None
            and thread.is_alive()
            and thread is not current_thread()
        ):
            thread.join(timeout=5)

    def run(self) -> None:
        """Consume queued source pages until shutdown is requested."""
        while not self._stop_event.is_set():
            try:
                page = self._queue.get(timeout=0.25)
            except Empty:
                continue
            retry_scheduled = False
            failed = False
            try:
                self._submit(*page)
            except (
                RetryableSourceTranslationError,
                requests.ConnectionError,
            ) as error:
                retry_scheduled = self._retry(page, error)
                failed = not retry_scheduled and not self._stop_event.is_set()
            except Exception:  # pylint: disable=broad-exception-caught
                log.exception(
                    "Unable to queue source translation for '%s:%s'.", *page
                )
                failed = True
            else:
                self._notify(self._accepted_callback, page)
            finally:
                if not retry_scheduled:
                    with self._queue_lock:
                        self._queued_pages.discard(page)
                        self._retry_counts.pop(page, None)
                        self._request_ids.pop(page, None)
                if failed:
                    self._notify(self._failure_callback, page)
                self._queue.task_done()

    def _retry(
        self,
        page: tuple[str, str],
        error: Exception,
    ) -> bool:
        """Requeue an explicitly transient failure up to the retry limit."""
        with self._queue_lock:
            attempts = self._retry_counts.get(page, 0) + 1
            if attempts > SOURCE_TRANSLATION_MAX_RETRIES:
                log.error(
                    "Dropping source translation for '%s:%s' after %d retries: %s",
                    *page,
                    SOURCE_TRANSLATION_MAX_RETRIES,
                    error,
                )
                return False
            self._retry_counts[page] = attempts
        retry_after = getattr(error, "retry_after_seconds", None)
        retry_delay = (
            retry_after
            if isinstance(retry_after, int) and retry_after >= 0
            else min(2 ** (attempts - 1), 30)
        )
        if self._stop_event.wait(retry_delay):
            return False
        with self._queue_lock:
            try:
                self._queue.put_nowait(page)
            except Full:
                log.error(
                    "Source-translation queue is full; cannot retry '%s:%s'.",
                    *page,
                )
                return False
        log.warning(
            "Retrying source translation for '%s:%s' after %d seconds (%d/%d): %s",
            *page,
            retry_delay,
            attempts,
            SOURCE_TRANSLATION_MAX_RETRIES,
            error,
        )
        return True

    def _submit(self, language: str, title: str) -> bool:
        """Submit one asynchronous translation and accept its job record."""
        page = (language, title)
        with self._queue_lock:
            request_id = self._request_ids.get(page)
            if request_id is None:
                request_id = self._request_id_factory()
                self._request_ids[page] = request_id
        response = self._manager.post_once(
            f"wiktionary-pages/{language}/jobs",
            json={"title": title, "request_id": request_id},
        )
        job = handle_translation_response(response)
        log.info(
            "Queued source translation for '%s:%s' as job '%s' (%s).",
            language,
            title,
            job["job_id"],
            job["status"],
        )
        return True

    @staticmethod
    def _notify(
        callback: Optional[Callable[[str, str], None]],
        page: tuple[str, str],
    ) -> None:
        """Run a diagnostic callback without terminating the queue consumer."""
        if callback is None:
            return
        try:
            callback(*page)
        except Exception:  # pylint: disable=broad-exception-caught
            log.exception(
                "Unable to record source-translation diagnostics for '%s:%s'.",
                *page,
            )


def irc_retrieve() -> None:
    """Run the recent-changes bot and its background queue consumers."""
    wiktionary_bot = WiktionaryRecentChangesBot()
    try:
        wiktionary_bot.page_check_worker.start()
        wiktionary_bot.source_translation_worker.start()
        while True:
            try:
                wiktionary_bot.start()
            except KeyboardInterrupt:
                wiktionary_bot.die()
                break
    finally:
        wiktionary_bot.page_check_worker.stop(wait=False)
        wiktionary_bot.source_translation_worker.stop(wait=False)


class IrcBotException(Exception):
    """Raised when a recent-change event or API response is invalid."""


class RetryablePageCheckError(IrcBotException):
    """Raised when a page-check submission should be retried from the queue."""


class RetryableSourceTranslationError(IrcBotException):
    """Raised when a source-translation submission may be retried."""

    def __init__(
        self,
        message: str,
        retry_after_seconds: Optional[int] = None,
    ) -> None:
        """Record an optional server-requested delay for the next attempt."""
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


def _get_retry_after_seconds(response: Response) -> Optional[int]:
    """Return a non-negative integer Retry-After delay when supplied."""
    value = response.headers.get("Retry-After")
    if value is None:
        return None
    try:
        delay = int(value)
    except (TypeError, ValueError):
        return None
    return delay if delay >= 0 else None


def handle_translation_response(response: Response) -> dict[str, Any]:
    """Validate one accepted asynchronous source-translation job."""
    try:
        data = response.json()
    except ValueError as exc:
        if response.status_code == 429 or 500 <= response.status_code < 600:
            raise RetryableSourceTranslationError(
                f"Source-translation API returned HTTP {response.status_code}.",
                _get_retry_after_seconds(response),
            ) from exc
        raise IrcBotException(
            "Source-translation API returned invalid JSON."
        ) from exc

    if response.status_code == 429 or 500 <= response.status_code < 600:
        raise RetryableSourceTranslationError(
            str(data),
            _get_retry_after_seconds(response),
        )
    if response.status_code != 202:
        raise IrcBotException(str(data))
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("job_id"), str)
        or not data["job_id"]
        or not isinstance(data.get("status"), str)
        or not data["status"]
    ):
        raise IrcBotException(
            "Source-translation API returned an invalid job response."
        )
    return data


def handle_page_check_response(response: Response) -> None:
    """Raise when the asynchronous page-check API rejects a submission."""
    try:
        data = response.json()
    except ValueError as exc:
        if response.status_code == 429 or response.status_code >= 500:
            raise RetryablePageCheckError(
                f"Page-check API returned HTTP {response.status_code}."
            ) from exc
        raise IrcBotException("Page-check API returned invalid JSON.") from exc
    if response.status_code == 429 or response.status_code >= 500:
        raise RetryablePageCheckError(str(data))
    if response.status_code >= 400:
        raise IrcBotException(str(data))
    if not isinstance(data, dict) or not isinstance(data.get("jobs"), list):
        raise IrcBotException("Page-check API returned an invalid job response.")


class WiktionaryRecentChangesBot(  # pylint: disable=too-many-instance-attributes
    irc.bot.SingleServerIRCBot
):
    """Track source-wiki edits and sampled Malagasy bot edits."""

    recent_change_server = ("irc.wikimedia.org", 6667)

    def __init__(  # pylint: disable=too-many-arguments
        self,
        nick_prefix: str = "botjagwar",
        entry_translator_manager: Optional[TranslatorManager] = None,
        settings_store: Optional[PageCheckerSettingsStore] = None,
        random_value: Callable[[], float] = random.random,
        page_queue: Optional[Queue[str]] = None,
        source_translation_queue: Optional[Queue[tuple[str, str]]] = None,
    ) -> None:
        """Initialize IRC, settings and queue dependencies without connecting."""
        nick_suffix = f"-{base36encode(random.randint(36**3, 36**4 - 1))}"
        user = nick_prefix + nick_suffix
        super().__init__(
            [self.recent_change_server],
            user,
            "Bot-Jagwar [IRCbot v2].",
        )

        self.chronometer = 0.0
        self.langs = [PAGE_CHECK_LANGUAGE]
        self.sitename = "wiktionary"
        self.joined = [
            f"#{language}.{self.sitename}" for language in self.langs
        ]
        self.stats = {"edits": 0.0, "newentries": 0.0, "errors": 0.0}
        self.edits = 0
        self.username = user
        self.entry_translator_manager = (
            entry_translator_manager or EntryTranslatorServiceManager()
        )
        self.settings_store = settings_store or PageCheckerSettingsStore()
        self._settings_cache = PageCheckerSettingsCache(self.settings_store.get)
        self._settings_cache.refresh()
        self._random_value = random_value
        self.page_check_worker = PageCheckQueueWorker(
            self.entry_translator_manager,
            self._settings_cache.refresh,
            page_queue=page_queue,
        )
        self.source_translation_worker = SourceTranslationQueueWorker(
            self.entry_translator_manager,
            translation_queue=source_translation_queue,
            accepted_callback=self._record_translation_accepted,
            failure_callback=self._record_translation_failure,
        )
        self.connect_in_languages()

    def connect_in_languages(self) -> None:
        """Log the Wikimedia IRC channels that will be joined on welcome."""
        print("\n---------------------\nIRC BOT PAREMETERS : ")
        for channel in self.joined:
            print(("Channel:", channel, " Nickname:", self.username))
        print("Connection complete")

    def do_join(self, server: Any, _events: Any) -> None:
        """Join every configured recent-changes channel."""
        for channel in self.joined:
            server.join(channel)

    def on_welcome(self, server: Any, events: Any) -> None:
        """Join channels after the IRC server accepts the connection."""
        self.do_join(server, events)

    def on_kick(self, server: Any, events: Any) -> None:
        """Rejoin configured channels after a kick."""
        self.do_join(server, events)

    def on_pubmsg(self, _server: Any, events: Any) -> None:
        """Handle one recent-change message without running a page check inline."""
        try:
            message = _prepare_message(events)
            language = _get_origin_wiki(message)
            if language == PAGE_CHECK_LANGUAGE:
                self._consider_page_check(message)
            elif language in {"en", "fr"}:
                self._translate_source_edit(message)
        except Exception as error:  # pylint: disable=broad-exception-caught
            log.exception("Unable to process IRC recent change: %s", error)
            self.stats["errors"] += 1

    def _consider_page_check(self, message: str) -> None:
        """Sample a watched Malagasy edit and enqueue its title when selected."""
        if _get_message_type(message) != "edit":
            return
        editor = _get_user(message)
        if editor is None:
            return
        settings = self._settings_cache.get()
        watched_users = {
            normalize_username(username) for username in settings.watched_users
        }
        if normalize_username(editor) not in watched_users:
            return
        title = _get_pagename(message)
        if (
            ":" in title
            or _get_edit_summary(message) in settings.ignored_edit_summaries
        ):
            return
        probability = float(settings.check_probability) / 100.0
        if probability <= 0:
            return
        if probability < 1 and self._random_value() >= probability:
            return
        if not self.page_check_worker.enqueue(title):
            self.stats["errors"] += 1

    def _translate_source_edit(self, message: str) -> None:
        """Queue an English or French source edit without performing HTTP."""
        language = _get_origin_wiki(message)
        title = _get_pagename(message)
        if not self.source_translation_worker.enqueue(language, title):
            self.stats["errors"] += 1

    def _record_translation_accepted(self, _language: str, _title: str) -> None:
        """Update the existing source-translation throughput diagnostics."""
        current_time = time.time()
        self.edits += 1
        if not self.edits % 5:
            throughput = 60.0 * 5.0 / (current_time - self.chronometer)
            self.chronometer = current_time
            print((f"Edit #{self.edits} ({throughput:.2f} edits/min)"))

    def _record_translation_failure(self, _language: str, _title: str) -> None:
        """Count a source-translation submission that was not accepted."""
        self.stats["errors"] += 1

    def die(self, msg: str = "Bye") -> None:
        """Stop queue consumers without waiting before disconnecting from IRC."""
        self.page_check_worker.stop(wait=False)
        self.source_translation_worker.stop(wait=False)
        super().die(msg)


def _strip_irc_formatting(message: str) -> str:
    """Remove IRC color and emphasis controls from a feed message."""
    return IRC_FORMATTING_RE.sub("", message)


def _get_origin_wiki(message: str) -> str:
    """Extract the Wiktionary language code from a recent-change URL."""
    match = re.search(r"https?://([a-z-]+)\.wiktionary\.org/", message)
    if match is None:
        raise IrcBotException("Unable to determine the origin Wiktionary.")
    return match.group(1)


def _get_user(message: str) -> Optional[str]:
    """Extract the editor name from a Wikimedia recent-change message."""
    clean_message = _strip_irc_formatting(message)
    url_match = re.search(r"https?://\S+", clean_message)
    if url_match is None:
        return None
    editor_match = re.search(r"\*\s*(.*?)\s*\*", clean_message[url_match.end() :])
    if editor_match is None:
        return None
    editor = editor_match.group(1).strip()
    return editor or None


def _get_edit_summary(message: str) -> Optional[str]:
    """Extract the edit summary following the IRC byte-delta marker."""
    clean_message = _strip_irc_formatting(message)
    url_match = re.search(r"https?://\S+", clean_message)
    if url_match is None:
        return None
    editor_match = re.search(r"\*\s*(.*?)\s*\*", clean_message[url_match.end() :])
    if editor_match is None:
        return None
    remainder = clean_message[url_match.end() + editor_match.end() :]
    summary_match = re.match(r"\s*\([+-]?\d+\)\s*(.*)$", remainder)
    if summary_match is None:
        return None
    return summary_match.group(1).strip()


def _get_pagename(message: str) -> str:
    """Extract and validate the edited page title."""
    match = re.search(r"\[\[(.*?)\]\]", _strip_irc_formatting(message))
    if match is None:
        raise IrcBotException("Unable to determine the edited page title.")
    item = match.group(1).strip()
    if not item:
        raise IrcBotException("Page title is empty.")
    if len(item) > 200:
        raise IrcBotException("Title is too long")
    return item


def _get_message_type(message: str) -> str:
    """Classify all Special:Log events separately from ordinary edits."""
    clean_message = _strip_irc_formatting(message)
    return "log" if "Special:Log" in clean_message or "Log/" in clean_message else "edit"


def _prepare_message(events: Any) -> str:
    """Return the raw IRC message from an event object."""
    if not getattr(events, "arguments", None):
        raise IrcBotException("IRC event has no message body.")
    message = events.arguments[0]
    if not isinstance(message, str):
        raise IrcBotException("IRC event message must be text.")
    return message


def base36encode(
    number: int,
    alphabet: str = "0123456789abcdefghjiklmnopqrstuvwxyz",
) -> str:
    """Converts an integer to a base36 string."""
    if not isinstance(number, int):
        raise TypeError("number must be an integer")

    base36 = ""
    sign = ""

    if number < 0:
        sign = "-"
        number = -number

    if 0 <= number < len(alphabet):
        return sign + alphabet[number]

    while number != 0:
        number, i = divmod(number, len(alphabet))
        base36 = alphabet[i] + base36

    return sign + base36


if __name__ == "__main__":
    try:
        irc_retrieve()
    finally:
        print("bye")
