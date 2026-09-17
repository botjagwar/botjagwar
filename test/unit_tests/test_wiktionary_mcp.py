"""Protocol-level tests for the local Wiktionary review MCP server."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict

import anyio
from mcp import Client
from mcp.server.mcpserver.exceptions import ToolError
import pytest

import api.wiktionary_mcp as wiktionary_mcp
from api.services.reviewed_wiktionary_fix import ReviewedWiktionaryFixError
from api.services.wiktionary_review_service import WiktionaryReviewError

@pytest.fixture(autouse=True)
def _configure_environment(monkeypatch: Any) -> None:
    monkeypatch.setenv("BOTJAGWAR_REVIEW_ENVIRONMENT_ID", "test-suite")


class DummyReviewService:
    def __init__(self, diff: str = "-old\n+new\n") -> None:
        self.diff = diff

    def _proposal(self, proposal_id: str = "proposal-1") -> Dict[str, Any]:
        return {
            "proposal_id": proposal_id,
            "approval_digest": "a" * 64,
            "diff_sha256": hashlib.sha256(self.diff.encode()).hexdigest(),
            "diff": self.diff,
        }

    def claim_unchecked_entry(self) -> Dict[str, Any]:
        return {"status": "empty", "task": None}

    def list_unchecked_entries(self, limit: int = 20) -> Dict[str, Any]:
        return {"tasks": [], "limit": limit}

    def get_unchecked_entry(self, event_id: str) -> Dict[str, Any]:
        if event_id == "missing":
            raise WiktionaryReviewError("Unknown page-check review event.")
        return {"event_id": event_id, "content_trust": "untrusted_page_check_evidence"}

    def get_english_snapshot(self, title: str) -> Dict[str, Any]:
        content = "English evidence"
        return {
            "language": "en",
            "title": title,
            "namespace": 0,
            "content": content,
            "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
            "entries": [{"language": "en"}],
            "parsed": True,
            "parse_error": None,
            "content_trust": "untrusted_wiktionary_content",
        }

    def get_malagasy_snapshot(self, event_id: str) -> Dict[str, Any]:
        content = "Malagasy evidence"
        return {
            "language": "mg",
            "title": event_id,
            "namespace": 0,
            "content": content,
            "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
            "entries": [{"language": "mg"}],
            "parsed": True,
            "parse_error": None,
            "content_trust": "untrusted_wiktionary_content",
        }

    def prepare_fix(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self._proposal() | {
            "args": list(args),
            "kwargs": kwargs,
        }

    def get_fix_proposal(self, proposal_id: str) -> Dict[str, Any]:
        return self._proposal(proposal_id) | {
            "state": "prepared",
        }

def test_mcp_exposes_review_tools_and_structured_results(monkeypatch: Any) -> None:
    service = DummyReviewService()
    monkeypatch.setattr(wiktionary_mcp, "_SERVICE", service)

    async def exercise_server() -> None:
        async with Client(wiktionary_mcp.mcp) as client:
            tools = await client.list_tools()
            names = {tool.name for tool in tools.tools}
            assert names == {
                "claim_unchecked_entry",
                "list_unchecked_entries",
                "get_unchecked_entry",
                "get_english_wiktionary_snapshot",
                "get_malagasy_wiktionary_snapshot",
                "prepare_wiktionary_fix",
                "get_wiktionary_fix_proposal",
            }
            result = await client.call_tool("list_unchecked_entries", {"limit": 7})
            assert result.is_error is False
            assert result.structured_content == {
                "result": {"tasks": [], "limit": 7}
            }

    anyio.run(exercise_server)


def test_mcp_returns_anticipated_workflow_error_to_caller(monkeypatch: Any) -> None:
    monkeypatch.setattr(wiktionary_mcp, "_SERVICE", DummyReviewService())

    async def exercise_server() -> None:
        async with Client(wiktionary_mcp.mcp) as client:
            result = await client.call_tool(
                "get_unchecked_entry", {"event_id": "missing"}
            )
            assert result.is_error is True
            assert "Unknown page-check review event" in result.content[0].text

    anyio.run(exercise_server)


def test_read_and_prepare_tools_delegate_to_review_service(monkeypatch: Any) -> None:
    service = DummyReviewService()
    monkeypatch.setattr(wiktionary_mcp, "_SERVICE", service)

    assert wiktionary_mcp.claim_unchecked_entry()["status"] == "empty"
    assert wiktionary_mcp.get_unchecked_entry("event-1")["event_id"] == "event-1"
    english = wiktionary_mcp.get_english_wiktionary_snapshot("cat")
    assert english["language"] == "en"
    assert english["title"] == "cat"
    assert english["evidence_chunk"] == "English evidence"
    malagasy = wiktionary_mcp.get_malagasy_wiktionary_snapshot("event-1")
    assert malagasy["language"] == "mg"
    assert malagasy["title"] == "event-1"
    assert malagasy["evidence_chunk"] == "Malagasy evidence"
    prepared = wiktionary_mcp.prepare_wiktionary_fix(
        "event-1", "a" * 64, "cat", "b" * 64, "replacement", "summary"
    )
    assert prepared["proposal_id"] == "proposal-1"
    assert prepared["args"][-1] == "summary"
    assert prepared["evidence_chunk"] == "-old\n+new\n"
    stored = wiktionary_mcp.get_wiktionary_fix_proposal("proposal-1")
    assert stored["proposal_id"] == "proposal-1"
    assert stored["state"] == "prepared"
    assert stored["evidence_chunk"] == "-old\n+new\n"


def test_snapshot_and_diff_evidence_are_position_addressed(monkeypatch: Any) -> None:
    monkeypatch.setattr(wiktionary_mcp, "_SERVICE", DummyReviewService())

    first = wiktionary_mcp.get_english_wiktionary_snapshot(
        "cat", offset=0, limit=7
    )
    second = wiktionary_mcp.get_english_wiktionary_snapshot(
        "cat", offset=first["evidence_next_offset"], limit=20
    )
    entries = wiktionary_mcp.get_english_wiktionary_snapshot(
        "cat", section="entries"
    )
    first_diff = wiktionary_mcp.get_wiktionary_fix_proposal(
        "proposal-1", diff_offset=0, diff_limit=5
    )
    diff = wiktionary_mcp.get_wiktionary_fix_proposal(
        "proposal-1",
        diff_offset=first_diff["evidence_next_offset"],
        diff_limit=5,
        diff_review_token=first_diff["diff_review_token"],
    )

    assert first["evidence_chunk"] + second["evidence_chunk"] == "English evidence"
    assert first["evidence_sha256"] == second["evidence_sha256"]
    assert second["evidence_complete"] is True
    assert entries["evidence_format"] == "canonical_json"
    assert entries["evidence_chunk"] == '[{"language":"en"}]'
    assert diff["evidence_chunk"] == "+new\n"


def test_diff_review_requires_contiguous_chunks(monkeypatch: Any) -> None:
    service = DummyReviewService("0123456789")
    monkeypatch.setattr(wiktionary_mcp, "_SERVICE", service)
    wiktionary_mcp._DIFF_REVIEW_PROGRESS.clear()  # pylint: disable=protected-access

    first = wiktionary_mcp.get_wiktionary_fix_proposal(
        "proposal-1", diff_offset=0, diff_limit=4
    )
    with pytest.raises(ToolError, match="contiguously"):
        wiktionary_mcp.get_wiktionary_fix_proposal(
            "proposal-1",
            diff_offset=8,
            diff_limit=2,
            diff_review_token=first["diff_review_token"],
        )
    second = wiktionary_mcp.get_wiktionary_fix_proposal(
        "proposal-1",
        diff_offset=first["evidence_next_offset"],
        diff_limit=4,
        diff_review_token=first["diff_review_token"],
    )
    complete = wiktionary_mcp.get_wiktionary_fix_proposal(
        "proposal-1",
        diff_offset=second["evidence_next_offset"],
        diff_limit=4,
        diff_review_token=second["diff_review_token"],
    )

    assert complete["evidence_complete"] is True
    assert complete["diff_review_token"] == first["diff_review_token"]


def test_diff_review_token_expires(monkeypatch: Any) -> None:
    monkeypatch.setattr(wiktionary_mcp, "_SERVICE", DummyReviewService("0123456789"))
    wiktionary_mcp._DIFF_REVIEW_PROGRESS.clear()  # pylint: disable=protected-access
    now = [0.0]
    monkeypatch.setattr(wiktionary_mcp.time, "monotonic", lambda: now[0])
    first = wiktionary_mcp.get_wiktionary_fix_proposal(
        "proposal-1", diff_offset=0, diff_limit=4
    )
    now[0] = wiktionary_mcp._DIFF_REVIEW_VALIDITY_SECONDS + 1  # pylint: disable=protected-access

    with pytest.raises(ToolError, match="contiguously"):
        wiktionary_mcp.get_wiktionary_fix_proposal(
            "proposal-1",
            diff_offset=first["evidence_next_offset"],
            diff_limit=4,
            diff_review_token=first["diff_review_token"],
        )


def test_mcp_has_no_publication_queue_capability() -> None:
    assert not hasattr(wiktionary_mcp, "queue_reviewed_wiktionary_fix")

@pytest.mark.parametrize(
    ("offset", "limit", "message"),
    [(-1, 1, "offset"), (True, 1, "offset"), (0, 0, "limit"), (0, 6_001, "limit")],
)
def test_evidence_chunk_rejects_invalid_bounds(
    offset: int, limit: int, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        wiktionary_mcp._chunk_text("value", offset, limit)  # pylint: disable=protected-access

    with pytest.raises(ValueError, match="beyond"):
        wiktionary_mcp._chunk_text("value", 6, 1)  # pylint: disable=protected-access


def test_evidence_helpers_reject_invalid_sections_and_values() -> None:
    with pytest.raises(ValueError, match="section"):
        wiktionary_mcp._snapshot_chunk({}, "invalid", 0, 1)  # pylint: disable=protected-access
    with pytest.raises(ValueError, match="evidence is invalid"):
        wiktionary_mcp._snapshot_chunk(  # pylint: disable=protected-access
            {
                "language": "en",
                "title": "cat",
                "namespace": 0,
                "content": None,
                "content_sha256": "a" * 64,
                "parsed": False,
                "parse_error": None,
                "content_trust": "untrusted_wiktionary_content",
            },
            "content",
            0,
            1,
        )
    with pytest.raises(ValueError, match="proposal diff"):
        wiktionary_mcp._proposal_chunk({}, 0, 1)  # pylint: disable=protected-access


def test_lazy_service_uses_explicit_runtime_environment(
    monkeypatch: Any, tmp_path: Any
) -> None:
    sentinel = DummyReviewService()
    captured: Dict[str, Any] = {}

    def build_default_review_service(**kwargs: Any) -> DummyReviewService:
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(wiktionary_mcp, "_SERVICE", None)
    monkeypatch.setattr(
        wiktionary_mcp, "build_default_review_service", build_default_review_service
    )
    monkeypatch.setenv("BOTJAGWAR_PAGE_CHECK_REVIEW_QUEUE", "review-custom")
    monkeypatch.setenv(
        "BOTJAGWAR_WIKTIONARY_REVIEW_DB", str(tmp_path / "review.sqlite3")
    )
    monkeypatch.setenv("BOTJAGWAR_ENTRY_TRANSLATOR_URL", "http://translator:9000")
    monkeypatch.setenv("BOTJAGWAR_REVIEW_PUBLICATION_QUEUE", "reviewed-edits")

    assert wiktionary_mcp._get_service() is sentinel  # pylint: disable=protected-access
    assert captured["review_queue_name"] == "review-custom"
    assert captured["state_path"] == str(tmp_path / "review.sqlite3")
    assert captured["entry_translator_url"] == "http://translator:9000"
    assert captured["publication_queue_name"] == "translated"
    assert "reviewed_hmac_secret" not in captured
    assert "gateway_hmac_secret" not in captured
    assert len(captured["environment_fingerprint"]) == 64


def test_lazy_service_uses_xdg_state_default(monkeypatch: Any, tmp_path: Any) -> None:
    sentinel = DummyReviewService()
    captured: Dict[str, Any] = {}

    def build_default_review_service(**kwargs: Any) -> DummyReviewService:
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(wiktionary_mcp, "_SERVICE", None)
    monkeypatch.setattr(
        wiktionary_mcp, "build_default_review_service", build_default_review_service
    )
    monkeypatch.delenv("BOTJAGWAR_WIKTIONARY_REVIEW_DB", raising=False)
    monkeypatch.delenv("BOTJAGWAR_PAGE_CHECK_REVIEW_QUEUE", raising=False)
    monkeypatch.delenv("BOTJAGWAR_ENTRY_TRANSLATOR_URL", raising=False)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))

    assert wiktionary_mcp._get_service() is sentinel  # pylint: disable=protected-access
    environment_fingerprint = captured["environment_fingerprint"]
    assert len(environment_fingerprint) == 64
    assert captured["state_path"] == str(
        tmp_path
        / "botjagwar"
        / environment_fingerprint
        / "wiktionary-review.sqlite3"
    )
    assert captured["publication_queue_name"] == "translated"


def test_lazy_service_ignores_relative_xdg_state_location(
    monkeypatch: Any, tmp_path: Any
) -> None:
    sentinel = DummyReviewService()
    captured: Dict[str, Any] = {}

    def build_default_review_service(**kwargs: Any) -> DummyReviewService:
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(wiktionary_mcp, "_SERVICE", None)
    monkeypatch.setattr(
        wiktionary_mcp, "build_default_review_service", build_default_review_service
    )
    monkeypatch.setattr(wiktionary_mcp.Path, "home", lambda: tmp_path)
    monkeypatch.delenv("BOTJAGWAR_WIKTIONARY_REVIEW_DB", raising=False)
    monkeypatch.setenv("XDG_STATE_HOME", "relative-state")

    assert wiktionary_mcp._get_service() is sentinel  # pylint: disable=protected-access
    assert Path(captured["state_path"]).is_relative_to(
        tmp_path / ".local" / "state" / "botjagwar"
    )
    assert Path(captured["state_path"]).name == "wiktionary-review.sqlite3"


def test_lazy_service_falls_back_when_page_check_queue_is_unconfigured(
    monkeypatch: Any, tmp_path: Any
) -> None:
    captured: Dict[str, Any] = {}

    class MissingConfig:
        @staticmethod
        def get(_key: str, _section: str) -> str:
            raise KeyError("missing")

    monkeypatch.setattr(wiktionary_mcp, "_SERVICE", None)
    monkeypatch.setattr(wiktionary_mcp, "BotjagwarConfig", MissingConfig)
    monkeypatch.setattr(
        wiktionary_mcp,
        "build_default_review_service",
        lambda **kwargs: captured.update(kwargs) or DummyReviewService(),
    )
    monkeypatch.setenv(
        "BOTJAGWAR_WIKTIONARY_REVIEW_DB", str(tmp_path / "review.sqlite3")
    )

    wiktionary_mcp._get_service()  # pylint: disable=protected-access

    assert captured["publication_queue_name"] == "translated"


def test_lazy_service_rejects_relative_explicit_database(monkeypatch: Any) -> None:
    monkeypatch.setattr(wiktionary_mcp, "_SERVICE", None)
    monkeypatch.setenv("BOTJAGWAR_WIKTIONARY_REVIEW_DB", "relative.sqlite3")

    with pytest.raises(ValueError, match="absolute path"):
        wiktionary_mcp._get_service()  # pylint: disable=protected-access


def test_lazy_service_rejects_review_and_publication_queue_collision(
    monkeypatch: Any,
) -> None:
    values = {
        "page_check_review_queue": "shared-review-queue",
        "page_check_queue": "shared-review-queue",
        "queue": "edit",
    }

    def config_value(
        _settings: Any,
        key: str,
        _section: str,
        default: str,
    ) -> str:
        return values.get(key, default)

    monkeypatch.setattr(wiktionary_mcp, "_SERVICE", None)
    monkeypatch.setattr(wiktionary_mcp, "_config_value", config_value)
    monkeypatch.delenv("BOTJAGWAR_PAGE_CHECK_REVIEW_QUEUE", raising=False)

    with pytest.raises(ValueError, match="review queue must differ"):
        wiktionary_mcp._get_service()  # pylint: disable=protected-access


def test_lazy_service_requires_explicit_environment_identity(
    monkeypatch: Any, tmp_path: Any
) -> None:
    class MissingConfig:
        @staticmethod
        def get(_key: str, _section: str) -> str:
            raise KeyError("missing")

    monkeypatch.setattr(wiktionary_mcp, "_SERVICE", None)
    monkeypatch.setattr(wiktionary_mcp, "BotjagwarConfig", MissingConfig)
    monkeypatch.delenv("BOTJAGWAR_REVIEW_ENVIRONMENT_ID", raising=False)
    monkeypatch.setenv(
        "BOTJAGWAR_WIKTIONARY_REVIEW_DB", str(tmp_path / "review.sqlite3")
    )

    with pytest.raises(ReviewedWiktionaryFixError, match="environment ID"):
        wiktionary_mcp._get_service()  # pylint: disable=protected-access


def test_main_runs_stdio_server(monkeypatch: Any) -> None:
    calls: list[None] = []
    monkeypatch.setattr(wiktionary_mcp.mcp, "run", lambda: calls.append(None))

    wiktionary_mcp.main()

    assert calls == [None]
