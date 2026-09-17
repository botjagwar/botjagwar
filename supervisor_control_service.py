#!/usr/bin/env python3
"""Expose allowlisted Supervisor controls to the authenticated Atlas proxy."""

import argparse
import asyncio
import configparser
import concurrent.futures
import http.client
import hmac
import ipaddress
import json
import logging
import os
import re
import sqlite3
import threading
import time
import xmlrpc.client
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol
from urllib.parse import quote, urlsplit, urlunsplit

import psycopg2
import requests
from aiohttp import web

from api.http_client import BULK_HTTP_TIMEOUT
from scripts.deployment_config import atomic_write_text
from scripts.refresh_materialized_views import load_database_uri, refresh_materialized_views

LOGGER = logging.getLogger(__name__)
HOST_SECTION_PREFIX = "host:"
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")
PROGRAM_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")
FORBIDDEN_PROGRAMS = {"botjagwar_atlas", "load_balancer", "supervisor_control_service"}
AUDIT_SERVICES = {"database", "dictionary", "gemma", "translator", "supervisor"}
AUDIT_OUTCOMES = {"succeeded", "failed"}
AUDIT_ACTIONS_BY_SERVICE = {
    "database": {"create", "update", "delete", "refresh"},
    "dictionary": {"create", "update", "delete"},
    "translator": {"queue", "publish", "check", "configure"},
}
DEFAULT_GEMMA_API_URL = "http://127.0.0.1:8891/v1/chat/completions"
DEFAULT_GEMMA_MODEL = "gemma-4-e2b-it-q4-k-m"
MAX_GEMMA_MESSAGES = 40
MAX_GEMMA_MESSAGE_LENGTH = 8_000
MAX_GEMMA_CONVERSATION_LENGTH = 32_000
PRIVATE_GEMMA_NETWORKS = tuple(
    ipaddress.ip_network(network)
    for network in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "fc00::/7")
)


class SupervisorApi(Protocol):
    """Describe the Supervisor XML-RPC methods used by the gateway."""

    def getAllProcessInfo(self) -> list[dict[str, Any]]:  # noqa: N802
        """Return process information from Supervisor."""

    def startProcess(self, name: str, wait: bool = True) -> bool:  # noqa: N802
        """Start an allowlisted process."""

    def stopProcess(self, name: str, wait: bool = True) -> bool:  # noqa: N802
        """Stop an allowlisted process."""


class TimeoutTransport(xmlrpc.client.Transport):
    """Use a finite timeout for HTTP Supervisor XML-RPC requests."""

    def __init__(self, timeout: float) -> None:
        super().__init__()
        self.timeout = timeout

    def make_connection(self, host: str) -> http.client.HTTPConnection:
        """Create a timeout-bound HTTP connection."""
        connection_host, self._extra_headers, _ = self.get_host_info(host)
        return http.client.HTTPConnection(connection_host, timeout=self.timeout)


class TimeoutSafeTransport(xmlrpc.client.SafeTransport):
    """Use a finite timeout for HTTPS Supervisor XML-RPC requests."""

    def __init__(self, timeout: float) -> None:
        super().__init__()
        self.timeout = timeout

    def make_connection(self, host: str) -> http.client.HTTPSConnection:
        """Create a verified timeout-bound HTTPS connection."""
        connection_host, self._extra_headers, x509 = self.get_host_info(host)
        return http.client.HTTPSConnection(connection_host, timeout=self.timeout, context=self.context, **(x509 or {}))


@dataclass(frozen=True)
class SupervisorHost:
    """Store one remote Supervisor endpoint and its program allowlist."""

    identifier: str
    label: str
    url: str
    username: str
    password: str
    programs: tuple[str, ...]
    timeout: float = 5.0


class OperationAudit:
    """Persist bounded Atlas operation metadata in an append-only SQLite journal."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS operations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    accepted_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                    completed_at TEXT,
                    username TEXT NOT NULL,
                    service TEXT NOT NULL,
                    action TEXT NOT NULL,
                    resource TEXT NOT NULL,
                    target TEXT NOT NULL,
                    changed_fields TEXT NOT NULL,
                    outcome TEXT NOT NULL DEFAULT 'pending',
                    error_summary TEXT
                )
            """)
            connection.execute("CREATE INDEX IF NOT EXISTS operations_recent_idx ON operations(id DESC)")

    def _connect(self) -> sqlite3.Connection:
        """Open one short-lived connection safe for worker-thread use."""
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    def begin(self, username: str, service: str, action: str, resource: str, target: dict[str, Any], changed_fields: list[str]) -> dict[str, Any]:
        """Create a pending operation record before a mutation is attempted."""
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO operations (username, service, action, resource, target, changed_fields) VALUES (?, ?, ?, ?, ?, ?)",
                (username, service, action, resource, json.dumps(target, separators=(",", ":")), json.dumps(changed_fields)),
            )
            operation_id = int(cursor.lastrowid or 0)
        return self.get(operation_id)

    def complete(self, operation_id: int, username: str, outcome: str, error_summary: str | None = None) -> dict[str, Any] | None:
        """Complete only a pending operation belonging to the authenticated user."""
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE operations SET completed_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), outcome = ?, error_summary = ? WHERE id = ? AND username = ? AND outcome = 'pending'",
                (outcome, error_summary[:500] if error_summary else None, operation_id, username),
            )
            if cursor.rowcount != 1:
                return None
        return self.get(operation_id)

    def get(self, operation_id: int) -> dict[str, Any]:
        """Return one serialized operation record."""
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM operations WHERE id = ?", (operation_id,)).fetchone()
        if row is None:
            raise KeyError(operation_id)
        return self._serialise(row)

    def list(self, limit: int, before: int | None = None, service: str | None = None, outcome: str | None = None) -> list[dict[str, Any]]:
        """List recent operation records using bounded keyset pagination."""
        clauses: list[str] = []
        values: list[Any] = []
        if before is not None:
            clauses.append("id < ?")
            values.append(before)
        if service is not None:
            clauses.append("service = ?")
            values.append(service)
        if outcome is not None:
            clauses.append("outcome = ?")
            values.append(outcome)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        values.append(limit)
        with self._connect() as connection:
            rows = connection.execute(f"SELECT * FROM operations{where} ORDER BY id DESC LIMIT ?", values).fetchall()
        return [self._serialise(row) for row in rows]

    @staticmethod
    def _serialise(row: sqlite3.Row) -> dict[str, Any]:
        """Convert an SQLite row to the public audit response shape."""
        value = dict(row)
        value["target"] = json.loads(value["target"])
        value["changed_fields"] = json.loads(value["changed_fields"])
        return value


def load_hosts(path: Path) -> dict[str, SupervisorHost]:
    """Load and validate remote Supervisor hosts from a protected INI file."""
    if not path.exists():
        LOGGER.warning("Supervisor control configuration does not exist: %s", path)
        return {}

    parser = configparser.ConfigParser(interpolation=None)
    parser.read(path, encoding="utf-8")
    hosts: dict[str, SupervisorHost] = {}
    for section in parser.sections():
        if not section.startswith(HOST_SECTION_PREFIX):
            continue
        identifier = section.removeprefix(HOST_SECTION_PREFIX).strip()
        if not IDENTIFIER_PATTERN.fullmatch(identifier):
            raise ValueError(f"Invalid Supervisor host identifier: {identifier}")

        url = parser.get(section, "url").strip()
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError(f"Invalid Supervisor URL for host {identifier}")
        if parsed.query or parsed.fragment:
            raise ValueError(f"Supervisor URL cannot contain a query or fragment for host {identifier}")
        try:
            is_loopback = ipaddress.ip_address(parsed.hostname).is_loopback
        except ValueError:
            is_loopback = parsed.hostname == "localhost"
        if parsed.scheme == "http" and not is_loopback:
            raise ValueError(f"Remote Supervisor URL must use HTTPS for host {identifier}")

        programs = tuple(
            dict.fromkeys(item.strip() for item in parser.get(section, "programs").replace("\n", ",").split(",") if item.strip())
        )
        if not programs:
            raise ValueError(f"At least one program is required for host {identifier}")
        for program in programs:
            if not PROGRAM_PATTERN.fullmatch(program):
                raise ValueError(f"Invalid Supervisor program name: {program}")
            if program in FORBIDDEN_PROGRAMS:
                raise ValueError(f"Supervisor program cannot be controlled through Atlas: {program}")

        hosts[identifier] = SupervisorHost(
            identifier=identifier,
            label=parser.get(section, "label", fallback=identifier).strip() or identifier,
            url=url,
            username=parser.get(section, "username").strip(),
            password=parser.get(section, "password"),
            programs=programs,
            timeout=parser.getfloat(section, "timeout", fallback=5.0),
        )
        if not hosts[identifier].username or not hosts[identifier].password:
            raise ValueError(f"Supervisor credentials are required for host {identifier}")
        if not 0 < hosts[identifier].timeout <= 10:
            raise ValueError(f"Supervisor timeout must be between 0 and 10 seconds for host {identifier}")
        if len(hosts) > 32:
            raise ValueError("No more than 32 Supervisor hosts may be configured")
    return hosts


def create_supervisor_client(host: SupervisorHost) -> SupervisorApi:
    """Create a credentialed XML-RPC client for one configured host."""
    parsed = urlsplit(host.url)
    credentials = f"{quote(host.username, safe='')}:{quote(host.password, safe='')}@"
    endpoint = urlunsplit((parsed.scheme, f"{credentials}{parsed.netloc}", parsed.path or "/RPC2", "", ""))
    transport: xmlrpc.client.Transport
    if parsed.scheme == "https":
        transport = TimeoutSafeTransport(host.timeout)
    else:
        transport = TimeoutTransport(host.timeout)
    proxy = xmlrpc.client.ServerProxy(endpoint, transport=transport, allow_none=True)
    return proxy.supervisor


class SupervisorControl:
    """Read and change allowlisted remote Supervisor process states."""

    def __init__(
        self,
        hosts: dict[str, SupervisorHost],
        client_factory: Callable[[SupervisorHost], SupervisorApi] = create_supervisor_client,
    ) -> None:
        self.hosts = hosts
        self.client_factory = client_factory

    @staticmethod
    def serialise_process(host: SupervisorHost, process: dict[str, Any]) -> dict[str, Any]:
        """Return the bounded process details required by Atlas."""
        state = str(process.get("statename", "UNKNOWN")).lower()
        now = int(time.time())
        started = int(process.get("start", 0) or 0)
        return {
            "id": str(process.get("name", "")),
            "host_id": host.identifier,
            "state": state,
            "running": state == "running",
            "description": str(process.get("description", "")),
            "pid": int(process.get("pid", 0) or 0),
            "uptime_seconds": max(0, now - started) if state == "running" and started else 0,
        }

    def host_status(self, host_id: str) -> dict[str, Any]:
        """Return allowlisted process states for one configured host."""
        host = self.hosts.get(host_id)
        if host is None:
            raise KeyError(host_id)
        try:
            processes = self.client_factory(host).getAllProcessInfo()
            by_name = {str(process.get("name")): process for process in processes}
            services = [
                self.serialise_process(host, by_name[program])
                if program in by_name
                else {
                    "id": program,
                    "host_id": host.identifier,
                    "state": "unavailable",
                    "running": False,
                    "description": "Program is not registered on this Supervisor host.",
                    "pid": 0,
                    "uptime_seconds": 0,
                }
                for program in host.programs
            ]
            return {"id": host.identifier, "label": host.label, "available": True, "services": services}
        except (OSError, xmlrpc.client.Error):
            LOGGER.warning("Supervisor host %s is unavailable.", host.identifier)
            return {"id": host.identifier, "label": host.label, "available": False, "services": []}

    def all_statuses(self) -> list[dict[str, Any]]:
        """Return status summaries for every configured host."""
        if not self.hosts:
            return []
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.hosts)) as executor:
            return list(executor.map(self.host_status, self.hosts))

    def change_state(self, host_id: str, program: str, action: str) -> dict[str, Any]:
        """Start or stop one explicitly allowlisted Supervisor program."""
        host = self.hosts.get(host_id)
        if host is None or program not in host.programs:
            raise KeyError(f"{host_id}/{program}")
        if action not in {"start", "stop"}:
            raise ValueError(action)

        client = self.client_factory(host)
        processes = {str(item.get("name")): item for item in client.getAllProcessInfo()}
        if program not in processes:
            raise LookupError(program)
        current = self.serialise_process(host, processes[program])
        if action == "start" and not current["running"]:
            client.startProcess(program, True)
        elif action == "stop" and current["running"]:
            client.stopProcess(program, True)

        updated = {str(item.get("name")): item for item in client.getAllProcessInfo()}
        if program not in updated:
            raise LookupError(program)
        return self.serialise_process(host, updated[program])


class AtlasMaintenance:
    """Run fixed, server-configured Atlas maintenance operations."""

    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path

    def refresh_materialized_views(self) -> dict[str, Any]:
        """Refresh every database materialized view in dependency order."""
        refreshed_views = refresh_materialized_views(load_database_uri(self.config_path))
        return {
            "refreshed_views": refreshed_views,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }


class GemmaChat:
    """Send bounded Atlas conversations to the server-configured Gemma endpoint."""

    def __init__(
        self,
        config_path: Path,
        request_post: Callable[..., requests.Response] = requests.post,
    ) -> None:
        """Load endpoint credentials without exposing them to the browser."""
        parser = configparser.ConfigParser(interpolation=None)
        parser.read(config_path, encoding="utf-8")
        self.config_path = config_path
        self.api_url = self._validated_api_url(
            parser.get("gemma", "api_url", fallback=DEFAULT_GEMMA_API_URL)
        )
        self.model = parser.get("gemma", "model", fallback=DEFAULT_GEMMA_MODEL).strip()
        self.api_key = parser.get("gemma", "api_key", fallback="").strip()
        self.request_post = request_post
        self._settings_lock = threading.Lock()
        if not self.model:
            raise ValueError("The Gemma model must be configured.")

    @staticmethod
    def _validated_api_url(value: object) -> str:
        """Allow HTTPS endpoints and plaintext endpoints on private hosts only."""
        if not isinstance(value, str):
            raise ValueError("The Gemma API URL must be text.")
        api_url = value.strip()
        if not api_url or len(api_url) > 2_048 or any(character.isspace() or ord(character) < 32 for character in api_url):
            raise ValueError("The Gemma API URL is invalid.")
        parsed_url = urlsplit(api_url)
        if not parsed_url.hostname or parsed_url.username or parsed_url.password or parsed_url.fragment:
            raise ValueError("The Gemma API URL must not contain credentials or a fragment.")
        try:
            parsed_url.port
        except ValueError as exc:
            raise ValueError("The Gemma API URL contains an invalid port.") from exc
        try:
            address = ipaddress.ip_address(parsed_url.hostname)
            private_http = address.is_loopback or any(address in network for network in PRIVATE_GEMMA_NETWORKS)
        except ValueError:
            private_http = parsed_url.hostname.lower() == "localhost"
        if parsed_url.scheme != "https" and not (parsed_url.scheme == "http" and private_http):
            raise ValueError("The Gemma API URL must use HTTPS unless it has a private or loopback IP address.")
        return api_url

    def settings(self) -> dict[str, str]:
        """Return the public, non-secret Gemma connection settings."""
        with self._settings_lock:
            return {"api_url": self.api_url, "model": self.model}

    def update_api_url(self, api_url: object) -> dict[str, str]:
        """Persist and immediately activate a validated Gemma endpoint URL."""
        validated_url = self._validated_api_url(api_url)
        with self._settings_lock:
            if self.config_path.is_symlink():
                raise OSError("Refusing to replace a symbolic-link configuration file.")
            content = self.config_path.read_text(encoding="utf-8")
            updated = self._replace_ini_value(content, "gemma", "api_url", validated_url)
            atomic_write_text(self.config_path, updated, mode=0o600)
            self.api_url = validated_url
            return {"api_url": self.api_url, "model": self.model}

    @staticmethod
    def _replace_ini_value(content: str, section: str, key: str, value: str) -> str:
        """Replace one INI value while preserving unrelated settings and comments."""
        newline = "\r\n" if "\r\n" in content else "\n"
        lines = content.splitlines(keepends=True)
        section_pattern = re.compile(r"^\s*\[([^]]+)]")
        key_pattern = re.compile(rf"^(\s*{re.escape(key)}\s*=).*$", re.IGNORECASE)
        output: list[str] = []
        in_section = False
        found_section = False
        replaced = False
        for line in lines:
            section_match = section_pattern.match(line)
            if section_match:
                if in_section and not replaced:
                    output.append(f"{key} = {value}{newline}")
                    replaced = True
                in_section = section_match.group(1).strip().lower() == section.lower()
                found_section = found_section or in_section
            key_match = key_pattern.match(line.rstrip("\r\n")) if in_section else None
            if key_match and not replaced:
                line_ending = line[len(line.rstrip("\r\n")):] or newline
                output.append(f"{key_match.group(1)} {value}{line_ending}")
                replaced = True
            else:
                output.append(line)
        if in_section and not replaced:
            if output and not output[-1].endswith(("\n", "\r")):
                output[-1] += newline
            output.append(f"{key} = {value}{newline}")
        elif not found_section:
            if output and output[-1].strip():
                if not output[-1].endswith(("\n", "\r")):
                    output[-1] += newline
                output.append(newline)
            output.extend((f"[{section}]{newline}", f"{key} = {value}{newline}"))
        return "".join(output)

    def complete(self, messages: list[dict[str, str]]) -> dict[str, str]:
        """Return one assistant response from the configured OpenAI-compatible endpoint."""
        with self._settings_lock:
            api_url = self.api_url
            model = self.model
            api_key = self.api_key
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        try:
            response = self.request_post(
                api_url,
                headers=headers,
                json={"model": model, "messages": messages, "temperature": 0.2},
                timeout=BULK_HTTP_TIMEOUT,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
        except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as exc:
            raise RuntimeError("Gemma endpoint request failed.") from exc
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Gemma endpoint returned empty text.")
        return {"model": model, "content": content.strip()}


CONTROL_KEY = web.AppKey("control", SupervisorControl)
GATEWAY_TOKEN_KEY = web.AppKey("gateway_token", str)
AUDIT_KEY = web.AppKey("audit", OperationAudit)
MAINTENANCE_KEY = web.AppKey("maintenance", AtlasMaintenance)
GEMMA_KEY = web.AppKey("gemma", GemmaChat)


@web.middleware
async def authenticated_proxy_only(request: web.Request, handler: Callable[[web.Request], Any]) -> web.StreamResponse:
    """Reject requests that did not pass through Atlas's authenticated proxy."""
    expected_token = request.app[GATEWAY_TOKEN_KEY]
    supplied_token = request.headers.get("X-Atlas-Gateway-Token", "")
    if not supplied_token or not hmac.compare_digest(supplied_token, expected_token):
        raise web.HTTPUnauthorized(text="Authenticated Atlas gateway required.")
    username = request.headers.get("X-Atlas-Authenticated", "").strip()
    if not username:
        raise web.HTTPUnauthorized(text="Authenticated Atlas proxy required.")
    if request.method in {"POST", "PUT"}:
        if request.path.startswith("/operations/"):
            expected_header = "X-Atlas-Operation-Audit"
        elif request.path.startswith("/maintenance/"):
            expected_header = "X-Atlas-Maintenance"
        elif request.path.startswith("/gemma/"):
            expected_header = "X-Atlas-Gemma"
        else:
            expected_header = "X-Atlas-Service-Control"
        if request.headers.get(expected_header) != "1":
            raise web.HTTPForbidden(text="Atlas operation request header required.")
    if request.method == "PATCH" and request.headers.get("X-Atlas-Operation-Audit") != "1":
        raise web.HTTPForbidden(text="Atlas operation request header required.")
    if request.method in {"POST", "PUT", "PATCH"}:
        if request.headers.get("Sec-Fetch-Site", "same-origin") == "cross-site":
            raise web.HTTPForbidden(text="Cross-site service-control requests are forbidden.")
        origin = request.headers.get("Origin")
        forwarded_host = request.headers.get("X-Forwarded-Host", request.host)
        if origin and urlsplit(origin).netloc != forwarded_host:
            raise web.HTTPForbidden(text="Request origin does not match Atlas.")
    return await handler(request)


def create_app(
    control: SupervisorControl,
    gateway_token: str,
    audit: OperationAudit | None = None,
    maintenance: AtlasMaintenance | None = None,
    gemma: GemmaChat | None = None,
) -> web.Application:
    """Create the localhost-only Supervisor control HTTP application."""
    if not gateway_token:
        raise ValueError("A Supervisor control gateway token is required")
    app = web.Application(middlewares=[authenticated_proxy_only])
    app[CONTROL_KEY] = control
    app[GATEWAY_TOKEN_KEY] = gateway_token
    if audit is not None:
        app[AUDIT_KEY] = audit
    if maintenance is not None:
        app[MAINTENANCE_KEY] = maintenance
    if gemma is not None:
        app[GEMMA_KEY] = gemma

    def operation_audit(request: web.Request) -> OperationAudit:
        """Return the configured audit journal or report unavailable persistence."""
        if AUDIT_KEY not in request.app:
            raise web.HTTPServiceUnavailable(text="Operation audit storage is unavailable.")
        return request.app[AUDIT_KEY]

    async def list_services(request: web.Request) -> web.Response:
        """List configured hosts and allowlisted process states."""
        statuses = await asyncio.to_thread(request.app[CONTROL_KEY].all_statuses)
        return web.json_response({"hosts": statuses})

    async def change_service_state(request: web.Request) -> web.Response:
        """Start or stop one allowlisted process."""
        audit_store = operation_audit(request)
        username = request.headers["X-Atlas-Authenticated"]
        operation = await asyncio.to_thread(
            audit_store.begin,
            username,
            "supervisor",
            request.match_info["action"],
            request.match_info["program"],
            {"host_id": request.match_info["host_id"]},
            [],
        )
        try:
            service = await asyncio.to_thread(
                request.app[CONTROL_KEY].change_state,
                request.match_info["host_id"],
                request.match_info["program"],
                request.match_info["action"],
            )
        except KeyError as exc:
            await asyncio.to_thread(audit_store.complete, operation["id"], username, "failed", "Unknown managed service.")
            raise web.HTTPNotFound(text="Unknown managed service.") from exc
        except LookupError as exc:
            await asyncio.to_thread(audit_store.complete, operation["id"], username, "failed", "Managed service is not registered.")
            raise web.HTTPConflict(text="Managed service is not registered on the remote host.") from exc
        except ValueError as exc:
            await asyncio.to_thread(audit_store.complete, operation["id"], username, "failed", "Unsupported service action.")
            raise web.HTTPBadRequest(text="Unsupported service action.") from exc
        except (OSError, xmlrpc.client.Error) as exc:
            await asyncio.to_thread(audit_store.complete, operation["id"], username, "failed", "Remote Supervisor is unavailable.")
            LOGGER.warning(
                "Supervisor action failed for host=%s service=%s action=%s.",
                request.match_info["host_id"],
                request.match_info["program"],
                request.match_info["action"],
            )
            raise web.HTTPBadGateway(text="Remote Supervisor is unavailable.") from exc
        LOGGER.info(
            "Supervisor action user=%s host=%s service=%s action=%s state=%s",
            request.headers.get("X-Atlas-Authenticated"),
            request.match_info["host_id"],
            request.match_info["program"],
            request.match_info["action"],
            service["state"],
        )
        await asyncio.to_thread(audit_store.complete, operation["id"], username, "succeeded")
        return web.json_response(service)

    async def refresh_views(request: web.Request) -> web.Response:
        """Refresh all materialized views through the fixed maintenance routine."""
        if MAINTENANCE_KEY not in request.app:
            raise web.HTTPServiceUnavailable(text="Atlas maintenance is unavailable.")
        audit_store = operation_audit(request)
        username = request.headers["X-Atlas-Authenticated"]
        operation = await asyncio.to_thread(
            audit_store.begin,
            username,
            "database",
            "refresh",
            "materialized-views",
            {},
            [],
        )
        try:
            result = await asyncio.to_thread(request.app[MAINTENANCE_KEY].refresh_materialized_views)
        except (FileNotFoundError, ValueError, RuntimeError, psycopg2.Error) as exc:
            await asyncio.to_thread(audit_store.complete, operation["id"], username, "failed", "Materialized-view refresh failed.")
            LOGGER.exception("Materialized-view refresh requested by user=%s failed.", username)
            raise web.HTTPInternalServerError(text="Materialized-view refresh failed. Check the server log for details.") from exc
        await asyncio.to_thread(audit_store.complete, operation["id"], username, "succeeded")
        LOGGER.info("Materialized-view refresh user=%s refreshed_views=%s", username, result["refreshed_views"])
        return web.json_response(result)

    async def list_operations(request: web.Request) -> web.Response:
        """Return a bounded page from the persistent operation journal."""
        try:
            limit = min(100, max(1, int(request.query.get("limit", "50"))))
            before = int(request.query["before"]) if "before" in request.query else None
        except ValueError as exc:
            raise web.HTTPBadRequest(text="Invalid operation pagination.") from exc
        service = request.query.get("service") or None
        outcome = request.query.get("outcome") or None
        if service is not None and service not in AUDIT_SERVICES:
            raise web.HTTPBadRequest(text="Invalid operation service filter.")
        if outcome is not None and outcome not in AUDIT_OUTCOMES | {"pending"}:
            raise web.HTTPBadRequest(text="Invalid operation outcome filter.")
        operations = await asyncio.to_thread(operation_audit(request).list, limit + 1, before, service, outcome)
        return web.json_response({"operations": operations[:limit], "next_before": operations[limit - 1]["id"] if len(operations) > limit else None})

    async def begin_operation(request: web.Request) -> web.Response:
        """Persist a pending audit record before an Atlas mutation."""
        if request.content_length is not None and request.content_length > 4096:
            raise web.HTTPRequestEntityTooLarge(max_size=4096, actual_size=request.content_length)
        payload = await request.json()
        service = payload.get("service")
        action = payload.get("action")
        resource = payload.get("resource")
        target = payload.get("target", {})
        changed_fields = payload.get("changed_fields", [])
        if service not in AUDIT_ACTIONS_BY_SERVICE or action not in AUDIT_ACTIONS_BY_SERVICE[service]:
            raise web.HTTPBadRequest(text="Invalid operation classification.")
        if not isinstance(resource, str) or not resource or len(resource) > 160:
            raise web.HTTPBadRequest(text="Invalid operation resource.")
        if not isinstance(target, dict) or not isinstance(changed_fields, list) or not all(isinstance(field, str) and len(field) <= 100 for field in changed_fields):
            raise web.HTTPBadRequest(text="Invalid operation metadata.")
        if len(json.dumps(target)) > 2048:
            raise web.HTTPBadRequest(text="Operation target is too large.")
        operation = await asyncio.to_thread(operation_audit(request).begin, request.headers["X-Atlas-Authenticated"], service, action, resource, target, changed_fields)
        return web.json_response(operation, status=201)

    async def complete_operation(request: web.Request) -> web.Response:
        """Mark the authenticated user's pending operation complete."""
        if request.content_length is not None and request.content_length > 4096:
            raise web.HTTPRequestEntityTooLarge(max_size=4096, actual_size=request.content_length)
        payload = await request.json()
        outcome = payload.get("outcome")
        if outcome not in AUDIT_OUTCOMES:
            raise web.HTTPBadRequest(text="Invalid operation outcome.")
        operation = await asyncio.to_thread(
            operation_audit(request).complete,
            int(request.match_info["operation_id"]),
            request.headers["X-Atlas-Authenticated"],
            outcome,
            payload.get("error_summary") if isinstance(payload.get("error_summary"), str) else None,
        )
        if operation is None:
            raise web.HTTPNotFound(text="Pending operation not found.")
        return web.json_response(operation)

    async def gemma_chat(request: web.Request) -> web.Response:
        """Forward a bounded text conversation to the configured Gemma endpoint."""
        if GEMMA_KEY not in request.app:
            raise web.HTTPServiceUnavailable(text="Gemma chat is unavailable.")
        if request.content_length is not None and request.content_length > 40_000:
            raise web.HTTPRequestEntityTooLarge(max_size=40_000, actual_size=request.content_length)
        try:
            payload = await request.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise web.HTTPBadRequest(text="Request body must be valid JSON.") from exc
        raw_messages = payload.get("messages") if isinstance(payload, dict) else None
        if not isinstance(raw_messages, list) or not 1 <= len(raw_messages) <= MAX_GEMMA_MESSAGES:
            raise web.HTTPBadRequest(text=f"messages must contain between 1 and {MAX_GEMMA_MESSAGES} items.")
        messages: list[dict[str, str]] = []
        total_length = 0
        for raw_message in raw_messages:
            if not isinstance(raw_message, dict) or raw_message.get("role") not in {"user", "assistant"}:
                raise web.HTTPBadRequest(text="Each message must have a user or assistant role.")
            content = raw_message.get("content")
            if not isinstance(content, str) or not content.strip() or len(content) > MAX_GEMMA_MESSAGE_LENGTH:
                raise web.HTTPBadRequest(text=f"Each message must contain 1 to {MAX_GEMMA_MESSAGE_LENGTH} characters.")
            total_length += len(content)
            messages.append({"role": raw_message["role"], "content": content.strip()})
        if total_length > MAX_GEMMA_CONVERSATION_LENGTH:
            raise web.HTTPBadRequest(text=f"Conversation text cannot exceed {MAX_GEMMA_CONVERSATION_LENGTH} characters.")
        if messages[-1]["role"] != "user":
            raise web.HTTPBadRequest(text="The final message must have the user role.")
        try:
            result = await asyncio.to_thread(request.app[GEMMA_KEY].complete, messages)
        except RuntimeError as exc:
            LOGGER.exception("Gemma chat request failed for user=%s.", request.headers.get("X-Atlas-Authenticated"))
            raise web.HTTPBadGateway(text="Gemma could not complete the request. Check the server log for details.") from exc
        return web.json_response({"model": result["model"], "message": {"role": "assistant", "content": result["content"]}})

    async def get_gemma_settings(request: web.Request) -> web.Response:
        """Return the active non-secret Gemma endpoint settings."""
        if GEMMA_KEY not in request.app:
            raise web.HTTPServiceUnavailable(text="Gemma chat is unavailable.")
        return web.json_response(request.app[GEMMA_KEY].settings())

    async def update_gemma_settings(request: web.Request) -> web.Response:
        """Persist and activate a deployment-wide Gemma endpoint."""
        if GEMMA_KEY not in request.app:
            raise web.HTTPServiceUnavailable(text="Gemma chat is unavailable.")
        if request.content_length is not None and request.content_length > 4_096:
            raise web.HTTPRequestEntityTooLarge(max_size=4_096, actual_size=request.content_length)
        try:
            payload = await request.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise web.HTTPBadRequest(text="Request body must be valid JSON.") from exc
        if not isinstance(payload, dict) or set(payload) != {"api_url"}:
            raise web.HTTPBadRequest(text="Gemma settings must contain exactly api_url.")
        try:
            validated_url = request.app[GEMMA_KEY]._validated_api_url(payload["api_url"])
        except ValueError as exc:
            raise web.HTTPBadRequest(text=str(exc)) from exc
        audit_store = operation_audit(request)
        username = request.headers["X-Atlas-Authenticated"]
        operation = await asyncio.to_thread(
            audit_store.begin,
            username,
            "gemma",
            "configure",
            "endpoint",
            {},
            ["api_url"],
        )
        try:
            settings = await asyncio.to_thread(request.app[GEMMA_KEY].update_api_url, validated_url)
        except (OSError, ValueError) as exc:
            await asyncio.to_thread(audit_store.complete, operation["id"], username, "failed", "Gemma endpoint update failed.")
            LOGGER.exception("Gemma endpoint update failed for user=%s.", username)
            raise web.HTTPInternalServerError(text="Gemma endpoint could not be saved. Check the server log for details.") from exc
        await asyncio.to_thread(audit_store.complete, operation["id"], username, "succeeded")
        LOGGER.info("Gemma endpoint updated by user=%s.", username)
        return web.json_response(settings)

    app.router.add_get("/hosts", list_services)
    app.router.add_post("/hosts/{host_id}/services/{program}/{action}", change_service_state)
    app.router.add_post("/maintenance/materialized-views/refresh", refresh_views)
    app.router.add_get("/operations/records", list_operations)
    app.router.add_post("/operations/records", begin_operation)
    app.router.add_patch("/operations/records/{operation_id}", complete_operation)
    app.router.add_post("/gemma/chat", gemma_chat)
    app.router.add_get("/gemma/settings", get_gemma_settings)
    app.router.add_put("/gemma/settings", update_gemma_settings)
    return app


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the control gateway."""
    parser = argparse.ArgumentParser(description="Botjagwar Atlas Supervisor control gateway")
    parser.add_argument("--config", type=Path, default=Path("/etc/botjagwar/supervisor-control.ini"))
    parser.add_argument("--token-file", type=Path, default=Path("/etc/botjagwar/supervisor-control-gateway.token"))
    parser.add_argument("--audit-db", type=Path, default=Path("/var/lib/botjagwar/atlas_operations.sqlite3"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8002)
    return parser.parse_args()


def main() -> None:
    """Run the Supervisor control gateway on a loopback address."""
    args = parse_args()
    logging.basicConfig(level=logging.INFO)
    hosts = load_hosts(args.config)
    gateway_token = args.token_file.read_text(encoding="ascii").strip()
    config_path = Path(os.environ.get("BOTJAGWAR_CONFIG", "/etc/botjagwar/config.ini"))
    web.run_app(
        create_app(
            SupervisorControl(hosts),
            gateway_token,
            OperationAudit(args.audit_db),
            AtlasMaintenance(config_path),
            GemmaChat(config_path),
        ),
        host=args.host,
        port=args.port,
    )


if __name__ == "__main__":
    main()
