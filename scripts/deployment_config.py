#!/usr/bin/env python3
"""Read and write declarative Botjagwar deployment configuration."""

from __future__ import annotations

import configparser
import io
import ipaddress
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


DEFAULT_INSTANCE_COUNTS = {
    "dictionary_service": 6,
    "entry_translator": 10,
    "postgrest": 10,
    "translator": 3,
}
INSTANCE_ENVIRONMENT_VARIABLES = {
    "dictionary_service": "DICTIONARY_SERVICE_INSTANCES",
    "entry_translator": "ENTRY_TRANSLATOR_INSTANCES",
    "postgrest": "POSTGREST_INSTANCES",
    "translator": "TRANSLATOR_INSTANCES",
}
MAX_INSTANCE_COUNTS = {
    "dictionary_service": 1000,
    "entry_translator": 1000,
    "postgrest": 16,
    "translator": 4,
}
LOCAL_HEALTHCHECK_SOURCES = ("127.0.0.0/8", "::1/128")


def atomic_write_text(path: Path, content: str, mode: int = 0o600) -> None:
    """Atomically write text content to a path with a fixed mode."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as temporary_file:
            temporary_file.write(content)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.chmod(temporary_name, mode)
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


@dataclass(frozen=True)
class DeploymentConfig:
    """Values that determine generated services and release retention."""

    service_user: str
    service_group: str
    instance_counts: dict[str, int]
    autostart: bool = True
    keep_releases: int = 5
    haproxy_bind_address: str = "127.0.0.1"
    haproxy_allowed_sources: tuple[str, ...] = ()

    @classmethod
    def load(cls, path: Path) -> DeploymentConfig:
        """Load and validate a deployment manifest from disk."""
        parser = configparser.ConfigParser(interpolation=None)
        if not parser.read(path, encoding="utf-8"):
            raise ValueError(f"Unable to read deployment configuration {path}.")
        try:
            counts = {
                service: _validated_count(service, parser.getint("services", service))
                for service in DEFAULT_INSTANCE_COUNTS
            }
            allowed_sources = _validated_sources(parser.get("haproxy", "allowed_sources", fallback=""))
            return cls(
                service_user=parser.get("deployment", "service_user"),
                service_group=parser.get("deployment", "service_group"),
                instance_counts=counts,
                autostart=parser.getboolean("services", "autostart"),
                keep_releases=_validated_keep_releases(parser.getint("deployment", "keep_releases")),
                haproxy_bind_address=_validated_address(parser.get("haproxy", "bind_address")),
                haproxy_allowed_sources=allowed_sources,
            )
        except (configparser.Error, KeyError, ValueError) as error:
            raise ValueError(f"Invalid deployment configuration {path}: {error}") from error

    def write(self, path: Path) -> None:
        """Atomically write this deployment manifest."""
        if path.is_symlink():
            path = path.resolve(strict=True)
        parser = configparser.ConfigParser(interpolation=None)
        parser["deployment"] = {
            "schema_version": "1",
            "service_user": self.service_user,
            "service_group": self.service_group,
            "keep_releases": str(self.keep_releases),
        }
        parser["services"] = {
            **{service: str(self.instance_counts[service]) for service in DEFAULT_INSTANCE_COUNTS},
            "autostart": "true" if self.autostart else "false",
        }
        parser["haproxy"] = {
            "bind_address": self.haproxy_bind_address,
            "allowed_sources": ",".join(self.haproxy_allowed_sources),
        }
        with io.StringIO() as buffer:
            parser.write(buffer)
            atomic_write_text(path, buffer.getvalue())


def configured_instance_counts(paths: list[Path]) -> dict[str, int]:
    """Discover existing generated service counts from Supervisor sections."""
    counts: dict[str, int] = {}
    pattern = re.compile(r"^\[program:(dictionary_service|entry_translator|postgrest|translator)_(\d+)]$")
    for path in paths:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            match = pattern.fullmatch(line.strip())
            if match:
                service, index = match.groups()
                count = int(index) - (1 if service == "postgrest" else 0)
                counts[service] = max(counts.get(service, 0), count)
    return counts


def instance_counts(environment: Mapping[str, str], existing: Mapping[str, int] | None = None) -> dict[str, int]:
    """Read and validate service instance counts from environment variables."""
    counts: dict[str, int] = {}
    existing = existing or {}
    for service, default in DEFAULT_INSTANCE_COUNTS.items():
        variable = INSTANCE_ENVIRONMENT_VARIABLES[service]
        value = environment.get(variable, str(existing.get(service, default)))
        try:
            count = int(value)
        except ValueError:
            raise ValueError(f"{variable} must be an integer, got {value!r}.") from None
        counts[service] = _validated_count(service, count, variable)
    return counts


def resolved_deployment_config(
    environment: Mapping[str, str],
    user: str,
    group: str,
    current_path: Path | None = None,
    existing_supervisor_paths: list[Path] | None = None,
    existing_haproxy_path: Path | None = None,
) -> DeploymentConfig:
    """Resolve a manifest from persisted values, legacy files, and explicit overrides."""
    current = DeploymentConfig.load(current_path) if current_path and current_path.exists() else None
    discovered_counts = current.instance_counts if current else configured_instance_counts(existing_supervisor_paths or [])
    bind_address, allowed_sources = _existing_haproxy_network(existing_haproxy_path)
    if current:
        bind_address = current.haproxy_bind_address
        allowed_sources = current.haproxy_allowed_sources

    if environment.get("REGENERATE_HAPROXY") == "1":
        bind_address, allowed_sources = "127.0.0.1", ()
    bind_address = _validated_address(environment.get("HAPROXY_BIND_ADDRESS", bind_address))
    allowed_sources = _validated_sources(
        environment.get("HAPROXY_ALLOWED_SOURCES", ",".join(allowed_sources))
    )
    autostart = current.autostart if current else True
    if "NO_AUTOSTART" in environment:
        autostart = environment["NO_AUTOSTART"] != "1"

    keep_releases_value = environment.get(
        "BOTJAGWAR_KEEP_RELEASES", str(current.keep_releases if current else 5)
    )
    try:
        keep_releases = _validated_keep_releases(int(keep_releases_value))
    except ValueError:
        raise ValueError(
            f"BOTJAGWAR_KEEP_RELEASES must be an integer between 2 and 20, got {keep_releases_value!r}."
        ) from None

    return DeploymentConfig(
        service_user=environment.get("BOTJAGWAR_SERVICE_USER", current.service_user if current else user),
        service_group=environment.get("BOTJAGWAR_SERVICE_GROUP", current.service_group if current else group),
        instance_counts=instance_counts(environment, discovered_counts),
        autostart=autostart,
        keep_releases=keep_releases,
        haproxy_bind_address=bind_address,
        haproxy_allowed_sources=allowed_sources,
    )


def render_haproxy_bind(address: str, port: int) -> str:
    """Render an HAProxy bind target, adding IPv6 brackets when required."""
    parsed = ipaddress.ip_address(address)
    return f"[{address}]:{port}" if parsed.version == 6 else f"{address}:{port}"


def render_haproxy_access_rules(sources: tuple[str, ...]) -> str:
    """Render the optional source allowlist shared by managed frontends."""
    if not sources:
        return ""
    allowed_sources = (*sources, *LOCAL_HEALTHCHECK_SOURCES)
    return (
        f"    acl atlas_backend_source src {' '.join(allowed_sources)}\n"
        "    http-request deny if !atlas_backend_source"
    )


def _validated_count(service: str, count: int, variable: str | None = None) -> int:
    """Validate one service count and return it."""
    maximum = MAX_INSTANCE_COUNTS[service]
    if not 1 <= count <= maximum:
        label = variable or service
        raise ValueError(f"{label} must be between 1 and {maximum}, got {count}.")
    return count


def _validated_keep_releases(value: int) -> int:
    """Validate the bounded release-retention count."""
    if not 2 <= value <= 20:
        raise ValueError(f"keep_releases must be between 2 and 20, got {value}.")
    return value


def _validated_address(value: str) -> str:
    """Validate and normalize one IP address."""
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        raise ValueError(f"Invalid HAProxy bind address {value!r}.") from None


def _validated_sources(value: str) -> tuple[str, ...]:
    """Validate and normalize a comma-separated list of IP networks."""
    sources: list[str] = []
    for source in filter(None, (item.strip() for item in value.split(","))):
        try:
            sources.append(str(ipaddress.ip_network(source, strict=False)))
        except ValueError:
            raise ValueError(f"Invalid HAProxy allowed source {source!r}.") from None
    return tuple(sources)


def _existing_haproxy_network(path: Path | None) -> tuple[str, tuple[str, ...]]:
    """Extract managed network policy from a legacy HAProxy configuration."""
    if not path or not path.exists():
        return "127.0.0.1", ()
    content = path.read_text(encoding="utf-8")
    bind_match = re.search(r"^\s*bind\s+(?:\[([^]]+)]|([^:\s]+)):\d+", content, re.MULTILINE)
    source_match = re.search(r"^\s*acl\s+atlas_backend_source\s+src\s+(.+)$", content, re.MULTILINE)
    address = (bind_match.group(1) or bind_match.group(2)) if bind_match else "127.0.0.1"
    sources = _validated_sources(source_match.group(1).replace(" ", ",")) if source_match else ()
    return _validated_address(address), sources
