"""Validation and Redis persistence for page-checker automation settings."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, replace
from typing import Any, Dict, Tuple, Union

import redis

from api.config import BotjagwarConfig


Numeric = Union[int, float]
MAX_COOLDOWN_SECONDS = 86_400
DEFAULT_JOB_HISTORY_LIMIT = 2_500
MAX_JOB_HISTORY_LIMIT = 100_000
DEFAULT_IGNORED_EDIT_SUMMARIES = (
    "fanitsiana famaritana",
    "Dikanteny: es",
)
_LEGACY_SETTINGS_FIELDS = {
    "watched_users",
    "check_probability",
    "cooldown_seconds",
}
_PREVIOUS_SETTINGS_FIELDS = {
    *_LEGACY_SETTINGS_FIELDS,
    "ignored_edit_summaries",
}
_SETTINGS_FIELDS = {
    *_PREVIOUS_SETTINGS_FIELDS,
    "job_history_limit",
    "autonomous_agent_enabled",
    "translation_prefilter_enabled",
}


class PageCheckerSettingsValidationError(ValueError):
    """Raised when a page-checker settings payload is invalid."""


class PageCheckerSettingsStoreError(RuntimeError):
    """Raised when authoritative page-checker settings cannot be read or written."""


def normalize_username(username: str) -> str:
    """Return a MediaWiki username key with canonical separators and first case."""
    normalized = " ".join(username.replace("_", " ").split())
    return normalized[:1].upper() + normalized[1:]


def _canonical_users(users: object) -> Tuple[str, ...]:
    """Validate users and preserve the first spelling of equivalent names."""
    if not isinstance(users, (list, tuple)):
        raise PageCheckerSettingsValidationError(
            "watched_users must be a list of usernames"
        )

    canonical_users = []
    seen = set()
    for user in users:
        if not isinstance(user, str):
            raise PageCheckerSettingsValidationError(
                "watched_users must contain only strings"
            )
        display_name = user.strip()
        normalized_name = normalize_username(display_name)
        if not display_name or not normalized_name:
            raise PageCheckerSettingsValidationError(
                "watched_users must not contain blank usernames"
            )
        if normalized_name not in seen:
            canonical_users.append(display_name)
            seen.add(normalized_name)
    return tuple(canonical_users)


def _canonical_summaries(summaries: object) -> Tuple[str, ...]:
    """Validate edit summaries and preserve unique exact matches in order."""
    if not isinstance(summaries, (list, tuple)):
        raise PageCheckerSettingsValidationError(
            "ignored_edit_summaries must be a list of summaries"
        )

    canonical_summaries = []
    seen = set()
    for summary in summaries:
        if not isinstance(summary, str):
            raise PageCheckerSettingsValidationError(
                "ignored_edit_summaries must contain only strings"
            )
        canonical_summary = summary.strip()
        if not canonical_summary:
            raise PageCheckerSettingsValidationError(
                "ignored_edit_summaries must not contain blank summaries"
            )
        if canonical_summary not in seen:
            canonical_summaries.append(canonical_summary)
            seen.add(canonical_summary)
    return tuple(canonical_summaries)


def _validate_number(
    value: object,
    field: str,
    minimum: Numeric,
    maximum: Numeric | None = None,
) -> None:
    """Validate one finite, non-boolean numeric settings field."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PageCheckerSettingsValidationError(f"{field} must be a number")
    if isinstance(value, float) and not math.isfinite(value):
        raise PageCheckerSettingsValidationError(f"{field} must be finite")
    if value < minimum or (maximum is not None and value > maximum):
        raise PageCheckerSettingsValidationError(f"{field} is out of range")


def _decode_redis_json(value: Any) -> Any:
    """Decode one JSON value returned by Redis."""
    if isinstance(value, bytes):
        encoded_value = value.decode("utf-8")
    elif isinstance(value, str):
        encoded_value = value
    else:
        raise TypeError("Redis settings values must be text")
    return json.loads(encoded_value)


@dataclass(frozen=True)
class PageCheckerSettings:
    """Immutable, validated page-checker automation settings."""

    watched_users: Tuple[str, ...] = ("Bot-Jagwar",)
    check_probability: Numeric = 10
    cooldown_seconds: Numeric = 5
    ignored_edit_summaries: Tuple[str, ...] = DEFAULT_IGNORED_EDIT_SUMMARIES
    job_history_limit: int = DEFAULT_JOB_HISTORY_LIMIT
    autonomous_agent_enabled: bool = False
    translation_prefilter_enabled: bool = False

    def __post_init__(self) -> None:
        """Validate and canonicalize values supplied to the settings object."""
        object.__setattr__(self, "watched_users", _canonical_users(self.watched_users))
        object.__setattr__(
            self,
            "ignored_edit_summaries",
            _canonical_summaries(self.ignored_edit_summaries),
        )
        _validate_number(
            self.check_probability,
            "check_probability",
            minimum=0,
            maximum=100,
        )
        _validate_number(
            self.cooldown_seconds,
            "cooldown_seconds",
            minimum=0,
            maximum=MAX_COOLDOWN_SECONDS,
        )
        _validate_number(
            self.job_history_limit,
            "job_history_limit",
            minimum=1,
            maximum=MAX_JOB_HISTORY_LIMIT,
        )
        if not isinstance(self.job_history_limit, int):
            raise PageCheckerSettingsValidationError(
                "job_history_limit must be an integer"
            )
        if not isinstance(self.autonomous_agent_enabled, bool):
            raise PageCheckerSettingsValidationError(
                "autonomous_agent_enabled must be a boolean"
            )
        if not isinstance(self.translation_prefilter_enabled, bool):
            raise PageCheckerSettingsValidationError(
                "translation_prefilter_enabled must be a boolean"
            )

    @classmethod
    def from_payload(cls, payload: Any) -> "PageCheckerSettings":
        """Build settings from an object containing exactly the public fields."""
        if not isinstance(payload, dict):
            raise PageCheckerSettingsValidationError(
                "settings payload must be an object"
            )
        if set(payload) != _SETTINGS_FIELDS:
            raise PageCheckerSettingsValidationError(
                "settings payload must contain exactly the supported fields"
            )
        return cls.from_monitoring_payload(
            {
                key: value
                for key, value in payload.items()
                if key
                not in {
                    "autonomous_agent_enabled",
                    "job_history_limit",
                    "translation_prefilter_enabled",
                }
            },
            job_history_limit=payload["job_history_limit"],
            autonomous_agent_enabled=payload["autonomous_agent_enabled"],
            translation_prefilter_enabled=payload["translation_prefilter_enabled"],
        )

    @classmethod
    def from_monitoring_payload(
        cls,
        payload: Any,
        *,
        job_history_limit: int = DEFAULT_JOB_HISTORY_LIMIT,
        autonomous_agent_enabled: bool = False,
        translation_prefilter_enabled: bool = False,
    ) -> "PageCheckerSettings":
        """Build settings from the rollback-compatible monitoring fields."""
        if not isinstance(payload, dict) or set(payload) != _PREVIOUS_SETTINGS_FIELDS:
            raise PageCheckerSettingsValidationError(
                "settings payload must contain exactly the monitoring fields"
            )
        if not isinstance(payload["watched_users"], list):
            raise PageCheckerSettingsValidationError(
                "watched_users must be a list of usernames"
            )
        if not isinstance(payload["ignored_edit_summaries"], list):
            raise PageCheckerSettingsValidationError(
                "ignored_edit_summaries must be a list of summaries"
            )
        return cls(
            watched_users=tuple(payload["watched_users"]),
            check_probability=payload["check_probability"],
            cooldown_seconds=payload["cooldown_seconds"],
            ignored_edit_summaries=tuple(payload["ignored_edit_summaries"]),
            job_history_limit=job_history_limit,
            autonomous_agent_enabled=autonomous_agent_enabled,
            translation_prefilter_enabled=translation_prefilter_enabled,
        )

    @classmethod
    def from_stored_payload(cls, payload: Any) -> "PageCheckerSettings":
        """Build settings while upgrading the previous persisted schema."""
        if isinstance(payload, dict) and set(payload) == _LEGACY_SETTINGS_FIELDS:
            payload = {
                **payload,
                "ignored_edit_summaries": list(DEFAULT_IGNORED_EDIT_SUMMARIES),
            }
        return cls.from_monitoring_payload(payload)

    def serialise(self) -> Dict[str, Any]:
        """Return the canonical JSON-compatible settings shape."""
        return {
            **self.serialise_monitoring(),
            "job_history_limit": self.job_history_limit,
            "autonomous_agent_enabled": self.autonomous_agent_enabled,
            "translation_prefilter_enabled": self.translation_prefilter_enabled,
        }

    def serialise_monitoring(self) -> Dict[str, Any]:
        """Return fields understood by previous Botjagwar releases."""
        return {
            "watched_users": list(self.watched_users),
            "check_probability": self.check_probability,
            "cooldown_seconds": self.cooldown_seconds,
            "ignored_edit_summaries": list(self.ignored_edit_summaries),
        }


class PageCheckerSettingsStore:
    """Store page-checker settings in authoritative Redis storage."""

    DEFAULT_KEY = "botjagwar:page_checker:settings"
    DEFAULT_AUTONOMOUS_AGENT_KEY = (
        "botjagwar:page_checker:autonomous_agent_enabled"
    )
    DEFAULT_JOB_HISTORY_LIMIT_KEY = "botjagwar:page_checker:job_history_limit"
    DEFAULT_TRANSLATION_PREFILTER_KEY = (
        "botjagwar:page_checker:translation_prefilter_enabled"
    )

    def __init__(
        self,
        redis_client: Any = None,
        key: str = DEFAULT_KEY,
        autonomous_agent_key: str | None = None,
        job_history_limit_key: str | None = None,
        translation_prefilter_key: str | None = None,
    ) -> None:
        """Initialize the store with an injectable Redis client."""
        self._redis_client = (
            redis_client if redis_client is not None else self._build_redis_client()
        )
        self._key = key
        self._autonomous_agent_key = autonomous_agent_key or (
            self.DEFAULT_AUTONOMOUS_AGENT_KEY
            if key == self.DEFAULT_KEY
            else f"{key}:autonomous_agent_enabled"
        )
        self._job_history_limit_key = job_history_limit_key or (
            self.DEFAULT_JOB_HISTORY_LIMIT_KEY
            if key == self.DEFAULT_KEY
            else f"{key}:job_history_limit"
        )
        self._translation_prefilter_key = translation_prefilter_key or (
            self.DEFAULT_TRANSLATION_PREFILTER_KEY
            if key == self.DEFAULT_KEY
            else f"{key}:translation_prefilter_enabled"
        )

    def get(self) -> PageCheckerSettings:
        """Return stored settings, or defaults when the Redis key is absent."""
        try:
            (
                raw_settings,
                raw_autonomous_agent,
                raw_job_history_limit,
                raw_translation_prefilter,
            ) = (
                self._redis_client.mget(
                    [
                        self._key,
                        self._autonomous_agent_key,
                        self._job_history_limit_key,
                        self._translation_prefilter_key,
                    ]
                )
            )
        except redis.RedisError as exc:
            raise PageCheckerSettingsStoreError(
                "Page-checker settings could not be read from Redis."
            ) from exc

        try:
            settings = (
                PageCheckerSettings()
                if raw_settings is None
                else PageCheckerSettings.from_stored_payload(
                    _decode_redis_json(raw_settings)
                )
            )
            autonomous_agent_enabled = settings.autonomous_agent_enabled
            if raw_autonomous_agent is not None:
                autonomous_agent_enabled = _decode_redis_json(raw_autonomous_agent)
                if not isinstance(autonomous_agent_enabled, bool):
                    raise TypeError("Autonomous-agent setting must be a boolean")
            job_history_limit = settings.job_history_limit
            if raw_job_history_limit is not None:
                job_history_limit = _decode_redis_json(raw_job_history_limit)
            translation_prefilter_enabled = settings.translation_prefilter_enabled
            if raw_translation_prefilter is not None:
                translation_prefilter_enabled = _decode_redis_json(
                    raw_translation_prefilter
                )
                if not isinstance(translation_prefilter_enabled, bool):
                    raise TypeError("Translation-prefilter setting must be a boolean")
            return replace(
                settings,
                autonomous_agent_enabled=autonomous_agent_enabled,
                job_history_limit=job_history_limit,
                translation_prefilter_enabled=translation_prefilter_enabled,
            )
        except (
            json.JSONDecodeError,
            PageCheckerSettingsValidationError,
            TypeError,
            UnicodeDecodeError,
        ) as exc:
            raise PageCheckerSettingsStoreError(
                "Page-checker settings in Redis are invalid."
            ) from exc

    def set(self, settings: PageCheckerSettings) -> None:
        """Replace the authoritative settings value in Redis."""
        if not isinstance(settings, PageCheckerSettings):
            raise PageCheckerSettingsStoreError(
                "Only validated page-checker settings can be stored."
            )
        try:
            payload = self._serialize_monitoring_settings(settings)
            autonomous_agent_payload = json.dumps(
                settings.autonomous_agent_enabled,
                allow_nan=False,
            )
            job_history_limit_payload = json.dumps(
                settings.job_history_limit,
                allow_nan=False,
            )
            translation_prefilter_payload = json.dumps(
                settings.translation_prefilter_enabled,
                allow_nan=False,
            )
            self._redis_client.mset(
                {
                    self._key: payload,
                    self._autonomous_agent_key: autonomous_agent_payload,
                    self._job_history_limit_key: job_history_limit_payload,
                    self._translation_prefilter_key: translation_prefilter_payload,
                }
            )
        except redis.RedisError as exc:
            raise PageCheckerSettingsStoreError(
                "Page-checker settings could not be written to Redis."
            ) from exc
        except (KeyError, TypeError, ValueError) as exc:
            raise PageCheckerSettingsStoreError(
                "Page-checker settings could not be serialized."
            ) from exc

    def set_monitoring(self, settings: PageCheckerSettings) -> None:
        """Replace monitoring fields without changing autonomous assignment."""
        if not isinstance(settings, PageCheckerSettings):
            raise PageCheckerSettingsStoreError(
                "Only validated page-checker settings can be stored."
            )
        try:
            self._redis_client.set(
                self._key,
                self._serialize_monitoring_settings(settings),
            )
        except redis.RedisError as exc:
            raise PageCheckerSettingsStoreError(
                "Page-checker monitoring settings could not be written to Redis."
            ) from exc
        except (KeyError, TypeError, ValueError) as exc:
            raise PageCheckerSettingsStoreError(
                "Page-checker monitoring settings could not be serialized."
            ) from exc

    def set_autonomous_agent_enabled(self, enabled: bool) -> None:
        """Replace only the autonomous-agent flag."""
        if not isinstance(enabled, bool):
            raise PageCheckerSettingsStoreError(
                "The autonomous-agent setting must be a boolean."
            )
        try:
            self._redis_client.set(
                self._autonomous_agent_key,
                json.dumps(enabled),
            )
        except redis.RedisError as exc:
            raise PageCheckerSettingsStoreError(
                "The autonomous-agent setting could not be written to Redis."
            ) from exc

    def set_job_history_limit(self, limit: int) -> None:
        """Replace only the number of jobs exposed in history and statistics."""
        try:
            settings = PageCheckerSettings(job_history_limit=limit)
            self._redis_client.set(
                self._job_history_limit_key,
                json.dumps(settings.job_history_limit),
            )
        except PageCheckerSettingsValidationError as exc:
            raise PageCheckerSettingsStoreError(
                "The job-history limit is invalid."
            ) from exc
        except redis.RedisError as exc:
            raise PageCheckerSettingsStoreError(
                "The job-history limit could not be written to Redis."
            ) from exc

    def set_translation_prefilter_enabled(self, enabled: bool) -> None:
        """Replace only the translated-page prefilter flag."""
        if not isinstance(enabled, bool):
            raise PageCheckerSettingsStoreError(
                "The translation-prefilter setting must be a boolean."
            )
        try:
            self._redis_client.set(
                self._translation_prefilter_key,
                json.dumps(enabled),
            )
        except redis.RedisError as exc:
            raise PageCheckerSettingsStoreError(
                "The translation-prefilter setting could not be written to Redis."
            ) from exc

    @staticmethod
    def _serialize_monitoring_settings(settings: PageCheckerSettings) -> str:
        """Serialize only fields understood by previous Botjagwar releases."""
        return json.dumps(settings.serialise_monitoring(), allow_nan=False)

    @staticmethod
    def _build_redis_client() -> Any:
        """Build a lazy Redis client from Botjagwar configuration."""
        config = BotjagwarConfig()
        password = config.get("password", "redis") or None
        return redis.Redis(
            host=config.get("host", "redis"),
            port=6379,
            password=password,
            socket_timeout=3,
        )


__all__ = [
    "DEFAULT_JOB_HISTORY_LIMIT",
    "DEFAULT_IGNORED_EDIT_SUMMARIES",
    "MAX_COOLDOWN_SECONDS",
    "MAX_JOB_HISTORY_LIMIT",
    "PageCheckerSettings",
    "PageCheckerSettingsStore",
    "PageCheckerSettingsStoreError",
    "PageCheckerSettingsValidationError",
    "normalize_username",
]
