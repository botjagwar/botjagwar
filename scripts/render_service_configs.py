#!/usr/bin/env python3
"""Render Supervisor and HAProxy configuration from shared instance counts."""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Mapping

try:
    from scripts.deployment_config import (
        atomic_write_text,
        render_haproxy_access_rules,
        render_haproxy_bind,
        resolved_deployment_config,
    )
except ModuleNotFoundError:  # Direct execution adds scripts/, not the repository root, to sys.path.
    from deployment_config import (
        atomic_write_text,
        render_haproxy_access_rules,
        render_haproxy_bind,
        resolved_deployment_config,
    )


def render_program(
    name: str,
    command: str,
    stdout_logfile: str,
    stderr_logfile: str,
    user: str,
    autostart: bool,
    directory: str | None = None,
    max_log_size: str = "100MB",
    environment: str | None = None,
) -> str:
    """Render one Supervisor program section."""
    return (
        f"[program:{name}]\n"
        f"command={command}\n"
        f"stdout_logfile={stdout_logfile}\n"
        f"stderr_logfile={stderr_logfile}\n"
        f"autostart={'true' if autostart else 'false'}\n"
        f"{f'directory={directory}' + chr(10) if directory else ''}"
        f"{f'environment={environment}' + chr(10) if environment else ''}"
        "startretries=10\n"
        f"user={user}\n"
        f"stderr_logfile_maxbytes={max_log_size}"
    )


def render_dictionary_programs(
    count: int,
    user: str,
    autostart: bool,
    application_root: Path,
    config_root: Path,
    state_root: Path,
) -> str:
    """Render dictionary service programs on ports starting at 28001."""
    return "\n\n".join(
        render_program(
            f"dictionary_service_{index}",
            f"{application_root}/pyenv/bin/python {application_root}/dictionary_service.py -p {28000 + index}",
            f"{state_root}/user_data/supervisor_dictionary_service_stdout.log",
            f"{state_root}/user_data/supervisor_dictionary_service_stderr.log",
            user,
            autostart,
            str(application_root),
            environment=f'BOTJAGWAR_CONFIG="{config_root}/config.ini"',
        )
        for index in range(1, count + 1)
    )


def render_entry_translator_programs(
    count: int,
    user: str,
    autostart: bool,
    application_root: Path,
    config_root: Path,
    state_root: Path,
) -> str:
    """Render entry translator programs on ports starting at 18001."""
    return "\n\n".join(
        render_program(
            f"entry_translator_{index}",
            f"{application_root}/pyenv/bin/python {application_root}/entry_translator_v2.py -p {18000 + index} -q translated",
            f"{state_root}/user_data/supervisor_entry_translator_stdout.log",
            f"{state_root}/user_data/supervisor_entry_translator_stderr.log",
            user,
            autostart,
            str(application_root),
            environment=f'BOTJAGWAR_CONFIG="{config_root}/config.ini"',
        )
        for index in range(1, count + 1)
    )


def render_postgrest_programs(
    count: int,
    user: str,
    autostart: bool,
    application_root: Path,
    config_root: Path,
    state_root: Path,
) -> str:
    """Render PostgREST programs, reserving port 8100 for HAProxy."""
    return "\n\n".join(
        render_program(
            f"postgrest_{index}",
            f"{application_root}/bin/postgrest {config_root}/pgrest/pgrest_{index}.ini",
            f"{state_root}/user_data/supervisor_postgrest{index}_stdout.log",
            f"{state_root}/user_data/supervisor_postgrest{index}_stderr.log",
            user,
            autostart,
            str(application_root),
        )
        for index in range(2, count + 2)
    )


def render_postgrest_configs(
    count: int,
    template_dir: Path,
    output_dir: Path,
) -> None:
    """Render PostgREST instance configuration files from a single template.

    Reserves port 8100 for HAProxy and assigns ports 8101..8100+count to
    individual PostgREST instances.
    """
    pgrest_dir = output_dir / "pgrest"
    pgrest_dir.mkdir(parents=True, exist_ok=True)
    template_path = template_dir / "pgrest" / "pgrest.ini.template"
    for index in range(2, count + 2):
        port = 8100 + index - 1
        content = render_template(template_path, {"SERVER_PORT": str(port)})
        atomic_write_text(pgrest_dir / f"pgrest_{index}.ini", content, mode=0o600)


def render_translator_programs(count: int, user: str, autostart: bool) -> str:
    """Render CTranslate programs on ports starting at 8886."""
    return "\n\n".join(
        render_program(
            f"translator_{index}",
            f"/opt/ctranslate/venv/bin/python /opt/ctranslate/ctranslate-lite.py {8885 + index}",
            f"/opt/ctranslate/translator_{index}_stdout.log",
            f"/opt/ctranslate/translator_{index}_stderr.log",
            user,
            autostart,
            max_log_size="10MB",
        )
        for index in range(1, count + 1)
    )


def render_gemma_configuration(
    template_dir: Path,
    output_dir: Path,
    user: str,
    autostart: bool,
    gemma_root: Path = Path("/opt/gemma"),
) -> None:
    """Render the standalone single-instance Gemma Supervisor configuration."""
    content = render_template(
        template_dir / "supervisor-gemma.conf.template",
        {
            "USER": user,
            "AUTOSTART": "true" if autostart else "false",
            "GEMMA_ROOT": str(gemma_root),
        },
    )
    atomic_write_text(output_dir / "supervisor-gemma.conf", content, mode=0o644)


def render_servers(name: str, first_port: int, count: int) -> str:
    """Render an HAProxy server pool with sequential names and ports."""
    return "\n".join(
        f"server {name}{index} 127.0.0.1:{first_port + index - 1} check" for index in range(1, count + 1)
    )


PLACEHOLDER_PATTERN = re.compile(r"\{\{([^{}\n]+)\}\}")


def render_template(path: Path, replacements: Mapping[str, str]) -> str:
    """Render a marker-based template in one pass and reject unknown or malformed markers."""
    content = path.read_text(encoding="utf-8")

    def replace(match: re.Match[str]) -> str:
        marker = match.group(1)
        if marker not in replacements:
            raise ValueError(f"Unresolved template marker in {path}: {marker}")
        return replacements[marker]

    rendered = PLACEHOLDER_PATTERN.sub(replace, content)
    if "{{" in PLACEHOLDER_PATTERN.sub("", rendered) or "}}" in PLACEHOLDER_PATTERN.sub("", rendered):
        raise ValueError(f"Malformed template marker in {path}.")
    return rendered.rstrip() + "\n"


def render_configurations(
    template_dir: Path,
    output_dir: Path,
    counts: Mapping[str, int],
    user: str,
    autostart: bool,
    application_root: Path = Path("/opt/botjagwar/current"),
    config_root: Path = Path("/etc/botjagwar"),
    state_root: Path = Path("/var/lib/botjagwar"),
    frontend_root: Path = Path("/opt/botjagwar/current/frontend"),
    haproxy_bind_address: str = "127.0.0.1",
    haproxy_allowed_sources: tuple[str, ...] = (),
) -> None:
    """Render all service configurations so Supervisor and HAProxy stay aligned."""
    supervisor = render_template(
        template_dir / "supervisor-botjagwar.conf.template",
        {
            "USER": user,
            "APPLICATION_ROOT": str(application_root),
            "CONFIG_ROOT": str(config_root),
            "STATE_ROOT": str(state_root),
            "FRONTEND_ROOT": str(frontend_root),
            "DICTIONARY_SERVICE_PROGRAMS": render_dictionary_programs(
                counts["dictionary_service"],
                user,
                autostart,
                application_root,
                config_root,
                state_root,
            ),
            "ENTRY_TRANSLATOR_PROGRAMS": render_entry_translator_programs(
                counts["entry_translator"],
                user,
                autostart,
                application_root,
                config_root,
                state_root,
            ),
            "POSTGREST_PROGRAMS": render_postgrest_programs(
                counts["postgrest"], user, autostart, application_root, config_root, state_root
            ),
        },
    )
    ctranslate = render_template(
        template_dir / "supervisor-ctranslate.conf.template",
        {"TRANSLATOR_PROGRAMS": render_translator_programs(counts["translator"], user, autostart)},
    )
    haproxy = render_template(
        template_dir / "haproxy.cfg.template",
        {
            "TRANSLATOR_BIND": render_haproxy_bind(haproxy_bind_address, 8890),
            "DICTIONARY_BIND": render_haproxy_bind(haproxy_bind_address, 8001),
            "ENTRY_TRANSLATOR_BIND": render_haproxy_bind(haproxy_bind_address, 8000),
            "POSTGREST_BIND": render_haproxy_bind(haproxy_bind_address, 8100),
            "HAPROXY_ACCESS_RULES": render_haproxy_access_rules(haproxy_allowed_sources),
            "TRANSLATOR_SERVERS": render_servers("translator", 8886, counts["translator"]),
            "DICTIONARY_SERVICE_SERVERS": render_servers(
                "dictionary", 28001, counts["dictionary_service"]
            ),
            "ENTRY_TRANSLATOR_SERVERS": render_servers(
                "entry_translator", 18001, counts["entry_translator"]
            ),
            "POSTGREST_SERVERS": render_servers("pgrest", 8101, counts["postgrest"]),
        },
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, content in (
        ("supervisor-botjagwar.conf", supervisor),
        ("supervisor-ctranslate.conf", ctranslate),
        ("haproxy.cfg", haproxy),
    ):
        atomic_write_text(output_dir / filename, content, mode=0o644)

    render_postgrest_configs(counts["postgrest"], template_dir, output_dir)


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser."""
    repository_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-dir", type=Path, default=repository_root / "conf")
    parser.add_argument("--output-dir", type=Path, default=repository_root / "conf")
    parser.add_argument("--user", default="user", help="Operating-system user for Supervisor programs")
    parser.add_argument("--group", default="user", help="Operating-system group for deployment files")
    parser.add_argument("--application-root", type=Path, default=Path("/opt/botjagwar/current"))
    parser.add_argument("--config-root", type=Path, default=Path("/etc/botjagwar"))
    parser.add_argument("--state-root", type=Path, default=Path("/var/lib/botjagwar"))
    parser.add_argument("--frontend-root", type=Path, default=Path("/opt/botjagwar/current/frontend"))
    parser.add_argument("--deployment-config", type=Path)
    parser.add_argument("--write-deployment-config", type=Path)
    parser.add_argument("--existing-haproxy-config", type=Path)
    parser.add_argument("--gemma-only", action="store_true", help="Render only standalone Gemma Supervisor config")
    parser.add_argument("--gemma-root", type=Path, default=Path("/opt/gemma"))
    parser.add_argument(
        "--existing-supervisor-config",
        action="append",
        type=Path,
        default=[],
        help="Existing generated Supervisor configuration used to retain instance counts",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Render configuration using environment variables and command-line paths."""
    args = build_parser().parse_args(argv)
    try:
        if args.gemma_only:
            render_gemma_configuration(
                args.template_dir,
                args.output_dir,
                args.user,
                os.environ.get("NO_AUTOSTART") != "1",
                args.gemma_root,
            )
            return 0
        deployment = resolved_deployment_config(
            os.environ,
            args.user,
            args.group,
            args.deployment_config,
            args.existing_supervisor_config,
            args.existing_haproxy_config,
        )
        if args.write_deployment_config:
            deployment.write(args.write_deployment_config)
        render_configurations(
            args.template_dir,
            args.output_dir,
            deployment.instance_counts,
            deployment.service_user,
            deployment.autostart,
            args.application_root,
            args.config_root,
            args.state_root,
            args.frontend_root,
            deployment.haproxy_bind_address,
            deployment.haproxy_allowed_sources,
        )
    except (OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
