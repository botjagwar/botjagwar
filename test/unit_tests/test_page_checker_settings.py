"""Tests for page-checker settings validation and Redis persistence."""
from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from typing import Any

import pytest

from api.services import page_checker_settings as settings_module
from api.services.page_checker_settings import (
    DEFAULT_JOB_HISTORY_LIMIT,
    DEFAULT_IGNORED_EDIT_SUMMARIES,
    MAX_COOLDOWN_SECONDS,
    MAX_JOB_HISTORY_LIMIT,
    PageCheckerSettings,
    PageCheckerSettingsStore,
    PageCheckerSettingsStoreError,
    PageCheckerSettingsValidationError,
    normalize_username,
)


VALID_PAYLOAD = {
    "watched_users": ["Bot-Jagwar"],
    "check_probability": 10,
    "cooldown_seconds": 5,
    "ignored_edit_summaries": list(DEFAULT_IGNORED_EDIT_SUMMARIES),
    "job_history_limit": DEFAULT_JOB_HISTORY_LIMIT,
    "autonomous_agent_enabled": False,
    "translation_prefilter_enabled": False,
}


class FakeRedis:
    """Minimal Redis string-value test double."""

    def __init__(self, value: Any = None) -> None:
        """Initialize the fake with an optional stored value."""
        self.values: dict[str, Any] = {}
        if value is not None:
            self.values[PageCheckerSettingsStore.DEFAULT_KEY] = value
        self.last_keys: tuple[str, ...] = ()

    def mget(self, keys: list[str]) -> list[Any]:
        """Return the current fake values."""
        self.last_keys = tuple(keys)
        return [self.values.get(key) for key in keys]

    def mset(self, values: dict[str, str]) -> None:
        """Replace the supplied fake values atomically."""
        self.last_keys = tuple(values)
        self.values.update(values)

    def set(self, key: str, value: str) -> None:
        """Replace one fake value."""
        self.last_keys = (key,)
        self.values[key] = value


class FailingRedis:
    """Redis test double that fails all settings operations."""

    def mget(self, _keys: list[str]) -> Any:
        """Fail a Redis read."""
        raise settings_module.redis.RedisError("down")

    def mset(self, _values: dict[str, str]) -> None:
        """Fail a Redis write."""
        raise settings_module.redis.RedisError("down")

    def set(self, _key: str, _value: str) -> None:
        """Fail a Redis write."""
        raise settings_module.redis.RedisError("down")


def test_settings_defaults_are_immutable_and_serialisable() -> None:
    """Defaults use the required JSON shape and cannot be mutated."""
    settings = PageCheckerSettings()

    assert settings.watched_users == ("Bot-Jagwar",)
    assert settings.ignored_edit_summaries == DEFAULT_IGNORED_EDIT_SUMMARIES
    assert settings.job_history_limit == 2_500
    assert settings.autonomous_agent_enabled is False
    assert settings.translation_prefilter_enabled is False
    assert settings.serialise() == VALID_PAYLOAD
    with pytest.raises(FrozenInstanceError):
        settings.check_probability = 20  # type: ignore[misc]


def test_settings_canonicalise_users_and_allow_an_empty_whitelist() -> None:
    """Equivalent usernames deduplicate without changing the first spelling."""
    settings = PageCheckerSettings.from_payload(
        {
            "watched_users": [
                " Bot_Jagwar ",
                "bot   Jagwar",
                "Alice__Smith",
                "alice Smith",
            ],
            "check_probability": 25.5,
            "cooldown_seconds": 0,
            "ignored_edit_summaries": [" skip this ", "skip this", "Keep, comma"],
            "job_history_limit": 100_000,
            "autonomous_agent_enabled": True,
            "translation_prefilter_enabled": True,
        }
    )

    assert normalize_username(" Bot_Jagwar ") == normalize_username("bot   Jagwar")
    assert settings.serialise() == {
        "watched_users": ["Bot_Jagwar", "Alice__Smith"],
        "check_probability": 25.5,
        "cooldown_seconds": 0,
        "ignored_edit_summaries": ["skip this", "Keep, comma"],
        "job_history_limit": 100_000,
        "autonomous_agent_enabled": True,
        "translation_prefilter_enabled": True,
    }
    assert PageCheckerSettings.from_payload(
        {
            "watched_users": [],
            "check_probability": 0,
            "cooldown_seconds": 0,
            "ignored_edit_summaries": [],
            "job_history_limit": 1,
            "autonomous_agent_enabled": False,
            "translation_prefilter_enabled": False,
        }
    ).serialise() == {
        "watched_users": [],
        "check_probability": 0,
        "cooldown_seconds": 0,
        "ignored_edit_summaries": [],
        "job_history_limit": 1,
        "autonomous_agent_enabled": False,
        "translation_prefilter_enabled": False,
    }


def test_username_normalization_preserves_case_after_the_first_character() -> None:
    """Distinct Wikimedia accounts are not merged by whole-name case folding."""
    settings = PageCheckerSettings(
        watched_users=("Bot-Jagwar", "Bot-jagwar"),
    )

    assert settings.watched_users == ("Bot-Jagwar", "Bot-jagwar")


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {
            "watched_users": ["Bot-Jagwar"],
            "check_probability": 10,
        },
        {**VALID_PAYLOAD, "unexpected": True},
        {**VALID_PAYLOAD, "watched_users": ("Bot-Jagwar",)},
        {**VALID_PAYLOAD, "watched_users": [" "]},
        {**VALID_PAYLOAD, "watched_users": ["___"]},
        {**VALID_PAYLOAD, "watched_users": [7]},
        {**VALID_PAYLOAD, "ignored_edit_summaries": ("summary",)},
        {**VALID_PAYLOAD, "ignored_edit_summaries": [" "]},
        {**VALID_PAYLOAD, "ignored_edit_summaries": [7]},
        {**VALID_PAYLOAD, "check_probability": True},
        {**VALID_PAYLOAD, "check_probability": "10"},
        {**VALID_PAYLOAD, "check_probability": float("nan")},
        {**VALID_PAYLOAD, "check_probability": float("inf")},
        {**VALID_PAYLOAD, "check_probability": -0.1},
        {**VALID_PAYLOAD, "check_probability": 100.1},
        {**VALID_PAYLOAD, "cooldown_seconds": False},
        {**VALID_PAYLOAD, "cooldown_seconds": float("nan")},
        {**VALID_PAYLOAD, "cooldown_seconds": float("inf")},
        {**VALID_PAYLOAD, "cooldown_seconds": -1},
        {**VALID_PAYLOAD, "cooldown_seconds": MAX_COOLDOWN_SECONDS + 0.1},
        {**VALID_PAYLOAD, "job_history_limit": True},
        {**VALID_PAYLOAD, "job_history_limit": 1.5},
        {**VALID_PAYLOAD, "job_history_limit": 0},
        {**VALID_PAYLOAD, "job_history_limit": MAX_JOB_HISTORY_LIMIT + 1},
        {**VALID_PAYLOAD, "autonomous_agent_enabled": 1},
        {**VALID_PAYLOAD, "autonomous_agent_enabled": "true"},
        {**VALID_PAYLOAD, "autonomous_agent_enabled": None},
        {**VALID_PAYLOAD, "translation_prefilter_enabled": 1},
    ],
)
def test_settings_reject_invalid_payloads(payload: Any) -> None:
    """Settings reject malformed fields, users, and numeric values."""
    with pytest.raises(PageCheckerSettingsValidationError):
        PageCheckerSettings.from_payload(payload)


def test_settings_value_rejects_non_sequence_users() -> None:
    """Direct settings construction cannot bypass field validation."""
    with pytest.raises(PageCheckerSettingsValidationError):
        PageCheckerSettings(watched_users="Bot-Jagwar")  # type: ignore[arg-type]
    with pytest.raises(PageCheckerSettingsValidationError):
        PageCheckerSettings(ignored_edit_summaries="summary")  # type: ignore[arg-type]
    with pytest.raises(PageCheckerSettingsValidationError):
        PageCheckerSettings(autonomous_agent_enabled=1)  # type: ignore[arg-type]


def test_store_returns_defaults_and_round_trips_canonical_settings() -> None:
    """A missing key returns defaults and a saved value remains canonical."""
    redis_client = FakeRedis()
    store = PageCheckerSettingsStore(redis_client=redis_client, key="settings-key")

    assert store.get() == PageCheckerSettings()

    settings = PageCheckerSettings.from_payload(
        {
            "watched_users": [" Bot_Jagwar ", "bot jagwar"],
            "check_probability": 50,
            "cooldown_seconds": 2.5,
            "ignored_edit_summaries": ["fanitsiana famaritana"],
            "job_history_limit": 4_000,
            "autonomous_agent_enabled": True,
            "translation_prefilter_enabled": True,
        }
    )
    store.set(settings)

    assert redis_client.last_keys == (
        "settings-key",
        "settings-key:autonomous_agent_enabled",
        "settings-key:job_history_limit",
        "settings-key:translation_prefilter_enabled",
    )
    stored_settings = redis_client.values["settings-key"]
    assert json.loads(stored_settings) == settings.serialise_monitoring()
    assert json.loads(
        redis_client.values["settings-key:autonomous_agent_enabled"]
    ) is True
    assert json.loads(redis_client.values["settings-key:job_history_limit"]) == 4_000
    assert json.loads(
        redis_client.values["settings-key:translation_prefilter_enabled"]
    ) is True
    redis_client.values["settings-key"] = stored_settings.encode("utf-8")
    assert store.get() == settings


def test_store_upgrades_settings_from_previous_schemas() -> None:
    """Existing Redis settings gain defaults for every newer field on read."""
    legacy_payload = {
        "watched_users": ["Alice"],
        "check_probability": 50,
        "cooldown_seconds": 7,
    }
    store = PageCheckerSettingsStore(
        redis_client=FakeRedis(json.dumps(legacy_payload))
    )

    assert store.get().serialise() == {
        **legacy_payload,
        "ignored_edit_summaries": list(DEFAULT_IGNORED_EDIT_SUMMARIES),
        "job_history_limit": DEFAULT_JOB_HISTORY_LIMIT,
        "autonomous_agent_enabled": False,
        "translation_prefilter_enabled": False,
    }

    previous_payload = {
        **legacy_payload,
        "ignored_edit_summaries": ["skip"],
    }
    store = PageCheckerSettingsStore(
        redis_client=FakeRedis(json.dumps(previous_payload))
    )

    assert store.get().serialise() == {
        **previous_payload,
        "job_history_limit": DEFAULT_JOB_HISTORY_LIMIT,
        "autonomous_agent_enabled": False,
        "translation_prefilter_enabled": False,
    }


def test_store_reads_the_autonomous_agent_flag_from_its_rollback_safe_key() -> None:
    """The new flag does not change the legacy Redis settings document."""
    redis_client = FakeRedis()
    redis_client.values[PageCheckerSettingsStore.DEFAULT_KEY] = json.dumps(
        {
            key: value
            for key, value in VALID_PAYLOAD.items()
            if key
            not in {
                "autonomous_agent_enabled",
                "job_history_limit",
                "translation_prefilter_enabled",
            }
        }
    )
    redis_client.values[
        PageCheckerSettingsStore.DEFAULT_AUTONOMOUS_AGENT_KEY
    ] = json.dumps(True)

    settings = PageCheckerSettingsStore(redis_client=redis_client).get()

    assert settings.autonomous_agent_enabled is True


def test_store_updates_monitoring_and_autonomy_independently() -> None:
    """Field-specific writes cannot overwrite the other settings boundary."""
    redis_client = FakeRedis()
    store = PageCheckerSettingsStore(redis_client=redis_client)
    store.set(PageCheckerSettings(autonomous_agent_enabled=True))
    autonomous_value = redis_client.values[
        PageCheckerSettingsStore.DEFAULT_AUTONOMOUS_AGENT_KEY
    ]

    store.set_monitoring(PageCheckerSettings(check_probability=35))

    assert redis_client.values[
        PageCheckerSettingsStore.DEFAULT_AUTONOMOUS_AGENT_KEY
    ] == autonomous_value
    assert store.get().check_probability == 35
    assert store.get().autonomous_agent_enabled is True

    monitoring_value = redis_client.values[PageCheckerSettingsStore.DEFAULT_KEY]
    store.set_autonomous_agent_enabled(False)

    assert redis_client.values[PageCheckerSettingsStore.DEFAULT_KEY] == monitoring_value
    assert store.get().autonomous_agent_enabled is False

    store.set_job_history_limit(7_500)

    assert redis_client.values[PageCheckerSettingsStore.DEFAULT_KEY] == monitoring_value
    assert store.get().job_history_limit == 7_500

    store.set_translation_prefilter_enabled(True)

    assert redis_client.values[PageCheckerSettingsStore.DEFAULT_KEY] == monitoring_value
    assert store.get().translation_prefilter_enabled is True


@pytest.mark.parametrize("raw_setting", ["1", '"true"', "null", "{"])
def test_store_rejects_an_invalid_autonomous_agent_value(raw_setting: str) -> None:
    """A malformed separate flag is authoritative and fails closed."""
    redis_client = FakeRedis()
    redis_client.values[
        PageCheckerSettingsStore.DEFAULT_AUTONOMOUS_AGENT_KEY
    ] = raw_setting
    store = PageCheckerSettingsStore(redis_client=redis_client)

    with pytest.raises(PageCheckerSettingsStoreError):
        store.get()


@pytest.mark.parametrize("raw_setting", ["true", "0", "1.5", "100001", "{"])
def test_store_rejects_an_invalid_job_history_limit(raw_setting: str) -> None:
    """The separate history setting must be an integer in the public range."""
    redis_client = FakeRedis()
    redis_client.values[
        PageCheckerSettingsStore.DEFAULT_JOB_HISTORY_LIMIT_KEY
    ] = raw_setting
    store = PageCheckerSettingsStore(redis_client=redis_client)

    with pytest.raises(PageCheckerSettingsStoreError):
        store.get()


@pytest.mark.parametrize("raw_setting", ["1", '"true"', "null", "{"])
def test_store_rejects_an_invalid_translation_prefilter(raw_setting: str) -> None:
    """The separate prefilter setting must be a boolean."""
    redis_client = FakeRedis()
    redis_client.values[
        PageCheckerSettingsStore.DEFAULT_TRANSLATION_PREFILTER_KEY
    ] = raw_setting
    store = PageCheckerSettingsStore(redis_client=redis_client)

    with pytest.raises(PageCheckerSettingsStoreError):
        store.get()


@pytest.mark.parametrize(
    "raw_settings",
    [
        "{",
        "[]",
        json.dumps({"watched_users": []}),
        json.dumps({**VALID_PAYLOAD, "check_probability": True}),
        json.dumps({**VALID_PAYLOAD, "autonomous_agent_enabled": 1}),
        b"\xff",
        42,
    ],
)
def test_store_rejects_unparseable_or_invalid_redis_data(raw_settings: Any) -> None:
    """Stored settings must decode and satisfy the complete settings contract."""
    store = PageCheckerSettingsStore(redis_client=FakeRedis(raw_settings))

    with pytest.raises(PageCheckerSettingsStoreError):
        store.get()


def test_store_raises_focused_errors_without_a_local_fallback() -> None:
    """Redis read and write failures surface as settings-store errors."""
    store = PageCheckerSettingsStore(redis_client=FailingRedis())

    with pytest.raises(PageCheckerSettingsStoreError):
        store.get()
    with pytest.raises(PageCheckerSettingsStoreError):
        store.set(PageCheckerSettings())
    with pytest.raises(PageCheckerSettingsStoreError):
        store.set_monitoring(PageCheckerSettings())
    with pytest.raises(PageCheckerSettingsStoreError):
        store.set_autonomous_agent_enabled(True)
    with pytest.raises(PageCheckerSettingsStoreError):
        store.set_job_history_limit(2_500)
    with pytest.raises(PageCheckerSettingsStoreError):
        store.set_translation_prefilter_enabled(True)
    with pytest.raises(PageCheckerSettingsStoreError):
        store.set(VALID_PAYLOAD)  # type: ignore[arg-type]


def test_store_wraps_serialization_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unexpected serialization failures remain focused store errors."""
    store = PageCheckerSettingsStore(redis_client=FakeRedis())

    def invalid_serialise(_settings: PageCheckerSettings) -> dict[str, float]:
        """Return a value forbidden by the strict JSON serializer."""
        return {"invalid": float("nan")}

    monkeypatch.setattr(
        PageCheckerSettings,
        "serialise_monitoring",
        invalid_serialise,
    )

    with pytest.raises(PageCheckerSettingsStoreError):
        store.set(PageCheckerSettings())


def test_store_builds_client_from_botjagwar_redis_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The default client uses the configured Redis host and optional password."""
    sentinel = object()
    redis_arguments: dict[str, Any] = {}

    class FakeConfig:
        """Return deterministic Redis configuration for this test."""

        def get(self, key: str, section: str = "global") -> str:
            """Return a configured value by section and key."""
            assert section == "redis"
            return {"host": "redis.internal", "password": "secret"}[key]

    def build_fake_redis(**kwargs: Any) -> object:
        """Capture Redis constructor arguments without opening a connection."""
        redis_arguments.update(kwargs)
        return sentinel

    monkeypatch.setattr(settings_module, "BotjagwarConfig", FakeConfig)
    monkeypatch.setattr(settings_module.redis, "Redis", build_fake_redis)

    store = PageCheckerSettingsStore()

    assert store._redis_client is sentinel
    assert redis_arguments == {
        "host": "redis.internal",
        "port": 6379,
        "password": "secret",
        "socket_timeout": 3,
    }
