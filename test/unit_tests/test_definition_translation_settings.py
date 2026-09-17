"""Tests for definition-translation settings validation and persistence."""
from __future__ import annotations

from typing import Any

import pytest
import redis

from api.services.definition_translation_settings import (
    DefinitionTranslationSettings,
    DefinitionTranslationSettingsStore,
    DefinitionTranslationSettingsStoreError,
    DefinitionTranslationSettingsValidationError,
)


class FakeRedis:
    """Minimal Redis test double for one settings value."""

    def __init__(self, value: Any = None) -> None:
        self.value = value

    def get(self, _key: str) -> Any:
        """Return the stored value."""
        return self.value

    def set(self, _key: str, value: str) -> None:
        """Store one value."""
        self.value = value


class FailingRedis(FakeRedis):
    """Redis test double that rejects all operations."""

    def get(self, _key: str) -> Any:
        """Fail reads."""
        raise redis.RedisError("offline")

    def set(self, _key: str, value: str) -> None:
        """Fail writes."""
        raise redis.RedisError("offline")


def test_settings_default_disabled_and_round_trip() -> None:
    """The Gemma gate is opt-in while NLLB round-trip validation defaults on."""
    redis_client = FakeRedis()
    store = DefinitionTranslationSettingsStore(redis_client=redis_client)

    assert store.get().serialise() == {
        "basic_english_gate_enabled": False,
        "nllb_roundtrip_validation_enabled": True,
    }
    store.set(
        DefinitionTranslationSettings(
            basic_english_gate_enabled=True,
            nllb_roundtrip_validation_enabled=False,
        )
    )
    assert store.get().serialise() == {
        "basic_english_gate_enabled": True,
        "nllb_roundtrip_validation_enabled": False,
    }


def test_settings_load_legacy_persisted_gate_with_roundtrip_enabled() -> None:
    """Existing one-flag Redis values retain the historical enabled default."""
    store = DefinitionTranslationSettingsStore(
        redis_client=FakeRedis('{"basic_english_gate_enabled": true}')
    )

    assert store.get().serialise() == {
        "basic_english_gate_enabled": True,
        "nllb_roundtrip_validation_enabled": True,
    }


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"basic_english_gate_enabled": 1},
        {
            "basic_english_gate_enabled": False,
            "nllb_roundtrip_validation_enabled": 1,
        },
        {"enabled": True},
    ],
)
def test_settings_reject_invalid_payloads(payload: Any) -> None:
    """Only the exact boolean API shape is accepted."""
    with pytest.raises(DefinitionTranslationSettingsValidationError):
        DefinitionTranslationSettings.from_payload(payload)


def test_settings_store_reports_invalid_data_and_redis_failures() -> None:
    """Invalid persisted data and unavailable Redis are authoritative errors."""
    with pytest.raises(DefinitionTranslationSettingsStoreError):
        DefinitionTranslationSettingsStore(redis_client=FakeRedis("{}")).get()
    with pytest.raises(DefinitionTranslationSettingsStoreError):
        DefinitionTranslationSettingsStore(redis_client=FailingRedis()).get()
    with pytest.raises(DefinitionTranslationSettingsStoreError):
        DefinitionTranslationSettingsStore(redis_client=FailingRedis()).set(
            DefinitionTranslationSettings()
        )
