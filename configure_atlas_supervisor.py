#!/usr/bin/env python3
"""Securely connect a remote Supervisor instance to Botjagwar Atlas."""

from __future__ import annotations

import argparse
import base64
import ipaddress
import os
import re
import secrets
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from supervisor_control_service import SupervisorHost, create_supervisor_client, load_hosts


NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")
HOSTNAME_PATTERN = re.compile(
    r"^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)*"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$"
)
FORBIDDEN_PROGRAMS = {"botjagwar_atlas", "load_balancer", "supervisor_control_service"}
MANAGED_HOSTS_COMMENT = "botjagwar-atlas-supervisor:"


@dataclass(frozen=True)
class Configuration:
    """Store validated command-line settings."""

    host_id: str
    label: str
    address: str
    hostname: str
    atlas_source: str
    programs: tuple[str, ...]
    ssh_target: str
    ssh_options: tuple[str, ...]
    port: int
    username: str
    timeout: float
    atlas_config: Path
    hosts_file: Path
    remote_supervisor_config: str
    remote_nginx_location: str
    remote_nginx_prefix: str
    remote_nginx_config: str
    remote_nginx_program: str
    skip_gateway_restart: bool

    @property
    def url(self) -> str:
        """Return the public Supervisor XML-RPC endpoint."""
        return f"https://{self.hostname}:{self.port}/RPC2"


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Configure authenticated Supervisor XML-RPC on a remote Botjagwar host for Atlas.",
    )
    parser.add_argument("--host", required=True, help="Stable Atlas host identifier")
    parser.add_argument("--label", required=True, help="Display label shown in Atlas")
    parser.add_argument("--address", required=True, help="Remote IP address added to the Atlas host's /etc/hosts")
    parser.add_argument("--hostname", required=True, help="TLS hostname used by the remote Atlas Nginx server")
    parser.add_argument("--atlas-source", required=True, help="Atlas source IP address or CIDR allowed by remote Nginx")
    parser.add_argument("--program", action="append", required=True, help="Supervisor program to allow; repeat as needed")
    parser.add_argument("--ssh-target", help="SSH destination, defaulting to --address")
    parser.add_argument("--ssh-option", action="append", default=[], help="One ssh option, such as IdentityFile=/path")
    parser.add_argument("--port", type=int, default=38000, help="Remote HTTPS port (default: 38000)")
    parser.add_argument("--username", default="atlas-control", help="Remote Supervisor RPC username")
    parser.add_argument("--timeout", type=float, default=5.0, help="Atlas RPC timeout in seconds (default: 5)")
    parser.add_argument(
        "--atlas-config",
        type=Path,
        default=Path("/etc/botjagwar/supervisor-control.ini"),
        help="Local Atlas Supervisor configuration",
    )
    parser.add_argument("--hosts-file", type=Path, default=Path("/etc/hosts"), help=argparse.SUPPRESS)
    parser.add_argument(
        "--remote-supervisor-config",
        default="/etc/supervisor/conf.d/atlas-rpc.conf",
        help="Remote Supervisor listener configuration",
    )
    parser.add_argument(
        "--remote-nginx-location",
        default="/etc/botjagwar/supervisor-rpc-location.conf",
        help="Remote Nginx location include",
    )
    parser.add_argument(
        "--remote-nginx-prefix",
        default="/opt/botjagwar/current/frontend",
        help="Remote Atlas Nginx prefix",
    )
    parser.add_argument(
        "--remote-nginx-config",
        default="/opt/botjagwar/current/frontend/config/nginx/nginx.conf",
        help="Remote Atlas Nginx main configuration",
    )
    parser.add_argument(
        "--remote-nginx-program",
        default="botjagwar_atlas",
        help="Remote Supervisor program running Atlas Nginx",
    )
    parser.add_argument("--skip-gateway-restart", action="store_true", help=argparse.SUPPRESS)
    return parser


def validated_configuration(args: argparse.Namespace) -> Configuration:
    """Validate parsed arguments and return an immutable configuration."""
    if not NAME_PATTERN.fullmatch(args.host):
        raise ValueError("Host identifiers may contain only letters, numbers, dots, underscores, and hyphens.")
    if not args.label.strip() or any(character in args.label for character in "\r\n"):
        raise ValueError("The host label must be non-empty and fit on one line.")
    try:
        address = str(ipaddress.ip_address(args.address))
    except ValueError:
        raise ValueError("--address must be an IPv4 or IPv6 address.") from None
    if not HOSTNAME_PATTERN.fullmatch(args.hostname):
        raise ValueError("--hostname must be a valid DNS hostname.")
    try:
        atlas_source = str(ipaddress.ip_network(args.atlas_source, strict=False))
    except ValueError:
        raise ValueError("--atlas-source must be an IP address or CIDR network.") from None
    if not 1 <= args.port <= 65535:
        raise ValueError("--port must be between 1 and 65535.")
    if not 0 < args.timeout <= 10:
        raise ValueError("--timeout must be greater than zero and no more than 10 seconds.")
    if not NAME_PATTERN.fullmatch(args.username):
        raise ValueError("The RPC username contains unsupported characters.")
    programs = tuple(dict.fromkeys(args.program))
    for program in programs:
        if not NAME_PATTERN.fullmatch(program):
            raise ValueError(f"Invalid Supervisor program name: {program}")
        if program in FORBIDDEN_PROGRAMS:
            raise ValueError(f"Supervisor program cannot be controlled through Atlas: {program}")
    ssh_target = args.ssh_target or address
    if ssh_target.startswith("-") or any(character.isspace() for character in ssh_target):
        raise ValueError("The SSH target cannot begin with a hyphen or contain whitespace.")
    remote_paths = (
        args.remote_supervisor_config,
        args.remote_nginx_location,
        args.remote_nginx_prefix,
        args.remote_nginx_config,
    )
    if any(not path.startswith("/") or "\n" in path or "\r" in path for path in remote_paths):
        raise ValueError("Remote configuration paths must be absolute and fit on one line.")
    if not NAME_PATTERN.fullmatch(args.remote_nginx_program):
        raise ValueError("The remote Nginx Supervisor program name is invalid.")
    return Configuration(
        host_id=args.host,
        label=args.label.strip(),
        address=address,
        hostname=args.hostname.lower(),
        atlas_source=atlas_source,
        programs=programs,
        ssh_target=ssh_target,
        ssh_options=tuple(args.ssh_option),
        port=args.port,
        username=args.username,
        timeout=args.timeout,
        atlas_config=args.atlas_config,
        hosts_file=args.hosts_file,
        remote_supervisor_config=args.remote_supervisor_config,
        remote_nginx_location=args.remote_nginx_location,
        remote_nginx_prefix=args.remote_nginx_prefix,
        remote_nginx_config=args.remote_nginx_config,
        remote_nginx_program=args.remote_nginx_program,
        skip_gateway_restart=args.skip_gateway_restart,
    )


def generate_password() -> str:
    """Generate a Supervisor password safe for INI files and URL encoding."""
    return secrets.token_urlsafe(36)


def render_supervisor_listener(username: str, password: str) -> str:
    """Render the loopback-only Supervisor XML-RPC listener."""
    return (
        "# Managed by configure-atlas-supervisor.\n"
        "[inet_http_server]\n"
        "port = 127.0.0.1:9001\n"
        f"username = {username}\n"
        f"password = {password}\n"
    )


def render_nginx_location(atlas_source: str) -> str:
    """Render the source-restricted HTTPS XML-RPC proxy location."""
    return (
        "# Managed by configure-atlas-supervisor.\n"
        "location = /RPC2 {\n"
        "    auth_basic off;\n"
        f"    allow {atlas_source};\n"
        "    deny all;\n"
        "    limit_except POST { deny all; }\n"
        "    proxy_pass http://127.0.0.1:9001/RPC2;\n"
        "    proxy_connect_timeout 5s;\n"
        "    proxy_read_timeout 15s;\n"
        "}\n"
    )


def render_atlas_section(config: Configuration, password: str) -> str:
    """Render one Atlas host section containing the generated credentials."""
    program_lines = ",\n".join(f"    {program}" for program in config.programs)
    return (
        f"[host:{config.host_id}]\n"
        f"label = {config.label}\n"
        f"url = {config.url}\n"
        f"username = {config.username}\n"
        f"password = {password}\n"
        f"timeout = {config.timeout:g}\n"
        "programs =\n"
        f"{program_lines}\n"
    )


def replace_atlas_section(content: str, host_id: str, section: str) -> str:
    """Replace all matching managed host sections without changing other hosts."""
    lines = content.splitlines(keepends=True)
    output: list[str] = []
    target = f"host:{host_id}"
    skipping = False
    for line in lines:
        match = re.match(r"^\s*\[([^]]+)]\s*(?:[#;].*)?\r?\n?$", line)
        if match:
            skipping = match.group(1).strip() == target
        if not skipping:
            output.append(line)
    existing = "".join(output).rstrip()
    return f"{existing}\n\n{section.rstrip()}\n" if existing else f"{section.rstrip()}\n"


def replace_hosts_entry(content: str, host_id: str, address: str, hostname: str) -> str:
    """Replace the command's marked /etc/hosts entry and reject conflicting mappings."""
    marker = f"# {MANAGED_HOSTS_COMMENT}{host_id}"
    output: list[str] = []
    hostname_already_mapped = False
    for line in content.splitlines():
        if line.rstrip().endswith(marker):
            continue
        fields = line.split("#", 1)[0].split()
        if hostname in fields[1:]:
            if fields[0] != address:
                raise ValueError(f"{hostname} is already mapped to a different address in the hosts file.")
            hostname_already_mapped = True
        output.append(line)
    if not hostname_already_mapped:
        output.append(f"{address} {hostname} {marker}")
    return "\n".join(output).rstrip() + "\n"


def encoded(content: str) -> str:
    """Encode file content for transport inside an SSH standard-input script."""
    return base64.b64encode(content.encode("ascii")).decode("ascii")


def build_remote_script(config: Configuration, password: str) -> str:
    """Build the privileged remote installation script sent over SSH standard input."""
    supervisor_content = encoded(render_supervisor_listener(config.username, password))
    nginx_content = encoded(render_nginx_location(config.atlas_source))
    supervisor_path = shlex.quote(config.remote_supervisor_config)
    nginx_path = shlex.quote(config.remote_nginx_location)
    nginx_prefix = shlex.quote(config.remote_nginx_prefix.rstrip("/") + "/")
    nginx_config = shlex.quote(config.remote_nginx_config)
    nginx_program = shlex.quote(config.remote_nginx_program)
    legacy_nginx_path = shlex.quote(config.remote_nginx_prefix.rstrip("/") + "/config/nginx/supervisor-rpc-location.conf")
    return f"""#!/bin/bash
set -euo pipefail

install_encoded() {{
    local encoded_content=$1
    local destination=$2
    local mode=$3
    local temporary
    temporary=$(mktemp)
    printf '%s' "$encoded_content" | base64 --decode > "$temporary"
    install -D -o root -g root -m "$mode" "$temporary" "$destination"
    rm -f "$temporary"
}}

install_encoded {shlex.quote(supervisor_content)} {supervisor_path} 0600
install_encoded {shlex.quote(nginx_content)} {nginx_path} 0644

nginx_dump=$(/usr/sbin/nginx -T -p {nginx_prefix} -c {nginx_config} 2>&1)
if ! grep -Fq 'location = /RPC2' <<< "$nginx_dump"; then
    # Migrate hosts whose currently running Nginx still includes the legacy /opt path.
    install_encoded {shlex.quote(nginx_content)} {legacy_nginx_path} 0644
    nginx_dump=$(/usr/sbin/nginx -T -p {nginx_prefix} -c {nginx_config} 2>&1)
    if ! grep -Fq 'location = /RPC2' <<< "$nginx_dump"; then
        printf '%s\n' 'Remote Nginx does not include the Supervisor RPC location file.' >&2
        exit 1
    fi
fi
/usr/sbin/nginx -t -p {nginx_prefix} -c {nginx_config}

if command -v systemctl >/dev/null 2>&1; then
    systemctl restart supervisor
else
    service supervisor restart
fi
supervisorctl restart {nginx_program}
"""


def configure_remote(config: Configuration, password: str) -> None:
    """Install and activate the remote Supervisor and Nginx configuration."""
    command = ["ssh"]
    for option in config.ssh_options:
        command.extend(("-o", option))
    command.extend((config.ssh_target, "sudo", "-n", "bash", "-s"))
    try:
        subprocess.run(command, input=build_remote_script(config, password), text=True, check=True)
    except subprocess.CalledProcessError:
        raise RuntimeError(
            "Remote configuration failed. The SSH account must have non-interactive sudo access; rerun after correcting the error."
        ) from None


def validated_atlas_content(config: Configuration, password: str, existing: str) -> str:
    """Create and validate the complete local Atlas configuration."""
    content = replace_atlas_section(existing, config.host_id, render_atlas_section(config, password))
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as temporary:
        temporary.write(content)
        temporary.flush()
        load_hosts(Path(temporary.name))
    return content


def install_local_file(path: Path, content: str, mode: int, default_owner: tuple[int, int]) -> None:
    """Install a local file, using sudo when its directory is protected."""
    owner = default_owner
    if path.exists():
        file_stat = path.stat()
        owner = (file_stat.st_uid, file_stat.st_gid)
    if path.exists() and os.access(path, os.W_OK):
        path.write_text(content, encoding="utf-8")
        path.chmod(mode)
        return
    if not path.exists() and os.access(path.parent, os.W_OK):
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as temporary:
            temporary.write(content)
            temporary_path = Path(temporary.name)
        temporary_path.chmod(mode)
        os.replace(temporary_path, path)
        return
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False) as temporary:
        temporary.write(content)
        temporary_path = Path(temporary.name)
    try:
        subprocess.run(
            [
                "sudo",
                "install",
                "-D",
                "-o",
                str(owner[0]),
                "-g",
                str(owner[1]),
                "-m",
                f"{mode:04o}",
                str(temporary_path),
                str(path),
            ],
            check=True,
        )
    finally:
        temporary_path.unlink(missing_ok=True)


def validate_remote(config: Configuration, password: str) -> None:
    """Verify trusted TLS, RPC authentication, and all configured programs."""
    host = SupervisorHost(
        config.host_id,
        config.label,
        config.url,
        config.username,
        password,
        config.programs,
        config.timeout,
    )
    try:
        processes = create_supervisor_client(host).getAllProcessInfo()
    except Exception:
        raise RuntimeError(
            "Remote Supervisor validation failed. Verify DNS, certificate trust, source-IP routing, and the remote logs."
        ) from None
    available = {str(process.get("name", "")) for process in processes}
    missing = sorted(set(config.programs) - available)
    if missing:
        raise RuntimeError(f"Remote Supervisor does not define the allowlisted programs: {', '.join(missing)}")


def configure(config: Configuration) -> None:
    """Apply remote configuration, validate it, and register the host locally."""
    password = generate_password()
    configure_remote(config, password)

    hosts_content = config.hosts_file.read_text(encoding="utf-8") if config.hosts_file.exists() else ""
    hosts_content = replace_hosts_entry(hosts_content, config.host_id, config.address, config.hostname)
    install_local_file(config.hosts_file, hosts_content, 0o644, (0, 0))

    validate_remote(config, password)

    atlas_content = config.atlas_config.read_text(encoding="utf-8") if config.atlas_config.exists() else ""
    atlas_content = validated_atlas_content(config, password, atlas_content)
    install_local_file(config.atlas_config, atlas_content, 0o600, (os.getuid(), os.getgid()))
    if not config.skip_gateway_restart:
        subprocess.run(["sudo", "supervisorctl", "restart", "supervisor_control_service"], check=True)
    print(f"Configured Atlas Supervisor host {config.host_id} at {config.url} with {len(config.programs)} programs.")


def main(argv: list[str] | None = None) -> int:
    """Run the remote Supervisor configurator."""
    try:
        config = validated_configuration(build_parser().parse_args(argv))
        configure(config)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
