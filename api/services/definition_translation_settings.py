"""Redis persistence for definition-translation settings."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import redis

from api.config import BotjagwarConfig


class DefinitionTranslationSettingsStoreError(RuntimeError):
    """Raised when definition-translation settings cannot be read or written."""


class DefinitionTranslationSettingsValidationError(ValueError):
    """Raised when a definition-translation settings payload is invalid."""


@dataclass(frozen=True)
class DefinitionTranslationSettings:
    """Validated settings for definition translation."""

    basic_english_gate_enabled: bool = False
    nllb_roundtrip_validation_enabled: bool = True

    @classmethod
    def from_payload(
        cls,
        payload: Any,
        current: "DefinitionTranslationSettings | None" = None,
    ) -> "DefinitionTranslationSettings":
        """Build settings from the public payload or its legacy one-flag shape."""
        expected_keys = {
            "basic_english_gate_enabled",
            "nllb_roundtrip_validation_enabled",
        }
        payload_keys = set(payload) if isinstance(payload, dict) else set()
        if (
            not isinstance(payload, dict)
            or payload_keys not in (expected_keys, {"basic_english_gate_enabled"})
            or any(not isinstance(payload[key], bool) for key in payload_keys)
        ):
            raise DefinitionTranslationSettingsValidationError(
                "definition-translation settings must be booleans"
            )
        existing = current or cls()
        return cls(
            basic_english_gate_enabled=payload["basic_english_gate_enabled"],
            nllb_roundtrip_validation_enabled=payload.get(
                "nllb_roundtrip_validation_enabled",
                existing.nllb_roundtrip_validation_enabled,
            ),
        )

    def serialise(self) -> dict[str, bool]:
        """Return the public JSON-compatible settings shape."""
        return {
            "basic_english_gate_enabled": self.basic_english_gate_enabled,
            "nllb_roundtrip_validation_enabled": self.nllb_roundtrip_validation_enabled,
        }


class DefinitionTranslationSettingsStore:
    """Store definition-translation settings in authoritative Redis storage."""

    DEFAULT_KEY = "botjagwar:definition_translation:settings"

    def __init__(self, redis_client: Any = None, key: str = DEFAULT_KEY) -> None:
        """Initialize the store with an injectable Redis client."""
        self._redis_client = (
            redis_client if redis_client is not None else self._build_redis_client()
        )
        self._key = key

    def get(self) -> DefinitionTranslationSettings:
        """Return stored settings, or the defaults when absent."""
        try:
            raw_settings = self._redis_client.get(self._key)
        except redis.RedisError as exc:
            raise DefinitionTranslationSettingsStoreError(
                "Definition-translation settings could not be read from Redis."
            ) from exc
        if raw_settings is None:
            return DefinitionTranslationSettings()
        try:
            if isinstance(raw_settings, bytes):
                raw_settings = raw_settings.decode("utf-8")
            if not isinstance(raw_settings, str):
                raise TypeError("Redis settings values must be text")
            return DefinitionTranslationSettings.from_payload(json.loads(raw_settings))
        except (
            json.JSONDecodeError,
            DefinitionTranslationSettingsValidationError,
            TypeError,
            UnicodeDecodeError,
        ) as exc:
            raise DefinitionTranslationSettingsStoreError(
                "Definition-translation settings in Redis are invalid."
            ) from exc

    def set(self, settings: DefinitionTranslationSettings) -> None:
        """Replace the authoritative settings value in Redis."""
        if not isinstance(settings, DefinitionTranslationSettings):
            raise DefinitionTranslationSettingsStoreError(
                "Only validated definition-translation settings can be stored."
            )
        try:
            self._redis_client.set(
                self._key,
                json.dumps(settings.serialise()),
            )
        except redis.RedisError as exc:
            raise DefinitionTranslationSettingsStoreError(
                "Definition-translation settings could not be written to Redis."
            ) from exc

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
    "DefinitionTranslationSettings",
    "DefinitionTranslationSettingsStore",
    "DefinitionTranslationSettingsStoreError",
    "DefinitionTranslationSettingsValidationError",
]
