"""Tests for declarative deployment configuration."""

from pathlib import Path

import pytest

from scripts.deployment_config import DeploymentConfig, resolved_deployment_config


def test_default_deployment_policy_keeps_five_releases() -> None:
    """Fresh installations retain five releases unless explicitly overridden."""
    resolved = resolved_deployment_config({}, "botjagwar", "botjagwar")

    assert resolved.keep_releases == 5


def test_manifest_round_trip_preserves_deployment_policy(tmp_path: Path) -> None:
    """A written manifest can be loaded without losing typed values."""
    path = tmp_path / "deployment.ini"
    expected = DeploymentConfig(
        service_user="botjagwar",
        service_group="services",
        instance_counts={
            "dictionary_service": 2,
            "entry_translator": 3,
            "postgrest": 4,
            "translator": 1,
        },
        autostart=False,
        keep_releases=5,
        haproxy_bind_address="192.0.2.10",
        haproxy_allowed_sources=("192.0.2.20/32", "2001:db8::/64"),
    )

    expected.write(path)

    assert DeploymentConfig.load(path) == expected
    assert path.stat().st_mode & 0o777 == 0o600


def test_existing_manifest_is_preserved_and_environment_is_explicit_override(tmp_path: Path) -> None:
    """Reinstalls retain policy except for values explicitly supplied by operators."""
    path = tmp_path / "deployment.ini"
    original = DeploymentConfig(
        service_user="deployer",
        service_group="deployer",
        instance_counts={
            "dictionary_service": 8,
            "entry_translator": 9,
            "postgrest": 7,
            "translator": 2,
        },
        keep_releases=4,
        haproxy_bind_address="192.0.2.10",
        haproxy_allowed_sources=("192.0.2.20/32",),
    )
    original.write(path)

    resolved = resolved_deployment_config(
        {"POSTGREST_INSTANCES": "5"}, "ignored", "ignored", current_path=path
    )

    assert resolved.service_user == "deployer"
    assert resolved.instance_counts == {
        "dictionary_service": 8,
        "entry_translator": 9,
        "postgrest": 5,
        "translator": 2,
    }
    assert resolved.haproxy_allowed_sources == ("192.0.2.20/32",)


def test_legacy_haproxy_network_policy_is_migrated(tmp_path: Path) -> None:
    """The first manifest retains an existing bind address and source ACL."""
    haproxy = tmp_path / "haproxy.cfg"
    haproxy.write_text(
        "frontend dictionary_front\n"
        "    bind 192.0.2.10:8001\n"
        "    acl atlas_backend_source src 192.0.2.20/32 2001:db8::/64\n",
        encoding="utf-8",
    )

    resolved = resolved_deployment_config({}, "bot", "bot", existing_haproxy_path=haproxy)

    assert resolved.haproxy_bind_address == "192.0.2.10"
    assert resolved.haproxy_allowed_sources == ("192.0.2.20/32", "2001:db8::/64")


@pytest.mark.parametrize(
    ("environment", "message"),
    [
        ({"BOTJAGWAR_KEEP_RELEASES": "1"}, "BOTJAGWAR_KEEP_RELEASES"),
        ({"HAPROXY_BIND_ADDRESS": "host.example"}, "bind address"),
        ({"HAPROXY_ALLOWED_SOURCES": "everyone"}, "allowed source"),
    ],
)
def test_invalid_deployment_policy_is_rejected(environment: dict[str, str], message: str) -> None:
    """Invalid policy fails before any service configuration is generated."""
    with pytest.raises(ValueError, match=message):
        resolved_deployment_config(environment, "bot", "bot")
