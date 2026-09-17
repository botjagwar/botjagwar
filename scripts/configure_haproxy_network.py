#!/usr/bin/env python3
"""Configure source-restricted access to Botjagwar HAProxy frontends."""

from __future__ import annotations

import argparse
import dataclasses
import ipaddress
import os
import tempfile
from pathlib import Path

try:
    from scripts.deployment_config import DeploymentConfig, LOCAL_HEALTHCHECK_SOURCES
except ModuleNotFoundError:  # Direct execution adds scripts/, not the repository root, to sys.path.
    from deployment_config import DeploymentConfig, LOCAL_HEALTHCHECK_SOURCES


MANAGED_PORTS = {8000, 8001, 8100, 8890}
ACL_NAME = "atlas_backend_source"


def format_bind_address(address: str) -> str:
    """Format an IP address for an HAProxy bind directive."""
    parsed = ipaddress.ip_address(address)
    return f"[{parsed}]" if parsed.version == 6 else str(parsed)


def configure_network(content: str, bind_address: str, allowed_source: str) -> str:
    """Replace managed frontend binds and source restrictions idempotently."""
    bind = format_bind_address(bind_address)
    source = str(ipaddress.ip_network(allowed_source, strict=False))
    acl_sources = " ".join((source, *LOCAL_HEALTHCHECK_SOURCES))
    output: list[str] = []
    managed_frontend = False
    skip_managed_acl = False

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("frontend "):
            managed_frontend = False
            skip_managed_acl = False
        if managed_frontend and (
            stripped == f"acl {ACL_NAME} src {source}"
            or stripped.startswith(f"acl {ACL_NAME} src ")
            or stripped == f"http-request deny unless {ACL_NAME}"
            or stripped == f"http-request deny if !{ACL_NAME}"
        ):
            continue
        if stripped.startswith("bind "):
            endpoint = stripped.removeprefix("bind ").split()[0]
            try:
                port = int(endpoint.rsplit(":", maxsplit=1)[1])
            except (IndexError, ValueError):
                port = 0
            managed_frontend = port in MANAGED_PORTS
            skip_managed_acl = managed_frontend
            if managed_frontend:
                indent = line[: len(line) - len(line.lstrip())]
                output.extend(
                    (
                        f"{indent}bind {bind}:{port}",
                        f"{indent}acl {ACL_NAME} src {acl_sources}",
                        f"{indent}http-request deny unless {ACL_NAME}",
                    )
                )
                continue
        if skip_managed_acl and stripped.startswith(
            (f"acl {ACL_NAME} ", f"http-request deny unless {ACL_NAME}", f"http-request deny if !{ACL_NAME}")
        ):
            continue
        output.append(line)
    return "\n".join(output).rstrip() + "\n"


def update_config(path: Path, bind_address: str, allowed_source: str) -> None:
    """Atomically update one HAProxy configuration while retaining its mode."""
    if path.is_symlink():
        path = path.resolve(strict=True)
    original = path.read_text(encoding="utf-8")
    updated = configure_network(original, bind_address, allowed_source)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as temporary:
        temporary.write(updated)
        temporary_path = Path(temporary.name)
    temporary_path.chmod(path.stat().st_mode)
    os.replace(temporary_path, path)


def update_deployment_config(path: Path, bind_address: str, allowed_source: str) -> None:
    """Persist an HAProxy network change in the declarative manifest when present."""
    if not path.exists():
        return
    deployment = DeploymentConfig.load(path)
    updated = dataclasses.replace(
        deployment,
        haproxy_bind_address=str(ipaddress.ip_address(bind_address)),
        haproxy_allowed_sources=(str(ipaddress.ip_network(allowed_source, strict=False)),),
    )
    updated.write(path)


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("/etc/botjagwar/haproxy.cfg"))
    parser.add_argument("--deployment-config", type=Path, default=Path("/etc/botjagwar/deployment.ini"))
    parser.add_argument(
        "--bind-address",
        default="0.0.0.0",
        help="Backend bind address (default: all IPv4 interfaces)",
    )
    parser.add_argument("--allow-source", required=True, help="Atlas source IP address or CIDR")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Apply source-restricted network settings to HAProxy."""
    args = build_parser().parse_args(argv)
    try:
        update_config(args.config, args.bind_address, args.allow_source)
        update_deployment_config(args.deployment_config, args.bind_address, args.allow_source)
    except (OSError, ValueError) as error:
        print(f"Error: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
