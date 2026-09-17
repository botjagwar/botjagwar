from types import SimpleNamespace
from typing import Any

import pytest

import redis_wikicache
from redis_wikicache import NoPage, RedisPage, RedisSite, UnsafeWikiWriteError


class RecordingLimiter:
    """Record permits and observed failures without using Redis."""

    def __init__(self, events: list[Any] | None = None) -> None:
        self.events = events if events is not None else []
        self.observed: list[Exception] = []

    def acquire(self) -> float:
        """Record one reserved live boundary."""
        self.events.append("permit")
        return 0

    def observe_exception(self, error: Exception) -> bool:
        """Record a failed live boundary without retrying it."""
        self.observed.append(error)
        return False


def test_force_refresh_bypasses_stale_cache_and_updates_it(monkeypatch):
    """A live refresh reads Wiktionary even when Redis already has the page."""
    pushed = []
    redis_client = SimpleNamespace(get=lambda _key: b"stale text")
    site = SimpleNamespace(
        offline=False,
        wiki="wiktionary",
        language="mg",
        instance=redis_client,
        rate_limiter=RecordingLimiter(),
        wikimedia_site=object(),
        push_page=lambda title, content: pushed.append((title, content)),
    )
    wiki_page = SimpleNamespace(get=lambda **_kwargs: "current text")
    monkeypatch.setattr(
        redis_wikicache.pywikibot,
        "Page",
        lambda _site, _title: wiki_page,
    )
    page = RedisPage(site, "alika")

    assert page.get() == "stale text"
    assert page.get(force_refresh=True) == "current text"
    assert pushed == [("alika", "current text")]


def test_force_refresh_keeps_offline_cached_pages_offline(monkeypatch):
    """Offline pages continue to use Redis when a refresh is requested."""
    site = SimpleNamespace(
        offline=True,
        wiki="wiktionary",
        language="mg",
        instance=SimpleNamespace(get=lambda _key: b"cached text"),
    )
    monkeypatch.setattr(
        redis_wikicache.pywikibot,
        "Site",
        lambda *_args: pytest.fail("offline refresh attempted network access"),
    )

    assert RedisPage(site, "alika").get(force_refresh=True) == "cached text"


def test_force_refresh_ignores_redis_timeouts(monkeypatch):
    """A live refresh does not depend on a responsive Redis server."""
    redis_client = SimpleNamespace(
        get=lambda _key: pytest.fail("forced refresh read Redis"),
    )
    pushed = []
    site = SimpleNamespace(
        offline=False,
        wiki="wiktionary",
        language="mg",
        instance=redis_client,
        rate_limiter=RecordingLimiter(),
        wikimedia_site=object(),
        push_page=lambda title, content: pushed.append((title, content)),
    )
    wiki_page = SimpleNamespace(get=lambda **_kwargs: "current text")
    monkeypatch.setattr(
        redis_wikicache.pywikibot,
        "Page",
        lambda _site, _title: wiki_page,
    )

    assert RedisPage(site, "alika").get(force_refresh=True) == "current text"
    assert pushed == [("alika", "current text")]


def test_put_updates_cache_only_after_successful_wiki_write(monkeypatch):
    """Published text replaces stale Redis content after Pywikibot succeeds."""
    events = []
    site = SimpleNamespace(
        offline=False,
        wiki="wiktionary",
        language="mg",
        rate_limiter=RecordingLimiter(events),
        wikimedia_site=object(),
        push_page=lambda title, content: events.append(("cache", title, content)),
    )
    wiki_page = SimpleNamespace(
        put=lambda content, summary, **kwargs: events.append(
            ("wiki", content, summary, kwargs)
        )
        or "saved"
    )
    monkeypatch.setattr(
        redis_wikicache.pywikibot,
        "Page",
        lambda _site, _title: wiki_page,
    )

    result = RedisPage(site, "alika").put(
        "new text",
        "summary",
        before_live_call=lambda: events.append("guard"),
        nocreate=True,
        recreate=False,
    )

    assert result == "saved"
    assert events == [
        "permit",
        "guard",
        (
            "wiki",
            "new text",
            "summary",
            {"nocreate": True, "recreate": False},
        ),
        ("cache", "alika", "new text"),
    ]


def test_delete_evicts_cache_only_after_successful_wiki_delete(monkeypatch):
    """A live delete uses the limiter before evicting the cached page."""
    events = []
    site = SimpleNamespace(
        offline=False,
        wiki="wiktionary",
        language="mg",
        rate_limiter=RecordingLimiter(events),
        wikimedia_site=object(),
        instance=SimpleNamespace(
            delete=lambda key: events.append(("cache-delete", key))
        ),
    )
    wiki_page = SimpleNamespace(
        delete=lambda reason: events.append(("wiki-delete", reason)) or "deleted"
    )
    monkeypatch.setattr(
        redis_wikicache.pywikibot,
        "Page",
        lambda _site, _title: wiki_page,
    )

    result = RedisPage(site, "alika").delete("reason")

    assert result == "deleted"
    assert events == [
        "permit",
        ("wiki-delete", "reason"),
        ("cache-delete", "wiktionary.mg/alika"),
    ]


@pytest.mark.parametrize(
    ("language", "wiki"),
    [("en", "wiktionary"), ("mg", "wikipedia")],
)
def test_put_rejects_unsafe_destination_before_live_side_effects(
    monkeypatch, language: str, wiki: str
) -> None:
    """A programming error cannot turn a source or sibling wiki into a target."""
    limiter = RecordingLimiter()
    site = SimpleNamespace(
        offline=False,
        wiki=wiki,
        language=language,
        rate_limiter=limiter,
        push_page=lambda *_args: pytest.fail("unsafe write updated cache"),
    )
    monkeypatch.setattr(
        redis_wikicache.pywikibot,
        "Page",
        lambda *_args: pytest.fail("unsafe write constructed a live page"),
    )

    with pytest.raises(UnsafeWikiWriteError, match="restricted to mg.wiktionary"):
        RedisPage(site, "unsafe").put("content", "summary")

    assert limiter.events == []


def test_delete_and_delegated_save_reject_source_wiki(monkeypatch) -> None:
    """Delete and delegated Pywikibot writes share the destination restriction."""
    site = SimpleNamespace(
        offline=False,
        wiki="wiktionary",
        language="fr",
        rate_limiter=RecordingLimiter(),
    )
    monkeypatch.setattr(
        redis_wikicache.pywikibot,
        "Page",
        lambda *_args: pytest.fail("unsafe mutation constructed a live page"),
    )
    page = RedisPage(site, "unsafe")

    with pytest.raises(UnsafeWikiWriteError):
        page.delete("reason")
    with pytest.raises(UnsafeWikiWriteError):
        page.save()


def test_offline_page_rejects_live_mutations_before_limiter(monkeypatch) -> None:
    """Offline/test pages cannot reach any Malagasy Wiktionary write boundary."""
    limiter = RecordingLimiter()
    site = SimpleNamespace(
        offline=True,
        wiki="wiktionary",
        language="mg",
        rate_limiter=limiter,
    )
    monkeypatch.setattr(
        redis_wikicache.pywikibot,
        "Page",
        lambda *_args: pytest.fail("offline mutation constructed a live page"),
    )
    page = RedisPage(site, "alika")

    with pytest.raises(UnsafeWikiWriteError, match="disabled offline"):
        page.put("content", "summary")
    with pytest.raises(UnsafeWikiWriteError, match="disabled offline"):
        page.delete("reason")
    with pytest.raises(UnsafeWikiWriteError, match="disabled offline"):
        page.save()

    assert limiter.events == []


def test_force_refresh_and_put_share_revision_aware_page(monkeypatch):
    """The page loaded for conflict checking is also used for publication."""
    created_pages = []
    wiki_page = SimpleNamespace(
        get=lambda **_kwargs: "current text",
        put=lambda _content, _summary: None,
    )
    site = SimpleNamespace(
        offline=False,
        wiki="wiktionary",
        language="mg",
        rate_limiter=RecordingLimiter(),
        wikimedia_site=object(),
        push_page=lambda _title, _content: None,
    )

    def build_page(_site, _title):
        created_pages.append(wiki_page)
        return wiki_page

    monkeypatch.setattr(redis_wikicache.pywikibot, "Page", build_page)
    page = RedisPage(site, "alika")

    assert page.get(force_refresh=True) == "current text"
    page.put("new text", "summary")

    assert created_pages == [wiki_page]


def test_successive_force_refreshes_request_new_live_text(monkeypatch):
    """Reusing a RedisPage still forces Pywikibot to load each new revision."""
    versions = iter(("first revision", "second revision"))
    force_arguments = []

    def get_page_text(**kwargs):
        force_arguments.append(kwargs)
        return next(versions)

    wiki_page = SimpleNamespace(get=get_page_text)
    site = SimpleNamespace(
        offline=False,
        wiki="wiktionary",
        language="mg",
        rate_limiter=RecordingLimiter(),
        wikimedia_site=object(),
        push_page=lambda _title, _content: None,
    )
    monkeypatch.setattr(
        redis_wikicache.pywikibot,
        "Page",
        lambda _site, _title: wiki_page,
    )
    page = RedisPage(site, "alika")

    assert page.get(force_refresh=True) == "first revision"
    assert page.get(force_refresh=True) == "second revision"
    assert force_arguments == [{"force": True}, {"force": True}]


def test_cache_hits_bypass_limiter_and_live_page_creation(monkeypatch):
    """Even an empty cached page is authoritative and needs no live permit."""

    class UnexpectedLimiter:
        def acquire(self) -> None:
            pytest.fail("cache hit acquired a live permit")

    site = SimpleNamespace(
        offline=False,
        wiki="wiktionary",
        language="mg",
        instance=SimpleNamespace(get=lambda _key: b""),
        rate_limiter=UnexpectedLimiter(),
    )
    monkeypatch.setattr(
        redis_wikicache.pywikibot,
        "Page",
        lambda *_args: pytest.fail("cache hit created a live page"),
    )
    page = RedisPage(site, "alika")

    assert page.get() == ""
    assert page.exists() is True
    assert page.isRedirectPage() is False


def test_live_read_acquires_before_get_without_exists_request(monkeypatch):
    """One uncached read reserves one start and calls Page.get directly."""
    events: list[Any] = []
    limiter = RecordingLimiter(events)

    def get_text(**kwargs: Any) -> str:
        events.append(("get", kwargs))
        return "live text"

    wiki_page = SimpleNamespace(
        get=get_text,
        exists=lambda: pytest.fail("live get made a redundant exists request"),
    )
    site = SimpleNamespace(
        offline=False,
        wiki="wiktionary",
        language="mg",
        instance=SimpleNamespace(get=lambda _key: None),
        rate_limiter=limiter,
        wikimedia_site=object(),
        push_page=lambda title, content: events.append(("cache", title, content)),
    )
    monkeypatch.setattr(
        redis_wikicache.pywikibot,
        "Page",
        lambda _site, _title: wiki_page,
    )

    assert RedisPage(site, "alika").get() == "live text"
    assert events == [
        "permit",
        ("get", {"force": False}),
        ("cache", "alika", "live text"),
    ]


def test_missing_live_page_maps_no_page_without_caching(monkeypatch):
    """Page.get's NoPageError becomes the wrapper's established NoPage error."""
    wiki_page = SimpleNamespace(
        site=object(),
        title=lambda **_kwargs: "tsy-misy",
    )
    missing = redis_wikicache.pywikibot.exceptions.NoPageError(wiki_page)
    wiki_page.get = lambda **_kwargs: (_ for _ in ()).throw(missing)
    pushes: list[tuple[str, str]] = []
    limiter = RecordingLimiter()
    site = SimpleNamespace(
        offline=False,
        wiki="wiktionary",
        language="mg",
        instance=SimpleNamespace(get=lambda _key: None),
        rate_limiter=limiter,
        wikimedia_site=object(),
        push_page=lambda title, content: pushes.append((title, content)),
    )
    monkeypatch.setattr(
        redis_wikicache.pywikibot,
        "Page",
        lambda _site, _title: wiki_page,
    )

    with pytest.raises(NoPage):
        RedisPage(site, "tsy-misy").get()

    assert pushes == []
    assert limiter.observed == [missing]
    assert limiter.events == ["permit"]


def test_failed_live_read_is_observed_and_not_cached(monkeypatch):
    """A failed Wikimedia read never populates Redis or retries in the wrapper."""
    failure = RuntimeError("Wikimedia failed")
    read_calls = 0

    def fail_read(**_kwargs: Any) -> str:
        nonlocal read_calls
        read_calls += 1
        raise failure

    limiter = RecordingLimiter()
    site = SimpleNamespace(
        offline=False,
        wiki="wiktionary",
        language="mg",
        instance=SimpleNamespace(get=lambda _key: None),
        rate_limiter=limiter,
        wikimedia_site=object(),
        push_page=lambda *_args: pytest.fail("failed read was cached"),
    )
    monkeypatch.setattr(
        redis_wikicache.pywikibot,
        "Page",
        lambda _site, _title: SimpleNamespace(get=fail_read),
    )

    with pytest.raises(RuntimeError, match="Wikimedia failed"):
        RedisPage(site, "alika").get()

    assert read_calls == 1
    assert limiter.observed == [failure]


def test_failed_put_does_not_update_cache_or_retry(monkeypatch):
    """A failed publication is observed once and leaves cached text unchanged."""
    failure = RuntimeError("write rejected")
    write_calls = 0

    def fail_write(*_args: Any, **_kwargs: Any) -> None:
        nonlocal write_calls
        write_calls += 1
        raise failure

    limiter = RecordingLimiter()
    site = SimpleNamespace(
        offline=False,
        wiki="wiktionary",
        language="mg",
        rate_limiter=limiter,
        wikimedia_site=object(),
        push_page=lambda *_args: pytest.fail("failed write was cached"),
    )
    monkeypatch.setattr(
        redis_wikicache.pywikibot,
        "Page",
        lambda _site, _title: SimpleNamespace(put=fail_write),
    )

    with pytest.raises(RuntimeError, match="write rejected"):
        RedisPage(site, "alika").put("new text", "summary")

    assert write_calls == 1
    assert limiter.observed == [failure]


def test_exists_namespace_and_redirect_boundaries_are_gated(monkeypatch):
    """Every explicit metadata or redirect request reserves its own start."""
    events: list[Any] = []
    namespace = SimpleNamespace(id=0)
    target = object()
    wiki_page = SimpleNamespace(
        exists=lambda: events.append("exists") or False,
        namespace=lambda: events.append("namespace") or namespace,
        isRedirectPage=lambda: events.append("redirect") or True,
        getRedirectTarget=lambda: events.append("target") or target,
    )
    site = SimpleNamespace(
        offline=False,
        wiki="wiktionary",
        language="mg",
        instance=SimpleNamespace(get=lambda _key: None),
        rate_limiter=RecordingLimiter(events),
        wikimedia_site=object(),
    )
    monkeypatch.setattr(
        redis_wikicache.pywikibot,
        "Page",
        lambda _site, _title: wiki_page,
    )

    assert RedisPage(site, "missing").exists() is False
    assert RedisPage(site, "alika").namespace() is namespace
    assert RedisPage(site, "redirect").isRedirectPage() is True
    assert RedisPage(site, "redirect").getRedirectTarget() is target
    assert events == [
        "permit",
        "exists",
        "permit",
        "namespace",
        "permit",
        "redirect",
        "permit",
        "target",
    ]


def test_redis_site_applies_bounded_pywikibot_network_policy(monkeypatch):
    """Pywikibot policy is applied lazily before a site can perform I/O."""
    policy_names = (
        "max_retries",
        "retry_wait",
        "retry_max",
        "maxlag",
        "socket_timeout",
        "user_agent_description",
    )
    for name in policy_names:
        monkeypatch.setattr(
            redis_wikicache.pywikibot.config,
            name,
            getattr(redis_wikicache.pywikibot.config, name),
        )

    sentinel = object()
    created: list[tuple[str, str]] = []

    def build_site(language: str, wiki: str) -> object:
        created.append((language, wiki))
        return sentinel

    monkeypatch.setattr(redis_wikicache.pywikibot, "Site", build_site)
    site = RedisSite(
        "mg",
        "wiktionary",
        redis_client=SimpleNamespace(),
        rate_limiter=RecordingLimiter(),
    )

    assert created == []
    assert site.wikimedia_site is sentinel
    assert created == [("mg", "wiktionary")]
    assert redis_wikicache.pywikibot.config.max_retries == 2
    assert redis_wikicache.pywikibot.config.retry_wait == 1
    assert redis_wikicache.pywikibot.config.retry_max == 5
    assert redis_wikicache.pywikibot.config.maxlag == 5
    assert redis_wikicache.pywikibot.config.socket_timeout == (5, 30)
    assert "Botjagwar" in redis_wikicache.pywikibot.config.user_agent_description


def test_wikimedia_site_is_cached_per_instance(monkeypatch):
    """Each RedisSite must build its own Pywikibot site, not share one."""
    created: list[tuple[str, str]] = []

    def build_site(language: str, wiki: str) -> object:
        created.append((language, wiki))
        return object()

    monkeypatch.setattr(redis_wikicache.pywikibot, "Site", build_site)
    en_site = RedisSite(
        "en",
        "wiktionary",
        redis_client=SimpleNamespace(),
        rate_limiter=RecordingLimiter(),
    )
    mg_site = RedisSite(
        "mg",
        "wiktionary",
        redis_client=SimpleNamespace(),
        rate_limiter=RecordingLimiter(),
    )

    assert en_site.wikimedia_site is not mg_site.wikimedia_site
    assert en_site.wikimedia_site is en_site.wikimedia_site
    assert mg_site.wikimedia_site is mg_site.wikimedia_site
    assert created == [("en", "wiktionary"), ("mg", "wiktionary")]
