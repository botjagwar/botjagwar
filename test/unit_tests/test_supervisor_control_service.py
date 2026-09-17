import asyncio
import logging
import xmlrpc.client
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer, make_mocked_request

from supervisor_control_service import AtlasMaintenance, GemmaChat, OperationAudit, SupervisorControl, SupervisorHost, authenticated_proxy_only, create_app, load_hosts


class FakeSupervisor:
    """Provide an in-memory subset of Supervisor's XML-RPC API."""

    def __init__(self, state: str = "STOPPED") -> None:
        self.state = state
        self.start_calls: list[tuple[str, bool]] = []
        self.stop_calls: list[tuple[str, bool]] = []

    def getAllProcessInfo(self) -> list[dict[str, Any]]:  # noqa: N802
        """Return one fake process with the current state."""
        return [{
            "name": "dictionary_service_1",
            "statename": self.state,
            "description": self.state.lower(),
            "pid": 123 if self.state == "RUNNING" else 0,
            "start": 1,
        }]

    def startProcess(self, name: str, wait: bool = True) -> bool:  # noqa: N802
        """Start the fake process."""
        self.start_calls.append((name, wait))
        self.state = "RUNNING"
        return True

    def stopProcess(self, name: str, wait: bool = True) -> bool:  # noqa: N802
        """Stop the fake process."""
        self.stop_calls.append((name, wait))
        self.state = "STOPPED"
        return True


class FakeGemmaResponse:
    """Provide the successful response methods used by GemmaChat."""

    def raise_for_status(self) -> None:
        """Represent a successful remote response."""

    def json(self) -> dict[str, Any]:
        """Return one OpenAI-compatible completion."""
        return {"choices": [{"message": {"content": "  A useful answer.  "}}]}


def write_config(path: Path, *, url: str = "https://supervisor.internal/RPC2", programs: str = "dictionary_service_1") -> None:
    """Write one test Supervisor host configuration."""
    path.write_text(
        "[host:dictionary]\n"
        "label = Dictionary backend\n"
        f"url = {url}\n"
        "username = atlas-control\n"
        "password = secret\n"
        f"programs = {programs}\n",
        encoding="utf-8",
    )


def run_middleware(coroutine: Any) -> Any:
    """Run middleware while leaving a valid loop for legacy tests that follow."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(coroutine)


def gateway_headers(write_header: str | None = None, *, username: str = "alice") -> dict[str, str]:
    """Return authenticated gateway headers for one test request."""
    headers = {
        "X-Atlas-Gateway-Token": "gateway-secret",
        "X-Atlas-Authenticated": username,
    }
    if write_header is not None:
        headers[write_header] = "1"
    return headers


async def request_app(
    app: web.Application,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
    data: str | None = None,
) -> tuple[int, Any]:
    """Issue one request against an aiohttp application and decode its response."""
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        response = await client.request(method, path, headers=headers, json=json_body, data=data)
        if response.content_type == "application/json":
            return response.status, await response.json()
        return response.status, await response.text()
    finally:
        await client.close()


def test_load_hosts_accepts_https_and_allowlisted_programs(tmp_path: Path) -> None:
    """A valid host keeps credentials and explicit program names server-side."""
    config = tmp_path / "supervisor.ini"
    write_config(config)

    hosts = load_hosts(config)

    assert hosts["dictionary"].url == "https://supervisor.internal/RPC2"
    assert hosts["dictionary"].programs == ("dictionary_service_1",)


def test_load_hosts_rejects_plaintext_remote_credentials(tmp_path: Path) -> None:
    """Remote Supervisor credentials must not cross the network over HTTP."""
    config = tmp_path / "supervisor.ini"
    write_config(config, url="http://192.168.1.155:9001/RPC2")

    with pytest.raises(ValueError, match="must use HTTPS"):
        load_hosts(config)


@pytest.mark.parametrize("program", ["botjagwar_atlas", "load_balancer", "supervisor_control_service"])
def test_load_hosts_rejects_privileged_or_self_control(tmp_path: Path, program: str) -> None:
    """Atlas cannot stop its own security boundary or privileged unrelated services."""
    config = tmp_path / "supervisor.ini"
    write_config(config, programs=program)

    with pytest.raises(ValueError, match="cannot be controlled"):
        load_hosts(config)


def test_change_state_starts_allowlisted_service() -> None:
    """Start invokes only the fixed allowlisted Supervisor program."""
    host = SupervisorHost("dictionary", "Dictionary", "https://host/RPC2", "user", "secret", ("dictionary_service_1",))
    supervisor = FakeSupervisor()
    control = SupervisorControl({host.identifier: host}, lambda configured: supervisor)

    service = control.change_state("dictionary", "dictionary_service_1", "start")

    assert supervisor.start_calls == [("dictionary_service_1", True)]
    assert service["running"] is True


def test_gemma_chat_uses_protected_server_configuration(tmp_path: Path) -> None:
    """Forward conversations without returning endpoint credentials to Atlas."""
    config = tmp_path / "config.ini"
    config.write_text(
        "[gemma]\n"
        "api_url = https://gemma.example/v1/chat/completions\n"
        "model = gemma-remote\n"
        "api_key = secret-token\n",
        encoding="utf-8",
    )
    request_post = MagicMock(return_value=FakeGemmaResponse())
    gemma = GemmaChat(config, request_post=request_post)
    messages = [{"role": "user", "content": "Hello"}]

    result = gemma.complete(messages)

    assert result == {"model": "gemma-remote", "content": "A useful answer."}
    request_post.assert_called_once_with(
        "https://gemma.example/v1/chat/completions",
        headers={"Authorization": "Bearer secret-token"},
        json={"model": "gemma-remote", "messages": messages, "temperature": 0.2},
        timeout=(3.05, 120.0),
    )


def test_gemma_chat_accepts_plaintext_private_network_endpoint(tmp_path: Path) -> None:
    """A private hosted model can use HTTP without traversing a public network."""
    config = tmp_path / "config.ini"
    config.write_text(
        "[gemma]\napi_url = http://192.168.1.155:8891/v1/chat/completions\n",
        encoding="utf-8",
    )

    gemma = GemmaChat(config)

    assert gemma.settings()["api_url"] == "http://192.168.1.155:8891/v1/chat/completions"


@pytest.mark.parametrize(
    "api_url",
    [
        "http://93.184.216.34/v1/chat/completions",
        "http://169.254.169.254/latest/meta-data",
        "http://gemma.example/v1/chat/completions",
        "ftp://gemma.example/model",
        "https://user:secret@gemma.example/model",
        "https://gemma.example:invalid/model",
        "https://gemma.example/model#fragment",
    ],
)
def test_gemma_chat_rejects_unsafe_remote_endpoints(tmp_path: Path, api_url: str) -> None:
    """Public HTTP and credential-bearing endpoints are rejected."""
    config = tmp_path / "config.ini"
    config.write_text(f"[gemma]\napi_url = {api_url}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Gemma API URL"):
        GemmaChat(config)


def test_all_statuses_preserves_configured_host_order() -> None:
    """Concurrent host checks retain stable configured ordering for the UI."""
    first = SupervisorHost("first", "First", "https://first/RPC2", "user", "secret", ("dictionary_service_1",))
    second = SupervisorHost("second", "Second", "https://second/RPC2", "user", "secret", ("dictionary_service_1",))
    control = SupervisorControl({"first": first, "second": second}, lambda configured: FakeSupervisor("RUNNING"))

    statuses = control.all_statuses()

    assert [status["id"] for status in statuses] == ["first", "second"]


def test_change_state_is_idempotent() -> None:
    """Starting an already running service does not issue a duplicate command."""
    host = SupervisorHost("dictionary", "Dictionary", "https://host/RPC2", "user", "secret", ("dictionary_service_1",))
    supervisor = FakeSupervisor("RUNNING")
    control = SupervisorControl({host.identifier: host}, lambda configured: supervisor)

    control.change_state("dictionary", "dictionary_service_1", "start")

    assert supervisor.start_calls == []


def test_change_state_rejects_unallowlisted_program() -> None:
    """Browser-controlled service IDs never reach the Supervisor client."""
    host = SupervisorHost("dictionary", "Dictionary", "https://host/RPC2", "user", "secret", ("dictionary_service_1",))
    factory = MagicMock()
    control = SupervisorControl({host.identifier: host}, factory)

    with pytest.raises(KeyError):
        control.change_state("dictionary", "load_balancer", "stop")
    factory.assert_not_called()


def test_host_status_does_not_log_credential_bearing_protocol_error(caplog: pytest.LogCaptureFixture) -> None:
    """Remote HTTP failures never disclose credentials embedded in XML-RPC URLs."""
    host = SupervisorHost("dictionary", "Dictionary", "https://host/RPC2", "user", "top-secret", ("dictionary_service_1",))

    class FailingSupervisor:
        def getAllProcessInfo(self) -> list[dict[str, Any]]:  # noqa: N802
            raise xmlrpc.client.ProtocolError("https://user:top-secret@host/RPC2", 401, "Unauthorized", {})

    control = SupervisorControl({host.identifier: host}, lambda configured: FailingSupervisor())

    with caplog.at_level(logging.WARNING):
        result = control.host_status("dictionary")

    assert result["available"] is False
    assert "top-secret" not in caplog.text


def test_create_app_requires_gateway_token() -> None:
    """The localhost HTTP gateway cannot run without its Nginx shared secret."""
    with pytest.raises(ValueError, match="gateway token"):
        create_app(SupervisorControl({}), "")


def test_gateway_rejects_browser_spoofed_authentication_without_token() -> None:
    """A local caller cannot impersonate Nginx by supplying only the username header."""
    app = create_app(SupervisorControl({}), "gateway-secret")
    request = make_mocked_request("GET", "/hosts", headers={"X-Atlas-Authenticated": "atlas"}, app=app)
    handler = MagicMock()

    with pytest.raises(web.HTTPUnauthorized):
        run_middleware(authenticated_proxy_only(request, handler))
    handler.assert_not_called()


def test_gateway_rejects_post_without_control_header() -> None:
    """State changes require the custom same-origin control header."""
    app = create_app(SupervisorControl({}), "gateway-secret")
    request = make_mocked_request(
        "POST",
        "/hosts/dictionary/services/dictionary_service_1/start",
        headers={
            "X-Atlas-Gateway-Token": "gateway-secret",
            "X-Atlas-Authenticated": "atlas",
        },
        app=app,
    )
    handler = MagicMock()

    with pytest.raises(web.HTTPForbidden):
        run_middleware(authenticated_proxy_only(request, handler))
    handler.assert_not_called()


def test_gateway_accepts_authenticated_same_origin_post() -> None:
    """Valid Nginx-authenticated control requests reach the route handler."""
    app = create_app(SupervisorControl({}), "gateway-secret")
    request = make_mocked_request(
        "POST",
        "/hosts/dictionary/services/dictionary_service_1/start",
        headers={
            "Host": "atlas.example:38000",
            "Origin": "https://atlas.example:38000",
            "X-Forwarded-Host": "atlas.example:38000",
            "X-Atlas-Gateway-Token": "gateway-secret",
            "X-Atlas-Authenticated": "atlas",
            "X-Atlas-Service-Control": "1",
            "Sec-Fetch-Site": "same-origin",
        },
        app=app,
    )

    async def handler(_: web.Request) -> web.Response:
        return web.Response(status=204)

    response = run_middleware(authenticated_proxy_only(request, handler))

    assert response.status == 204


def test_gateway_requires_dedicated_maintenance_header() -> None:
    """Maintenance writes cannot reuse the generic service-control header."""
    app = create_app(SupervisorControl({}), "gateway-secret")
    request = make_mocked_request(
        "POST",
        "/maintenance/materialized-views/refresh",
        headers={
            "X-Atlas-Gateway-Token": "gateway-secret",
            "X-Atlas-Authenticated": "atlas",
            "X-Atlas-Service-Control": "1",
        },
        app=app,
    )

    with pytest.raises(web.HTTPForbidden):
        run_middleware(authenticated_proxy_only(request, MagicMock()))


def test_gateway_accepts_authenticated_maintenance_header() -> None:
    """The fixed maintenance route accepts its same-origin custom header."""
    app = create_app(SupervisorControl({}), "gateway-secret")
    request = make_mocked_request(
        "POST",
        "/maintenance/materialized-views/refresh",
        headers={
            "X-Atlas-Gateway-Token": "gateway-secret",
            "X-Atlas-Authenticated": "atlas",
            "X-Atlas-Maintenance": "1",
        },
        app=app,
    )

    async def handler(_: web.Request) -> web.Response:
        return web.Response(status=204)

    assert run_middleware(authenticated_proxy_only(request, handler)).status == 204


def test_gateway_rejects_cross_origin_post() -> None:
    """A valid gateway token does not authorize a cross-origin state change."""
    app = create_app(SupervisorControl({}), "gateway-secret")
    request = make_mocked_request(
        "POST",
        "/hosts/dictionary/services/dictionary_service_1/start",
        headers={
            "Origin": "https://attacker.example",
            "X-Forwarded-Host": "atlas.example:38000",
            "X-Atlas-Gateway-Token": "gateway-secret",
            "X-Atlas-Authenticated": "atlas",
            "X-Atlas-Service-Control": "1",
        },
        app=app,
    )
    handler = MagicMock()

    with pytest.raises(web.HTTPForbidden):
        run_middleware(authenticated_proxy_only(request, handler))
    handler.assert_not_called()


def test_operation_audit_persists_and_filters_records(tmp_path: Path) -> None:
    """Audit records survive new store instances and support bounded filters."""
    path = tmp_path / "operations.sqlite3"
    audit = OperationAudit(path)
    first = audit.begin("alice", "database", "update", "word", {"id": 12}, ["word"])
    second = audit.begin("bob", "translator", "publish", "wiktionary-page", {"language": "en", "title": "house"}, [])

    completed = audit.complete(second["id"], "bob", "succeeded")
    reloaded = OperationAudit(path)

    assert first["outcome"] == "pending"
    assert completed is not None and completed["completed_at"] is not None
    assert [record["id"] for record in reloaded.list(10)] == [second["id"], first["id"]]
    assert reloaded.list(10, service="translator")[0]["target"] == {"language": "en", "title": "house"}
    assert reloaded.list(10, outcome="pending")[0]["changed_fields"] == ["word"]


def test_operation_audit_only_completes_owner_pending_record(tmp_path: Path) -> None:
    """An authenticated user cannot complete another user's operation twice."""
    audit = OperationAudit(tmp_path / "operations.sqlite3")
    operation = audit.begin("alice", "dictionary", "delete", "entry", {"id": 4}, [])

    assert audit.complete(operation["id"], "bob", "failed") is None
    assert audit.complete(operation["id"], "alice", "succeeded") is not None
    assert audit.complete(operation["id"], "alice", "failed") is None


def test_atlas_maintenance_uses_protected_database_configuration(tmp_path: Path, mocker) -> None:
    """The browser cannot choose the database or materialized views to refresh."""
    config = tmp_path / "config.ini"
    load_uri = mocker.patch("supervisor_control_service.load_database_uri", return_value="postgresql://database")
    refresh = mocker.patch("supervisor_control_service.refresh_materialized_views", return_value=9)

    result = AtlasMaintenance(config).refresh_materialized_views()

    load_uri.assert_called_once_with(config)
    refresh.assert_called_once_with("postgresql://database")
    assert result["refreshed_views"] == 9
    assert result["completed_at"].endswith("+00:00")


def test_maintenance_route_refreshes_and_audits_operation(tmp_path: Path) -> None:
    """The authenticated HTTP route completes its database operation audit."""
    audit = OperationAudit(tmp_path / "operations.sqlite3")
    maintenance = MagicMock(spec=AtlasMaintenance)
    maintenance.refresh_materialized_views.return_value = {
        "refreshed_views": 9,
        "completed_at": "2026-08-14T00:00:00+00:00",
    }
    app = create_app(SupervisorControl({}), "gateway-secret", audit, maintenance)

    async def invoke() -> tuple[int, dict[str, Any]]:
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            response = await client.post(
                "/maintenance/materialized-views/refresh",
                headers={
                    "X-Atlas-Gateway-Token": "gateway-secret",
                    "X-Atlas-Authenticated": "alice",
                    "X-Atlas-Maintenance": "1",
                },
            )
            return response.status, await response.json()
        finally:
            await client.close()

    status, result = asyncio.run(invoke())

    assert status == 200
    assert result["refreshed_views"] == 9
    operation = audit.list(1)[0]
    assert (operation["service"], operation["action"], operation["resource"], operation["outcome"]) == (
        "database",
        "refresh",
        "materialized-views",
        "succeeded",
    )


def test_hosts_route_returns_control_statuses() -> None:
    """The host route exposes the status payload returned by the control layer."""
    control = MagicMock(spec=SupervisorControl)
    control.all_statuses.return_value = [{"id": "dictionary", "label": "Dictionary", "available": True, "services": []}]
    app = create_app(control, "gateway-secret")

    status, result = asyncio.run(request_app(app, "GET", "/hosts", headers=gateway_headers()))

    assert status == 200
    assert result == {"hosts": control.all_statuses.return_value}
    control.all_statuses.assert_called_once_with()


@pytest.mark.parametrize(
    ("control_result", "expected_status", "expected_outcome", "expected_error"),
    [
        ({"id": "dictionary_service_1", "state": "running", "running": True}, 200, "succeeded", None),
        (LookupError("dictionary_service_1"), 409, "failed", "Managed service is not registered."),
        (KeyError("dictionary/dictionary_service_1"), 404, "failed", "Unknown managed service."),
        (ValueError("restart"), 400, "failed", "Unsupported service action."),
        (OSError("connection refused"), 502, "failed", "Remote Supervisor is unavailable."),
    ],
)
def test_service_state_route_maps_results_and_errors(
    tmp_path: Path,
    control_result: dict[str, Any] | Exception,
    expected_status: int,
    expected_outcome: str,
    expected_error: str | None,
) -> None:
    """Service state outcomes are audited and mapped to stable HTTP statuses."""
    audit = OperationAudit(tmp_path / "operations.sqlite3")
    control = MagicMock(spec=SupervisorControl)
    if isinstance(control_result, Exception):
        control.change_state.side_effect = control_result
    else:
        control.change_state.return_value = control_result
    app = create_app(control, "gateway-secret", audit)

    status, result = asyncio.run(
        request_app(
            app,
            "POST",
            "/hosts/dictionary/services/dictionary_service_1/start",
            headers=gateway_headers("X-Atlas-Service-Control"),
        )
    )

    assert status == expected_status
    operation = audit.list(1)[0]
    assert operation["outcome"] == expected_outcome
    assert operation["error_summary"] == expected_error
    assert operation["username"] == "alice"
    assert operation["target"] == {"host_id": "dictionary"}
    control.change_state.assert_called_once_with("dictionary", "dictionary_service_1", "start")
    if expected_status == 200:
        assert result == control_result


def test_operation_routes_support_create_list_and_complete_lifecycle(tmp_path: Path) -> None:
    """Operation records can be created, paged, filtered, and completed over HTTP."""
    audit = OperationAudit(tmp_path / "operations.sqlite3")
    app = create_app(SupervisorControl({}), "gateway-secret", audit)
    write_headers = gateway_headers("X-Atlas-Operation-Audit")
    payload = {
        "service": "dictionary",
        "action": "update",
        "resource": "entry",
        "target": {"id": 12},
        "changed_fields": ["word"],
    }

    async def invoke() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            first_response = await client.post("/operations/records", headers=write_headers, json=payload)
            first = await first_response.json()
            second_response = await client.post("/operations/records", headers=write_headers, json=payload)
            second = await second_response.json()
            page_response = await client.get(
                "/operations/records?limit=1&service=dictionary&outcome=pending",
                headers=gateway_headers(),
            )
            page = await page_response.json()
            complete_response = await client.patch(
                f"/operations/records/{second['id']}",
                headers=write_headers,
                json={"outcome": "succeeded", "error_summary": "ignored on success"},
            )
            completed = await complete_response.json()
            before_response = await client.get(
                f"/operations/records?before={second['id']}&service=dictionary&outcome=pending",
                headers=gateway_headers(),
            )
            before = await before_response.json()
            assert (first_response.status, second_response.status, page_response.status, complete_response.status, before_response.status) == (
                201,
                201,
                200,
                200,
                200,
            )
            return first, page, completed, before
        finally:
            await client.close()

    first, page, completed, before = asyncio.run(invoke())

    assert page["operations"][0]["id"] == completed["id"]
    assert page["next_before"] == completed["id"]
    assert completed["outcome"] == "succeeded"
    assert completed["error_summary"] == "ignored on success"
    assert [operation["id"] for operation in before["operations"]] == [first["id"]]


@pytest.mark.parametrize(
    "query",
    [
        "limit=invalid",
        "service=unknown",
        "outcome=unknown",
    ],
)
def test_operation_list_rejects_invalid_queries(tmp_path: Path, query: str) -> None:
    """Operation pagination and filters reject unsupported query values."""
    app = create_app(SupervisorControl({}), "gateway-secret", OperationAudit(tmp_path / "operations.sqlite3"))

    status, _ = asyncio.run(request_app(app, "GET", f"/operations/records?{query}", headers=gateway_headers()))

    assert status == 400


@pytest.mark.parametrize(
    "payload",
    [
        {"service": "supervisor", "action": "start", "resource": "service"},
        {"service": "dictionary", "action": "update", "resource": ""},
        {"service": "dictionary", "action": "update", "resource": "entry", "changed_fields": ["x" * 101]},
        {"service": "dictionary", "action": "update", "resource": "entry", "target": {"value": "x" * 2049}},
    ],
)
def test_operation_creation_rejects_invalid_metadata(tmp_path: Path, payload: dict[str, Any]) -> None:
    """Operation creation validates classification and bounded metadata."""
    app = create_app(SupervisorControl({}), "gateway-secret", OperationAudit(tmp_path / "operations.sqlite3"))

    status, _ = asyncio.run(
        request_app(
            app,
            "POST",
            "/operations/records",
            headers=gateway_headers("X-Atlas-Operation-Audit"),
            json_body=payload,
        )
    )

    assert status == 400


def test_operation_creation_accepts_page_check_action(tmp_path: Path) -> None:
    """The page checker audit action is classified under the translator service."""
    app = create_app(SupervisorControl({}), "gateway-secret", OperationAudit(tmp_path / "operations.sqlite3"))

    status, body = asyncio.run(
        request_app(
            app,
            "POST",
            "/operations/records",
            headers=gateway_headers("X-Atlas-Operation-Audit"),
            json_body={
                "service": "translator",
                "action": "check",
                "resource": "wiktionary-page",
                "target": {"language": "mg", "titles": ["alika"]},
            },
        )
    )

    assert status == 201
    assert body["service"] == "translator"
    assert body["action"] == "check"


def test_operation_creation_accepts_page_checker_configure_action(
    tmp_path: Path,
) -> None:
    """Page-checker settings writes are valid translator audit operations."""
    app = create_app(
        SupervisorControl({}),
        "gateway-secret",
        OperationAudit(tmp_path / "operations.sqlite3"),
    )

    status, body = asyncio.run(
        request_app(
            app,
            "POST",
            "/operations/records",
            headers=gateway_headers("X-Atlas-Operation-Audit"),
            json_body={
                "service": "translator",
                "action": "configure",
                "resource": "page-checker-settings",
                "target": {},
                "changed_fields": ["watched_users"],
            },
        )
    )

    assert status == 201
    assert body["service"] == "translator"
    assert body["action"] == "configure"


def test_operation_completion_rejects_invalid_or_missing_pending_record(tmp_path: Path) -> None:
    """Completion rejects invalid outcomes and records not owned by the caller."""
    audit = OperationAudit(tmp_path / "operations.sqlite3")
    operation = audit.begin("alice", "dictionary", "update", "entry", {"id": 12}, [])
    app = create_app(SupervisorControl({}), "gateway-secret", audit)

    async def invoke() -> tuple[int, int]:
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            invalid = await client.patch(
                f"/operations/records/{operation['id']}",
                headers=gateway_headers("X-Atlas-Operation-Audit"),
                json={"outcome": "pending"},
            )
            missing = await client.patch(
                f"/operations/records/{operation['id']}",
                headers=gateway_headers("X-Atlas-Operation-Audit", username="bob"),
                json={"outcome": "failed", "error_summary": 42},
            )
            return invalid.status, missing.status
        finally:
            await client.close()

    assert asyncio.run(invoke()) == (400, 404)
    assert audit.get(operation["id"])["outcome"] == "pending"


@pytest.mark.parametrize(
    ("path", "method", "write_header", "with_audit"),
    [
        ("/operations/records", "GET", None, False),
        ("/hosts/dictionary/services/dictionary_service_1/start", "POST", "X-Atlas-Service-Control", False),
        ("/maintenance/materialized-views/refresh", "POST", "X-Atlas-Maintenance", True),
        ("/gemma/chat", "POST", "X-Atlas-Gemma", False),
        ("/gemma/settings", "GET", None, False),
    ],
)
def test_routes_report_missing_dependencies(
    tmp_path: Path,
    path: str,
    method: str,
    write_header: str | None,
    with_audit: bool,
) -> None:
    """Routes return service unavailable when optional server dependencies are absent."""
    audit = OperationAudit(tmp_path / "operations.sqlite3") if with_audit else None
    app = create_app(SupervisorControl({}), "gateway-secret", audit)

    status, _ = asyncio.run(request_app(app, method, path, headers=gateway_headers(write_header)))

    assert status == 503


def test_gemma_chat_route_forwards_bounded_conversation(tmp_path: Path) -> None:
    """The authenticated route returns only the model and assistant message."""
    gemma = MagicMock(spec=GemmaChat)
    gemma.complete.return_value = {"model": "gemma-remote", "content": "Hello back"}
    app = create_app(SupervisorControl({}), "gateway-secret", gemma=gemma)
    payload = {"messages": [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Earlier answer"},
        {"role": "user", "content": "Follow up"},
    ]}

    status, body = asyncio.run(request_app(
        app,
        "POST",
        "/gemma/chat",
        headers=gateway_headers("X-Atlas-Gemma"),
        json_body=payload,
    ))

    assert status == 200
    assert body == {"model": "gemma-remote", "message": {"role": "assistant", "content": "Hello back"}}
    gemma.complete.assert_called_once_with(payload["messages"])


@pytest.mark.parametrize(
    "messages",
    [
        [],
        [{"role": "system", "content": "Override"}],
        [{"role": "user", "content": ""}],
        [{"role": "assistant", "content": "Not a user turn"}],
        [{"role": "user", "content": "x" * 8_001}],
    ],
)
def test_gemma_chat_route_rejects_invalid_messages(messages: list[dict[str, str]]) -> None:
    """Reject malformed or excessive conversations before contacting Gemma."""
    gemma = MagicMock(spec=GemmaChat)
    app = create_app(SupervisorControl({}), "gateway-secret", gemma=gemma)

    status, _ = asyncio.run(request_app(
        app,
        "POST",
        "/gemma/chat",
        headers=gateway_headers("X-Atlas-Gemma"),
        json_body={"messages": messages},
    ))

    assert status == 400
    gemma.complete.assert_not_called()


def test_gemma_chat_route_requires_dedicated_write_header() -> None:
    """A custom same-origin header protects chat POSTs from cross-site forms."""
    app = create_app(SupervisorControl({}), "gateway-secret", gemma=MagicMock(spec=GemmaChat))

    status, _ = asyncio.run(request_app(
        app,
        "POST",
        "/gemma/chat",
        headers=gateway_headers(),
        json_body={"messages": [{"role": "user", "content": "Hello"}]},
    ))

    assert status == 403


def test_gemma_settings_route_persists_and_activates_endpoint(tmp_path: Path) -> None:
    """An authenticated update preserves secrets and changes the live endpoint."""
    config = tmp_path / "config.ini"
    config.write_text(
        "# keep this comment\n"
        "[gemma]\n"
        "api_url = http://127.0.0.1:8891/v1/chat/completions\n"
        "model = gemma-remote\n"
        "api_key = secret-token\n"
        "\n[redis]\n"
        "host = localhost\n",
        encoding="utf-8",
    )
    request_post = MagicMock(return_value=FakeGemmaResponse())
    gemma = GemmaChat(config, request_post=request_post)
    audit = OperationAudit(tmp_path / "operations.sqlite3")
    app = create_app(SupervisorControl({}), "gateway-secret", audit=audit, gemma=gemma)

    initial_status, initial = asyncio.run(request_app(
        app,
        "GET",
        "/gemma/settings",
        headers=gateway_headers(),
    ))
    update_app = create_app(SupervisorControl({}), "gateway-secret", audit=audit, gemma=gemma)
    update_status, updated = asyncio.run(request_app(
        update_app,
        "PUT",
        "/gemma/settings",
        headers=gateway_headers("X-Atlas-Gemma"),
        json_body={"api_url": "https://gemma.example/v1/chat/completions"},
    ))

    assert initial_status == 200
    assert initial == {"api_url": "http://127.0.0.1:8891/v1/chat/completions", "model": "gemma-remote"}
    assert update_status == 200
    assert updated == {"api_url": "https://gemma.example/v1/chat/completions", "model": "gemma-remote"}
    assert gemma.settings() == updated
    assert gemma.complete([{"role": "user", "content": "Hello"}])["content"] == "A useful answer."
    assert request_post.call_args.args[0] == "https://gemma.example/v1/chat/completions"
    persisted = config.read_text(encoding="utf-8")
    assert "# keep this comment" in persisted
    assert "api_url = https://gemma.example/v1/chat/completions" in persisted
    assert "api_key = secret-token" in persisted
    assert "[redis]\nhost = localhost" in persisted
    assert config.stat().st_mode & 0o777 == 0o600
    assert audit.list(1)[0]["service"] == "gemma"
    assert audit.list(1)[0]["outcome"] == "succeeded"


def test_gemma_settings_route_rejects_plaintext_remote_endpoint(tmp_path: Path) -> None:
    """Do not persist credentials or model traffic over remote plaintext HTTP."""
    config = tmp_path / "config.ini"
    config.write_text("[gemma]\napi_url = http://localhost:8891/v1/chat/completions\n", encoding="utf-8")
    gemma = GemmaChat(config)
    audit = OperationAudit(tmp_path / "operations.sqlite3")
    app = create_app(SupervisorControl({}), "gateway-secret", audit=audit, gemma=gemma)

    status, _ = asyncio.run(request_app(
        app,
        "PUT",
        "/gemma/settings",
        headers=gateway_headers("X-Atlas-Gemma"),
        json_body={"api_url": "http://gemma.example/v1/chat/completions"},
    ))

    assert status == 400
    assert gemma.settings()["api_url"] == "http://localhost:8891/v1/chat/completions"
    assert audit.list(1) == []


def test_gemma_settings_route_requires_dedicated_write_header(tmp_path: Path) -> None:
    """Gemma endpoint updates require the custom same-origin request header."""
    config = tmp_path / "config.ini"
    config.write_text("[gemma]\napi_url = http://localhost:8891/v1/chat/completions\n", encoding="utf-8")
    app = create_app(SupervisorControl({}), "gateway-secret", gemma=GemmaChat(config))

    status, _ = asyncio.run(request_app(
        app,
        "PUT",
        "/gemma/settings",
        headers=gateway_headers(),
        json_body={"api_url": "https://gemma.example/v1/chat/completions"},
    ))

    assert status == 403


def test_maintenance_route_audits_refresh_errors(tmp_path: Path) -> None:
    """A maintenance failure returns 500 and marks its audit operation failed."""
    audit = OperationAudit(tmp_path / "operations.sqlite3")
    maintenance = MagicMock(spec=AtlasMaintenance)
    maintenance.refresh_materialized_views.side_effect = RuntimeError("refresh failed")
    app = create_app(SupervisorControl({}), "gateway-secret", audit, maintenance)

    status, body = asyncio.run(
        request_app(
            app,
            "POST",
            "/maintenance/materialized-views/refresh",
            headers=gateway_headers("X-Atlas-Maintenance"),
        )
    )

    assert status == 500
    assert "Check the server log" in body
    operation = audit.list(1)[0]
    assert operation["outcome"] == "failed"
    assert operation["error_summary"] == "Materialized-view refresh failed."


@pytest.mark.parametrize(
    ("headers", "expected_status"),
    [
        ({"X-Atlas-Gateway-Token": "gateway-secret"}, 401),
        (
            {
                **gateway_headers("X-Atlas-Service-Control"),
                "Sec-Fetch-Site": "cross-site",
            },
            403,
        ),
    ],
)
def test_gateway_rejects_missing_identity_and_cross_site_fetches(headers: dict[str, str], expected_status: int) -> None:
    """Middleware rejects omitted proxy identity and browser cross-site writes."""
    app = create_app(SupervisorControl({}), "gateway-secret")
    method = "POST" if "Sec-Fetch-Site" in headers else "GET"
    path = "/hosts/dictionary/services/dictionary_service_1/start" if method == "POST" else "/hosts"

    status, _ = asyncio.run(request_app(app, method, path, headers=headers))

    assert status == expected_status


def test_gateway_rejects_patch_without_audit_header() -> None:
    """Audit completion requires the same-origin custom request header."""
    app = create_app(SupervisorControl({}), "gateway-secret")
    request = make_mocked_request(
        "PATCH",
        "/operations/records/1",
        headers={"X-Atlas-Gateway-Token": "gateway-secret", "X-Atlas-Authenticated": "atlas"},
        app=app,
    )
    handler = MagicMock()

    with pytest.raises(web.HTTPForbidden):
        run_middleware(authenticated_proxy_only(request, handler))
    handler.assert_not_called()


def test_operation_completion_rejects_oversized_payloads(tmp_path: Path) -> None:
    """Audit completion bounds request bodies just like operation creation."""
    audit = OperationAudit(tmp_path / "operations.sqlite3")
    app = create_app(SupervisorControl({}), "gateway-secret", audit)
    oversized = '{"outcome": "succeeded", "error_summary": "' + "x" * 5000 + '"}'

    async def invoke() -> int:
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            response = await client.patch(
                "/operations/records/1",
                data=oversized,
                headers={
                    "X-Atlas-Gateway-Token": "gateway-secret",
                    "X-Atlas-Authenticated": "alice",
                    "X-Atlas-Operation-Audit": "1",
                    "Content-Type": "application/json",
                },
            )
            return response.status
        finally:
            await client.close()

    status = run_middleware(invoke())

    assert status == 413
