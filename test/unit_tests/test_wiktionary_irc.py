"""Tests for IRC-driven asynchronous translation and page-check automation."""
from __future__ import annotations

from queue import Queue
from threading import Event
from types import SimpleNamespace
from typing import Any, Dict, List
from unittest.mock import Mock

import pytest
import requests
import wiktionary_irc

from api.services.page_checker_settings import (
    PageCheckerSettings,
    PageCheckerSettingsStoreError,
)
from wiktionary_irc import (
    IrcBotException,
    PageCheckQueueWorker,
    PageCheckerSettingsCache,
    RetryablePageCheckError,
    RetryableSourceTranslationError,
    SourceTranslationQueueWorker,
    WiktionaryRecentChangesBot,
    _get_edit_summary,
    _get_origin_wiki,
    _get_pagename,
    _get_user,
    _prepare_message,
    handle_page_check_response,
    handle_translation_response,
    irc_retrieve,
)


def recent_change(
    language: str = "mg",
    title: str = "alika",
    user: str = "Bot-Jagwar",
    suffix: str = "(+12) fanovana",
) -> str:
    """Build a representative color-coded Wikimedia IRC edit message."""
    return (
        f"\x0314[[\x0307{title}\x0314]]\x034 M\x0310 "
        f"https://{language}.wiktionary.org/w/index.php?diff=2&oldid=1 "
        f"\x035*\x03 \x0303{user}\x03 \x035*\x03 {suffix}"
    )


class FakeResponse:
    """Small requests.Response test double."""

    def __init__(
        self,
        payload: Any,
        status_code: int = 202,
        json_error: bool = False,
        headers: Dict[str, str] | None = None,
    ) -> None:
        self.payload = payload
        self.status_code = status_code
        self.text = str(payload)
        self.json_error = json_error
        self.headers = headers or {}

    def json(self) -> Any:
        """Return the configured payload or simulate invalid JSON."""
        if self.json_error:
            raise ValueError("invalid json")
        return self.payload


class FakeManager:
    """Record entry-translator requests without using HTTP."""

    def __init__(self, response: FakeResponse | None = None) -> None:
        self.response = response or FakeResponse({"jobs": [{"job_id": "job-1"}]})
        self.calls: List[tuple[str, Dict[str, Any]]] = []
        self.called = Event()

    def post(self, route: str, **kwargs: Any) -> FakeResponse:
        """Record and return one deterministic response."""
        self.calls.append((route, kwargs))
        self.called.set()
        return self.response

    def post_once(self, route: str, **kwargs: Any) -> FakeResponse:
        """Send one recorded request without retry behavior."""
        return self.post(route, **kwargs)


class FakeSettingsStore:
    """Return mutable in-memory automation settings."""

    def __init__(self, settings: PageCheckerSettings) -> None:
        self.settings = settings
        self.calls = 0

    def get(self) -> PageCheckerSettings:
        """Return the current settings value."""
        self.calls += 1
        return self.settings


class FakeClock:
    """Controllable monotonic clock."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class FakeStopEvent:
    """Event double that advances a fake clock while waiting."""

    def __init__(self, clock: FakeClock) -> None:
        self.clock = clock
        self.stopped = False
        self.waits: List[float] = []

    def clear(self) -> None:
        self.stopped = False

    def set(self) -> None:
        self.stopped = True

    def is_set(self) -> bool:
        return self.stopped

    def wait(self, seconds: float) -> bool:
        self.waits.append(seconds)
        self.clock.now += seconds
        return self.stopped


def build_bot(
    settings: PageCheckerSettings | None = None,
    random_value: float = 0.0,
    page_queue: Queue[str] | None = None,
    source_translation_queue: Queue[tuple[str, str]] | None = None,
) -> tuple[WiktionaryRecentChangesBot, FakeManager, FakeSettingsStore]:
    """Create the IRC bot with deterministic local dependencies."""
    manager = FakeManager(
        FakeResponse({"job_id": "translation-job-1", "status": "pending"})
    )
    store = FakeSettingsStore(settings or PageCheckerSettings())
    bot = WiktionaryRecentChangesBot(
        entry_translator_manager=manager,
        settings_store=store,  # type: ignore[arg-type]
        random_value=lambda: random_value,
        page_queue=page_queue,
        source_translation_queue=source_translation_queue,
    )
    return bot, manager, store


def test_recent_change_parser_extracts_colored_title_wiki_and_user() -> None:
    """IRC formatting does not leak into parsed event fields."""
    message = recent_change(title="trano fonenana", user="Bot_Jagwar")

    assert _get_origin_wiki(message) == "mg"
    assert _get_pagename(message) == "trano fonenana"
    assert _get_user(message) == "Bot_Jagwar"
    assert _get_edit_summary(message) == "fanovana"


def test_recent_change_parser_rejects_missing_or_invalid_fields() -> None:
    """Malformed events fail explicitly instead of targeting a fallback wiki."""
    assert _get_user("[[alika]] https://mg.wiktionary.org/wiki/alika") is None
    with pytest.raises(IrcBotException, match="origin"):
        _get_origin_wiki("[[alika]]")
    with pytest.raises(IrcBotException, match="title"):
        _get_pagename("https://mg.wiktionary.org/wiki/alika")
    with pytest.raises(IrcBotException, match="too long"):
        _get_pagename(recent_change(title="a" * 201))
    with pytest.raises(IrcBotException, match="no message"):
        _prepare_message(SimpleNamespace(arguments=[]))


def test_bot_joins_only_the_malagasy_channel() -> None:
    """The single IRC connection subscribes to the Malagasy Wiktionary only."""
    bot, _manager, _store = build_bot()
    server = SimpleNamespace(joined=[], join=lambda channel: server.joined.append(channel))

    bot.on_welcome(server, None)

    assert bot.joined == ["#mg.wiktionary"]
    assert server.joined == bot.joined


def test_settings_cache_fails_closed_until_redis_recovers() -> None:
    """A startup Redis outage cannot silently enable automatic checks."""
    def unavailable_settings() -> PageCheckerSettings:
        raise PageCheckerSettingsStoreError("down")

    cache = PageCheckerSettingsCache(unavailable_settings)

    assert cache.refresh().check_probability == 0
    assert cache.get().watched_users == ()


def test_matching_malagasy_edit_is_sampled_and_enqueued_without_http() -> None:
    """A selected edit only touches the queue in the IRC callback."""
    bot, manager, store = build_bot(random_value=0.099)

    bot.on_pubmsg(None, SimpleNamespace(arguments=[recent_change()]))

    assert bot.page_check_worker.queue.get_nowait() == "alika"
    assert manager.calls == []
    assert store.calls == 1


@pytest.mark.parametrize(
    ("settings", "random_value", "user", "suffix", "expected"),
    [
        (PageCheckerSettings(check_probability=10), 0.1, "Bot-Jagwar", "edit", False),
        (PageCheckerSettings(check_probability=0), 0.0, "Bot-Jagwar", "edit", False),
        (PageCheckerSettings(check_probability=100), 1.0, "Bot-Jagwar", "edit", True),
        (PageCheckerSettings(check_probability=100, autonomous_agent_enabled=True), 0.5, "Bot-Jagwar", "edit", True),
        (PageCheckerSettings(), 0.0, "SomeoneElse", "edit", False),
        (PageCheckerSettings(), 0.0, "Bot-Jagwar", "Log/delete", False),
        (PageCheckerSettings(watched_users=("Bot Jagwar",)), 0.0, "bot_Jagwar", "edit", True),
    ],
)
def test_malagasy_edit_filters_and_probability_boundaries(
    settings: PageCheckerSettings,
    random_value: float,
    user: str,
    suffix: str,
    expected: bool,
) -> None:
    """Whitelist, edit type and exact percentage boundaries gate enqueueing."""
    bot, _manager, _store = build_bot(settings, random_value=random_value)

    bot.on_pubmsg(
        None,
        SimpleNamespace(arguments=[recent_change(user=user, suffix=suffix)]),
    )

    assert (not bot.page_check_worker.queue.empty()) is expected


@pytest.mark.parametrize(
    "summary",
    ["fanitsiana famaritana", "Dikanteny: es"],
)
def test_default_edit_summaries_are_filtered_before_enqueue(summary: str) -> None:
    """Worker fixes and the configured Spanish rule do not trigger checks."""
    bot, _manager, _store = build_bot(
        PageCheckerSettings(check_probability=100),
        random_value=0,
    )

    bot.on_pubmsg(
        None,
        SimpleNamespace(arguments=[recent_change(suffix=f"(+12) {summary}")]),
    )

    assert bot.page_check_worker.queue.empty()


def test_edit_summary_filter_is_configurable_and_matches_exactly() -> None:
    """Custom exact summaries are ignored while similar summaries still run."""
    settings = PageCheckerSettings(
        check_probability=100,
        ignored_edit_summaries=("custom summary",),
    )
    ignored_bot, _manager, _store = build_bot(settings)
    accepted_bot, _manager, _store = build_bot(settings)

    ignored_bot.on_pubmsg(
        None,
        SimpleNamespace(
            arguments=[recent_change(suffix="(+12) custom summary")]
        ),
    )
    accepted_bot.on_pubmsg(
        None,
        SimpleNamespace(
            arguments=[recent_change(suffix="(+12) Custom summary")]
        ),
    )

    assert ignored_bot.page_check_worker.queue.empty()
    assert accepted_bot.page_check_worker.queue.get_nowait() == "alika"


@pytest.mark.parametrize(
    "message",
    [
        recent_change(title="Template:stub"),
        recent_change(title="Special:Log/move", suffix="moved page"),
    ],
)
def test_non_article_events_do_not_enter_page_check_queue(message: str) -> None:
    """Logs and namespaced pages are excluded before probability sampling."""
    bot, _manager, _store = build_bot(random_value=0)

    bot.on_pubmsg(None, SimpleNamespace(arguments=[message]))

    assert bot.page_check_worker.queue.empty()


@pytest.mark.parametrize("language", ["en", "fr"])
def test_source_wiki_edit_is_enqueued_without_callback_http(language: str) -> None:
    """English and French callbacks only enqueue exact source pages."""
    bot, manager, store = build_bot()

    bot.on_pubmsg(None, SimpleNamespace(arguments=[recent_change(language=language)]))

    assert bot.source_translation_worker.queue.get_nowait() == (language, "alika")
    assert manager.calls == []
    assert store.calls == 1
    assert bot.edits == 0


def test_source_translation_worker_posts_job_route_and_body() -> None:
    """The worker submits one asynchronous job and does not poll it."""
    manager = FakeManager(
        FakeResponse({"job_id": "translation-job-1", "status": "pending"})
    )
    worker = SourceTranslationQueueWorker(
        manager,
        request_id_factory=lambda: "9c9a6a48-2304-4505-9cfe-57fbddc88bb1",
    )

    assert worker._submit("fr", "maison") is True

    assert manager.calls == [
        (
            "wiktionary-pages/fr/jobs",
            {
                "json": {
                    "title": "maison",
                    "request_id": "9c9a6a48-2304-4505-9cfe-57fbddc88bb1",
                }
            },
        )
    ]


def test_source_translation_worker_deduplicates_exact_source_pages() -> None:
    """Only an exact language-title duplicate is coalesced in the queue."""
    worker = SourceTranslationQueueWorker(
        FakeManager(),
        translation_queue=Queue(maxsize=3),
    )

    assert worker.enqueue("en", "alika") is True
    assert worker.enqueue("en", "alika") is True
    assert worker.enqueue("fr", "alika") is True
    assert worker.enqueue("en", "Alika") is True

    assert worker.queue.qsize() == 3


def test_bounded_source_translation_queue_rejects_overflow() -> None:
    """A source-feed burst cannot grow the translation queue without bound."""
    worker = SourceTranslationQueueWorker(
        FakeManager(),
        translation_queue=Queue(maxsize=1),
    )

    assert worker.enqueue("en", "first") is True
    assert worker.enqueue("en", "second") is False


def test_source_translation_worker_thread_consumes_queue_and_stops() -> None:
    """The dedicated worker accepts a queued job and stops cleanly."""
    manager = FakeManager(
        FakeResponse({"job_id": "translation-job-1", "status": "pending"})
    )
    accepted = Event()
    worker = SourceTranslationQueueWorker(
        manager,
        accepted_callback=lambda _language, _title: accepted.set(),
    )

    worker.start()
    assert worker.enqueue("en", "alika") is True
    assert accepted.wait(timeout=1)
    worker.stop()

    assert worker._thread is not None
    assert not worker._thread.is_alive()
    assert len(manager.calls) == 1


def test_source_translation_worker_retries_connection_errors() -> None:
    """A connection failure uses bounded fallback before a later acceptance."""
    class ConnectionThenAcceptedManager(FakeManager):
        """Fail one connection and then return an accepted translation job."""

        def post(self, route: str, **kwargs: Any) -> FakeResponse:
            self.calls.append((route, kwargs))
            if len(self.calls) == 1:
                raise requests.ConnectionError("offline")
            return self.response

    manager = ConnectionThenAcceptedManager(
        FakeResponse({"job_id": "translation-job-1", "status": "pending"})
    )
    clock = FakeClock()
    stop_event = FakeStopEvent(clock)
    accepted = Event()
    worker = SourceTranslationQueueWorker(
        manager,
        stop_event=stop_event,  # type: ignore[arg-type]
        accepted_callback=lambda _language, _title: accepted.set(),
        request_id_factory=lambda: "9c9a6a48-2304-4505-9cfe-57fbddc88bb1",
    )

    worker.start()
    assert worker.enqueue("en", "alika") is True
    assert accepted.wait(timeout=1)
    worker.stop()

    assert len(manager.calls) == 2
    assert manager.calls[0][1]["json"] == manager.calls[1][1]["json"]
    assert stop_event.waits == [1]


@pytest.mark.parametrize("status_code", [429, 500, 503])
def test_translation_response_marks_only_transient_http_errors_retryable(
    status_code: int,
) -> None:
    """Capacity and server failures carry retry metadata to the worker."""
    response = FakeResponse(
        {"message": "try later"},
        status_code=status_code,
        headers={"Retry-After": "7"},
    )

    with pytest.raises(RetryableSourceTranslationError) as raised:
        handle_translation_response(response)  # type: ignore[arg-type]

    assert raised.value.retry_after_seconds == 7


@pytest.mark.parametrize("status_code", [400, 403, 408, 600])
def test_source_translation_worker_never_retries_client_rejections(
    status_code: int,
) -> None:
    """Invalid or forbidden requests are dropped after their first response."""
    manager = FakeManager(
        FakeResponse({"message": "rejected"}, status_code=status_code)
    )
    failed = Event()
    worker = SourceTranslationQueueWorker(
        manager,
        failure_callback=lambda _language, _title: failed.set(),
    )

    worker.start()
    assert worker.enqueue("en", "alika") is True
    assert failed.wait(timeout=1)
    worker.stop()

    assert len(manager.calls) == 1


@pytest.mark.parametrize(
    ("retry_after", "expected_delay"),
    [("11", 11), ("not-an-integer", 1), ("-2", 1)],
)
def test_source_translation_retry_honors_integer_retry_after_or_fallback(
    retry_after: str,
    expected_delay: int,
) -> None:
    """Valid server delays take precedence over the exponential fallback."""
    response = FakeResponse(
        {"message": "busy"},
        status_code=429,
        headers={"Retry-After": retry_after},
    )
    with pytest.raises(RetryableSourceTranslationError) as raised:
        handle_translation_response(response)  # type: ignore[arg-type]
    clock = FakeClock()
    stop_event = FakeStopEvent(clock)
    worker = SourceTranslationQueueWorker(
        FakeManager(),
        stop_event=stop_event,  # type: ignore[arg-type]
    )

    assert worker._retry(("en", "alika"), raised.value) is True

    assert stop_event.waits == [expected_delay]


def test_source_translation_retries_are_bounded_with_exponential_fallback() -> None:
    """A permanently disconnected service cannot cause unlimited attempts."""
    clock = FakeClock()
    stop_event = FakeStopEvent(clock)
    worker = SourceTranslationQueueWorker(
        FakeManager(),
        stop_event=stop_event,  # type: ignore[arg-type]
    )
    page = ("en", "alika")
    error = requests.ConnectionError("offline")

    for _ in range(5):
        assert worker._retry(page, error) is True
    assert worker._retry(page, error) is False

    assert stop_event.waits == [1, 2, 4, 8, 16]


@pytest.mark.parametrize(
    "response",
    [
        FakeResponse({"job_id": "translation-job-1"}),
        FakeResponse({"status": "pending"}),
        FakeResponse({"jobs": [{"job_id": "translation-job-1"}]}),
        FakeResponse(
            {"job_id": "translation-job-1", "status": "pending"},
            status_code=200,
        ),
        FakeResponse(None, json_error=True),
    ],
)
def test_translation_response_rejects_invalid_job_records(
    response: FakeResponse,
) -> None:
    """Acceptance requires one JSON job record with ID and status at HTTP 202."""
    with pytest.raises(IrcBotException) as raised:
        handle_translation_response(response)  # type: ignore[arg-type]

    assert not isinstance(raised.value, RetryableSourceTranslationError)


def test_irc_retrieve_starts_and_stops_both_workers_without_waiting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Top-level cleanup signals both background consumers without joining."""
    page_worker = SimpleNamespace(start=Mock(), stop=Mock())
    source_worker = SimpleNamespace(start=Mock(), stop=Mock())
    bot = SimpleNamespace(
        page_check_worker=page_worker,
        source_translation_worker=source_worker,
        start=Mock(side_effect=KeyboardInterrupt),
        die=Mock(),
    )
    monkeypatch.setattr(wiktionary_irc, "WiktionaryRecentChangesBot", lambda: bot)

    irc_retrieve()

    page_worker.start.assert_called_once_with()
    source_worker.start.assert_called_once_with()
    bot.die.assert_called_once_with()
    page_worker.stop.assert_called_once_with(wait=False)
    source_worker.stop.assert_called_once_with(wait=False)


def test_bot_die_stops_both_workers_without_waiting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """IRC disconnect does not wait on an in-flight HTTP request."""
    bot, _manager, _store = build_bot()
    page_stop = Mock()
    source_stop = Mock()
    parent_die = Mock()
    bot.page_check_worker = SimpleNamespace(stop=page_stop)  # type: ignore[assignment]
    bot.source_translation_worker = SimpleNamespace(  # type: ignore[assignment]
        stop=source_stop
    )
    monkeypatch.setattr(wiktionary_irc.irc.bot.SingleServerIRCBot, "die", parent_die)

    bot.die("shutdown")

    page_stop.assert_called_once_with(wait=False)
    source_stop.assert_called_once_with(wait=False)
    parent_die.assert_called_once_with("shutdown")


def test_malformed_message_is_logged_without_escaping_the_callback() -> None:
    """Bad feed data increments diagnostics but does not crash the IRC reactor."""
    bot, _manager, _store = build_bot()

    bot.on_pubmsg(None, SimpleNamespace(arguments=[]))

    assert bot.stats["errors"] == 1


def test_worker_submits_jobs_with_dynamic_cooldown_between_requests() -> None:
    """One worker spaces asynchronous check submissions using current settings."""
    manager = FakeManager()
    store = FakeSettingsStore(PageCheckerSettings(cooldown_seconds=5))
    clock = FakeClock()
    stop_event = FakeStopEvent(clock)
    worker = PageCheckQueueWorker(
        manager,
        store.get,
        stop_event=stop_event,  # type: ignore[arg-type]
        clock=clock,
    )

    assert worker._submit("alika") is True
    clock.now = 2
    store.settings = PageCheckerSettings(cooldown_seconds=4)
    assert worker._submit("soa") is True

    assert stop_event.waits == [1.0, 1.0]
    assert manager.calls == [
        ("wiktionary-pages/mg/check-jobs", {"json": {"titles": ["alika"]}}),
        ("wiktionary-pages/mg/check-jobs", {"json": {"titles": ["soa"]}}),
    ]


def test_worker_thread_consumes_queue_and_stops() -> None:
    """The background consumer turns a queued title into an HTTP job request."""
    manager = FakeManager()
    worker = PageCheckQueueWorker(
        manager,
        lambda: PageCheckerSettings(cooldown_seconds=0),
    )

    worker.start()
    assert worker.enqueue("alika") is True
    assert manager.called.wait(timeout=1)
    worker.stop()

    assert manager.calls[0][0] == "wiktionary-pages/mg/check-jobs"
    assert worker._thread is not None
    assert not worker._thread.is_alive()


def test_worker_retries_explicit_server_failures() -> None:
    """A capacity response is requeued instead of permanently losing the title."""
    class RetryManager(FakeManager):
        """Return one capacity failure followed by an accepted job."""

        def __init__(self) -> None:
            super().__init__()
            self.responses = [
                FakeResponse({"message": "full"}, status_code=503),
                FakeResponse({"jobs": [{"job_id": "job-1"}]}),
            ]
            self.accepted = Event()

        def post(self, route: str, **kwargs: Any) -> FakeResponse:
            self.calls.append((route, kwargs))
            response = self.responses.pop(0)
            if not self.responses:
                self.accepted.set()
            return response

    manager = RetryManager()
    worker = PageCheckQueueWorker(
        manager,
        lambda: PageCheckerSettings(cooldown_seconds=0),
    )

    worker.start()
    assert worker.enqueue("alika") is True
    assert manager.accepted.wait(timeout=3)
    worker.stop()

    assert len(manager.calls) == 2
    assert worker.queue.empty()


def test_bounded_worker_queue_rejects_overflow() -> None:
    """A feed burst cannot grow the in-process queue without a bound."""
    worker = PageCheckQueueWorker(
        FakeManager(),
        lambda: PageCheckerSettings(),
        page_queue=Queue(maxsize=1),
    )

    assert worker.enqueue("first") is True
    assert worker.enqueue("second") is False


def test_worker_coalesces_duplicate_queued_titles() -> None:
    """Repeated IRC events cannot occupy several queue slots for one title."""
    worker = PageCheckQueueWorker(
        FakeManager(),
        lambda: PageCheckerSettings(),
        page_queue=Queue(maxsize=2),
    )

    assert worker.enqueue("alika") is True
    assert worker.enqueue("alika") is True
    assert worker.queue.qsize() == 1


@pytest.mark.parametrize(
    "response",
    [
        FakeResponse({"message": "full"}, status_code=503),
        FakeResponse({"unexpected": True}),
        FakeResponse(None, json_error=True),
    ],
)
def test_page_check_response_rejects_failed_or_malformed_jobs(
    response: FakeResponse,
) -> None:
    """Only a successful asynchronous job payload is accepted."""
    with pytest.raises(IrcBotException):
        handle_page_check_response(response)  # type: ignore[arg-type]


def test_page_check_response_marks_server_capacity_as_retryable() -> None:
    """Explicit server failures remain in the worker queue for retry."""
    with pytest.raises(RetryablePageCheckError):
        handle_page_check_response(  # type: ignore[arg-type]
            FakeResponse({"message": "full"}, status_code=503)
        )
    with pytest.raises(RetryablePageCheckError):
        handle_page_check_response(  # type: ignore[arg-type]
            FakeResponse(None, status_code=503, json_error=True)
        )


def test_worker_aborts_cooldown_during_shutdown() -> None:
    """Shutdown prevents a waiting title from being submitted."""
    manager = FakeManager()
    clock = FakeClock()
    stop_event = FakeStopEvent(clock)
    worker = PageCheckQueueWorker(
        manager,
        lambda: PageCheckerSettings(cooldown_seconds=5),
        stop_event=stop_event,  # type: ignore[arg-type]
        clock=clock,
    )
    worker._last_submission_at = 0
    stop_event.set()

    assert worker._submit("alika") is False
    assert manager.calls == []
