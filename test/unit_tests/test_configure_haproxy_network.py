"""Tests for source-restricted HAProxy frontend configuration."""

import pytest

from scripts.configure_haproxy_network import ACL_NAME, build_parser, configure_network


CONFIG = """frontend dictionary_front
    bind 127.0.0.1:8001
    default_backend dictionary_back

backend dictionary_back
    server dictionary1 127.0.0.1:28001 check

frontend unrelated
    bind 127.0.0.1:9999
"""


def test_configure_network_exposes_only_managed_frontends_to_atlas() -> None:
    """Configured API ports bind remotely but reject clients outside Atlas's source CIDR."""
    updated = configure_network(CONFIG, "192.168.1.155", "192.168.1.30")

    assert "bind 192.168.1.155:8001" in updated
    assert f"acl {ACL_NAME} src 192.168.1.30/32" in updated
    assert "192.168.1.30/32 127.0.0.0/8 ::1/128" in updated
    assert f"http-request deny unless {ACL_NAME}" in updated
    assert "bind 127.0.0.1:9999" in updated
    assert "server dictionary1 127.0.0.1:28001 check" in updated
    assert configure_network(updated, "192.168.1.155", "192.168.1.30") == updated


def test_configure_network_formats_ipv6_and_rejects_invalid_addresses() -> None:
    """IPv6 bind syntax is valid and malformed network input fails closed."""
    assert "bind [2001:db8::10]:8001" in configure_network(CONFIG, "2001:db8::10", "2001:db8:1::/64")
    with pytest.raises(ValueError):
        configure_network(CONFIG, "not-an-address", "192.168.1.30")


def test_remote_configuration_defaults_to_all_ipv4_interfaces() -> None:
    """Allowlisted remote access must not depend on one server interface address."""
    arguments = build_parser().parse_args(["--allow-source", "192.168.1.30/32"])

    assert arguments.bind_address == "0.0.0.0"
