"""Behavioral tests for protected deployment configuration validation."""

import configparser
from pathlib import Path

import pytest

from scripts.validate_config import validate_config

def _write_config(
    path: Path,
    overrides: dict[tuple[str, str], str | None] | None = None,
) -> None:
    """Write a valid baseline configuration with optional test mutations."""
    parser = configparser.ConfigParser(interpolation=None)
    parser.read_dict(
        {
            "rabbitmq": {
                "queue": "botjagwar",
                "page_check_queue": "translated",
                "page_check_review_queue": "page-check-review",
                "gateway_replay_ledger": "/var/lib/botjagwar/gateway.sqlite3",
                "gateway_hmac_secret": (
                    "gateway-secret-value-that-is-at-least-32-bytes"
                ),
            },
            "wiktionary_review": {"environment_id": "production-test"},
        }
    )
    for (section, key), value in (overrides or {}).items():
        if value is None:
            parser.remove_option(section, key)
        else:
            if not parser.has_section(section):
                parser.add_section(section)
            parser.set(section, key, value)
    with path.open("w", encoding="utf-8") as config_file:
        parser.write(config_file)


def test_valid_review_configuration_is_accepted(tmp_path: Path) -> None:
    config = tmp_path / "config.ini"
    _write_config(config)

    validate_config(config)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({("wiktionary_review", "environment_id"): "default"}, "environment_id"),
        ({("rabbitmq", "gateway_hmac_secret"): "short"}, "gateway_hmac_secret"),
        ({("rabbitmq", "page_check_queue"): "invalid queue"}, "queue names"),
        (
            {("rabbitmq", "page_check_review_queue"): "translated"},
            "queue roles",
        ),
        ({("rabbitmq", "gateway_replay_ledger"): "relative.sqlite3"}, "absolute"),
    ],
)
def test_invalid_security_contract_is_rejected(
    tmp_path: Path,
    overrides: dict[tuple[str, str], str | None],
    message: str,
) -> None:
    config = tmp_path / "config.ini"
    _write_config(config, overrides)

    with pytest.raises(ValueError, match=message):
        validate_config(config)


def test_environment_identity_is_optional_when_review_is_not_configured(
    tmp_path: Path,
) -> None:
    config = tmp_path / "config.ini"
    _write_config(
        config,
        {
            ("wiktionary_review", "environment_id"): None,
        },
    )

    validate_config(config)


def test_gateway_settings_are_optional_for_direct_amqp_installations(
    tmp_path: Path,
) -> None:
    config = tmp_path / "config.ini"
    _write_config(
        config,
        {
            ("rabbitmq", "gateway_replay_ledger"): None,
            ("rabbitmq", "gateway_hmac_secret"): None,
        },
    )

    validate_config(config)
