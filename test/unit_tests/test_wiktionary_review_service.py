"""Tests for the guarded local Wiktionary review workflow."""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Dict

import pytest
import requests

from api.services.wiktionary_review_service import (
    DEFAULT_PAGE_CHECK_PUBLICATION_QUEUE,
    EntryTranslatorSnapshotClient,
    SqliteWiktionaryReviewStore,
    WiktionaryReviewError,
    WiktionaryReviewService,
    build_default_review_service,
)
import api.services.wiktionary_review_service as review_service_module
from api.services.page_check_review_queue import PageCheckReviewQueueError
from api.translation_v2.publishers import (
    WiktionaryRabbitMqPublisherError,
    WiktionaryRabbitMqPublisherRejectedError,
)

ENVIRONMENT_FINGERPRINT = "e" * 64


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _snapshot(language: str, title: str, content: str) -> Dict[str, Any]:
    return {
        "language": language,
        "title": title,
        "namespace": 0,
        "content": content,
        "content_sha256": _sha256(content),
        "entries": [{"language": language, "part_of_speech": "ana"}],
        "parsed": True,
        "parse_error": None,
        "content_trust": "untrusted_wiktionary_content",
    }


def _review_message() -> Dict[str, Any]:
    return {
        "kind": "page-check-review",
        "schema_version": 1,
        "event_id": "page-check:job-1",
        "job_id": "job-1",
        "queued_at": 123.0,
        "language": "mg",
        "title": "saka",
        "outcome": "unverifiable",
        "message": "No Malagasy definition",
        "source_language": "en",
        "source_title": "cat",
        "issues": [],
        "mg_entry": {"language": "mg", "word": "saka"},
    }


def _review_store(path: Path) -> SqliteWiktionaryReviewStore:
    """Build one test store bound to a stable fake deployment."""
    return SqliteWiktionaryReviewStore(
        path,
        environment_fingerprint=ENVIRONMENT_FINGERPRINT,
    )


class DummyResponse:
    def __init__(self, payload: Any, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> Any:
        return self._payload


class DummyReviewQueue:
    def __init__(self, message: Dict[str, Any] | None) -> None:
        self.message = message

    def transfer_next(
        self, accept: Callable[[Dict[str, Any]], Any]
    ) -> Any | None:
        if self.message is None:
            return None
        return accept(self.message)


class DummySnapshotClient:
    def __init__(self) -> None:
        self.snapshots = {
            ("mg", "saka"): _snapshot("mg", "saka", "==Malagasy==\nold\n"),
            ("en", "cat"): _snapshot("en", "cat", "==English==\ncat\n"),
        }
        self.calls: list[tuple[str, str]] = []

    def get_snapshot(self, language: str, title: str) -> Dict[str, Any]:
        self.calls.append((language, title))
        return dict(self.snapshots[(language, title)])


class DummyPublisher:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.published: list[Dict[str, Any]] = []

    def publish_wikipage(
        self,
        content: str,
        page_title: str,
        summary: str,
        minor: bool,
        expected_content_sha256: str,
    ) -> None:
        if self.error is not None:
            raise self.error
        self.published.append(
            {
                "content": content,
                "page_title": page_title,
                "summary": summary,
                "minor": minor,
                "expected_content_sha256": expected_content_sha256,
            }
        )


def _service(
    tmp_path: Path,
    *,
    snapshots: DummySnapshotClient | None = None,
    publisher: DummyPublisher | None = None,
) -> tuple[WiktionaryReviewService, DummySnapshotClient, DummyPublisher]:
    snapshot_client = snapshots or DummySnapshotClient()
    page_publisher = publisher or DummyPublisher()
    store = _review_store(tmp_path / "reviews.sqlite3")
    store.accept_task(_review_message())
    return (
        WiktionaryReviewService(
            DummyReviewQueue(None),  # type: ignore[arg-type]
            store,
            snapshot_client,
            page_publisher,
        ),
        snapshot_client,
        page_publisher,
    )


def _prepare(
    service: WiktionaryReviewService,
    snapshots: DummySnapshotClient,
) -> Dict[str, Any]:
    return service.prepare_fix(
        "page-check:job-1",
        snapshots.snapshots[("mg", "saka")]["content_sha256"],
        "cat",
        snapshots.snapshots[("en", "cat")]["content_sha256"],
        "==Malagasy==\nnew\n",
        "fanitsiana saka",
    )


def test_snapshot_client_reads_query_parameter_and_validates_content() -> None:
    page = _snapshot("en", "a/b", "exact\ncontent\n")
    calls: list[Dict[str, Any]] = []

    def request_get(url: str, **kwargs: Any) -> DummyResponse:
        calls.append({"url": url, **kwargs})
        return DummyResponse(page)

    client = EntryTranslatorSnapshotClient(
        "http://127.0.0.1:8000/root/", request_get=request_get
    )

    assert client.get_snapshot("en", "a/b") == page
    assert calls == [
        {
            "url": "http://127.0.0.1:8000/root/wiktionary-page-snapshots/en",
            "params": {"title": "a/b"},
            "timeout": (3.05, 30.0),
        }
    ]


@pytest.mark.parametrize(
    "base_url",
    [
        "file:///tmp/translator",
        "http://user:password@localhost:8000",
        "http://localhost:8000?secret=yes",
    ],
)
def test_snapshot_client_rejects_unsafe_base_urls(base_url: str) -> None:
    with pytest.raises(ValueError, match="URL is invalid"):
        EntryTranslatorSnapshotClient(base_url)


def test_snapshot_client_rejects_tampered_and_failed_responses() -> None:
    tampered = _snapshot("en", "cat", "content")
    tampered["content_sha256"] = "0" * 64
    client = EntryTranslatorSnapshotClient(
        request_get=lambda *_args, **_kwargs: DummyResponse(tampered)
    )
    with pytest.raises(WiktionaryReviewError, match="invalid snapshot"):
        client.get_snapshot("en", "cat")

    client = EntryTranslatorSnapshotClient(
        request_get=lambda *_args, **_kwargs: DummyResponse({}, 404)
    )
    with pytest.raises(WiktionaryReviewError, match="status 404"):
        client.get_snapshot("en", "missing")


def test_snapshot_client_wraps_transport_failure() -> None:
    def request_get(*_args: Any, **_kwargs: Any) -> DummyResponse:
        raise requests.ConnectionError("offline")

    client = EntryTranslatorSnapshotClient(request_get=request_get)
    with pytest.raises(WiktionaryReviewError, match="could not provide"):
        client.get_snapshot("en", "cat")


def test_snapshot_client_rejects_language_and_invalid_json() -> None:
    class InvalidJsonResponse(DummyResponse):
        def json(self) -> Any:
            raise ValueError("invalid JSON")

    client = EntryTranslatorSnapshotClient(
        request_get=lambda *_args, **_kwargs: InvalidJsonResponse(None)
    )

    with pytest.raises(WiktionaryReviewError, match="limited to English"):
        client.get_snapshot("fr", "chat")
    with pytest.raises(WiktionaryReviewError, match="invalid snapshot response"):
        client.get_snapshot("en", "cat")


@pytest.mark.parametrize(
    "payload,error",
    [
        ([], "invalid snapshot"),
        ({"language": "en"}, "incomplete snapshot"),
        (
            {
                **_snapshot("en", "cat", "content"),
                "namespace": True,
            },
            "invalid snapshot",
        ),
    ],
)
def test_snapshot_client_rejects_invalid_snapshot_contract(
    payload: Any, error: str
) -> None:
    client = EntryTranslatorSnapshotClient(
        request_get=lambda *_args, **_kwargs: DummyResponse(payload)
    )

    with pytest.raises(WiktionaryReviewError, match=error):
        client.get_snapshot("en", "cat")


def test_store_accepts_duplicate_event_idempotently(tmp_path: Path) -> None:
    store = _review_store(tmp_path / "review" / "state.sqlite3")

    first = store.accept_task(_review_message())
    duplicate = store.accept_task(_review_message())

    assert first["message"] == "No Malagasy definition"
    assert duplicate["message"] == "No Malagasy definition"
    assert duplicate["state"] == "pending"
    assert store.list_tasks() == [first]

    with pytest.raises(PageCheckReviewQueueError, match="conflicting"):
        store.accept_task({**_review_message(), "message": "changed duplicate"})


def test_store_migrates_queue_lease_column(tmp_path: Path) -> None:
    path = tmp_path / "reviews.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE fix_proposals (
                proposal_id TEXT PRIMARY KEY,
                event_id TEXT NOT NULL,
                target_title TEXT NOT NULL,
                target_content_sha256 TEXT NOT NULL,
                english_title TEXT NOT NULL,
                english_content_sha256 TEXT NOT NULL,
                replacement_content TEXT NOT NULL,
                replacement_content_sha256 TEXT NOT NULL,
                summary TEXT NOT NULL,
                diff TEXT NOT NULL,
                approval_digest TEXT NOT NULL,
                state TEXT NOT NULL,
                created_at REAL NOT NULL,
                queued_at REAL
            )
            """
        )

    _review_store(path)

    with sqlite3.connect(path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(fix_proposals)")
        }
    assert {
        "queue_started_at",
        "queue_claim_token",
        "diff_sha256",
        "publication_queue",
        "environment_fingerprint",
        "expires_at",
    }.issubset(columns)


def test_store_transactionally_migrates_version_one_metadata(tmp_path: Path) -> None:
    database = tmp_path / "reviews.sqlite3"
    service, snapshots, _publisher = _service(tmp_path)
    proposal = _prepare(service, snapshots)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE review_store_metadata SET schema_version = 1 WHERE singleton = 1"
        )

    migrated = _review_store(database)

    assert migrated.get_proposal(proposal["proposal_id"])["state"] == "superseded"
    task = migrated.get_task("page-check:job-1")
    assert task["state"] == "pending"
    assert task["proposal_id"] is None
    with sqlite3.connect(database) as connection:
        metadata = connection.execute(
            "SELECT schema_version FROM review_store_metadata WHERE singleton = 1"
        ).fetchone()
        user_version = connection.execute("PRAGMA user_version").fetchone()[0]
    assert metadata == (2,)
    assert user_version == 2


def test_store_rejects_database_from_another_environment(tmp_path: Path) -> None:
    database = tmp_path / "reviews.sqlite3"
    _review_store(database)

    with pytest.raises(WiktionaryReviewError, match="another environment"):
        SqliteWiktionaryReviewStore(
            database,
            environment_fingerprint="f" * 64,
        )


def test_store_reports_unknown_records_and_invalid_limit(tmp_path: Path) -> None:
    store = _review_store(tmp_path / "reviews.sqlite3")

    with pytest.raises(WiktionaryReviewError, match="Unknown page-check"):
        store.get_task("missing")
    with pytest.raises(WiktionaryReviewError, match="between 1 and 100"):
        store.list_tasks(0)
    with pytest.raises(WiktionaryReviewError, match="Unknown Wiktionary fix"):
        store.get_proposal("missing")
    with pytest.raises(WiktionaryReviewError, match="Unknown Wiktionary fix"):
        store.mark_queued("missing", "claim")
    with pytest.raises(WiktionaryReviewError, match="Unknown page-check"):
        store.save_proposal({"event_id": "missing"})


def test_claim_and_list_use_durable_store(tmp_path: Path) -> None:
    store = _review_store(tmp_path / "reviews.sqlite3")
    service = WiktionaryReviewService(
        DummyReviewQueue(_review_message()),  # type: ignore[arg-type]
        store,
        DummySnapshotClient(),
        DummyPublisher(),
    )

    result = service.claim_unchecked_entry()

    assert result["status"] == "claimed"
    assert result["task"]["event_id"] == "page-check:job-1"
    assert service.list_unchecked_entries() == {"tasks": [result["task"]]}


def test_claim_reports_empty_review_queue(tmp_path: Path) -> None:
    service = WiktionaryReviewService(
        DummyReviewQueue(None),  # type: ignore[arg-type]
        _review_store(tmp_path / "reviews.sqlite3"),
        DummySnapshotClient(),
        DummyPublisher(),
    )

    assert service.claim_unchecked_entry() == {"status": "empty", "task": None}


def test_prepare_fix_stores_hash_bound_diff(tmp_path: Path) -> None:
    service, snapshots, _publisher = _service(tmp_path)

    proposal = _prepare(service, snapshots)

    assert proposal["state"] == "prepared"
    assert proposal["target_title"] == "saka"
    assert proposal["replacement_content_sha256"] == _sha256(
        "==Malagasy==\nnew\n"
    )
    assert "-old" in proposal["diff"]
    assert "+new" in proposal["diff"]
    assert len(proposal["approval_digest"]) == 64
    assert proposal["diff_sha256"] == _sha256(proposal["diff"])
    assert proposal["publication_queue"] == DEFAULT_PAGE_CHECK_PUBLICATION_QUEUE
    assert proposal["environment_fingerprint"] == ENVIRONMENT_FINGERPRINT
    assert proposal["schema_version"] == 2
    assert proposal["publication_action"] == "edit_malagasy_wiktionary_page"
    assert service.get_unchecked_entry("page-check:job-1")["state"] == "proposed"
    assert service.get_fix_proposal(proposal["proposal_id"]) == proposal

    duplicate = _prepare(service, snapshots)
    assert duplicate == proposal


def test_prepare_fix_diff_marks_missing_final_newline(tmp_path: Path) -> None:
    service, snapshots, _publisher = _service(tmp_path)
    snapshots.snapshots[("mg", "saka")] = _snapshot("mg", "saka", "old")

    proposal = service.prepare_fix(
        "page-check:job-1",
        snapshots.snapshots[("mg", "saka")]["content_sha256"],
        "cat",
        snapshots.snapshots[("en", "cat")]["content_sha256"],
        "new",
    )

    assert proposal["diff"].count("\\ No newline at end of file") == 2


def test_prepare_fix_rejects_stale_target(tmp_path: Path) -> None:
    service, snapshots, _publisher = _service(tmp_path)

    with pytest.raises(WiktionaryReviewError, match="target changed"):
        service.prepare_fix(
            "page-check:job-1",
            "0" * 64,
            "cat",
            snapshots.snapshots[("en", "cat")]["content_sha256"],
            "replacement",
        )


def test_prepare_fix_rejects_stale_source_and_unchanged_content(tmp_path: Path) -> None:
    service, snapshots, _publisher = _service(tmp_path)

    with pytest.raises(WiktionaryReviewError, match="English source changed"):
        service.prepare_fix(
            "page-check:job-1",
            snapshots.snapshots[("mg", "saka")]["content_sha256"],
            "cat",
            "0" * 64,
            "replacement",
        )
    with pytest.raises(WiktionaryReviewError, match="does not change"):
        service.prepare_fix(
            "page-check:job-1",
            snapshots.snapshots[("mg", "saka")]["content_sha256"],
            "cat",
            snapshots.snapshots[("en", "cat")]["content_sha256"],
            snapshots.snapshots[("mg", "saka")]["content"],
        )


@pytest.mark.parametrize(
    "target_hash,english_title,english_hash,replacement,summary,error",
    [
        ("bad", "cat", "0" * 64, "replacement", "summary", "target_content"),
        ("0" * 64, "cat", "bad", "replacement", "summary", "english_content"),
        ("0" * 64, "", "0" * 64, "replacement", "summary", "title is required"),
        ("0" * 64, "cat", "0" * 64, "", "summary", "content is invalid"),
        ("0" * 64, "cat", "0" * 64, "replacement", "bad\nsummary", "summary is invalid"),
    ],
)
def test_prepare_fix_validates_proposal_inputs(
    tmp_path: Path,
    target_hash: str,
    english_title: str,
    english_hash: str,
    replacement: str,
    summary: str,
    error: str,
) -> None:
    service, _snapshots, _publisher = _service(tmp_path)

    with pytest.raises(WiktionaryReviewError, match=error):
        service.prepare_fix(
            "page-check:job-1",
            target_hash,
            english_title,
            english_hash,
            replacement,
            summary,
        )


def test_prepare_fix_rejects_oversized_replacement_and_diff(tmp_path: Path) -> None:
    service, snapshots, _publisher = _service(tmp_path)
    target_hash = snapshots.snapshots[("mg", "saka")]["content_sha256"]
    english_hash = snapshots.snapshots[("en", "cat")]["content_sha256"]

    with pytest.raises(WiktionaryReviewError, match="content is too large"):
        service.prepare_fix(
            "page-check:job-1",
            target_hash,
            "cat",
            english_hash,
            "x" * 1_000_001,
        )

    snapshots.snapshots[("mg", "saka")] = _snapshot(
        "mg", "saka", "old line\n" * 8_000
    )
    with pytest.raises(WiktionaryReviewError, match="diff is too large"):
        service.prepare_fix(
            "page-check:job-1",
            snapshots.snapshots[("mg", "saka")]["content_sha256"],
            "cat",
            english_hash,
            "new line\n" * 8_000,
        )


def test_prepare_fix_rejects_non_main_namespace(tmp_path: Path) -> None:
    service, snapshots, _publisher = _service(tmp_path)
    snapshots.snapshots[("mg", "saka")]["namespace"] = 2

    with pytest.raises(WiktionaryReviewError, match="main namespace"):
        _prepare(service, snapshots)


def test_new_proposal_supersedes_previous_one(tmp_path: Path) -> None:
    service, snapshots, _publisher = _service(tmp_path)
    first = _prepare(service, snapshots)

    second = service.prepare_fix(
        "page-check:job-1",
        snapshots.snapshots[("mg", "saka")]["content_sha256"],
        "cat",
        snapshots.snapshots[("en", "cat")]["content_sha256"],
        "==Malagasy==\nanother\n",
    )

    assert first["proposal_id"] != second["proposal_id"]
    assert service.get_fix_proposal(first["proposal_id"])["state"] == "superseded"
    assert second["state"] == "prepared"


def test_repreparing_superseded_content_creates_new_approval(tmp_path: Path) -> None:
    service, snapshots, _publisher = _service(tmp_path)
    first = _prepare(service, snapshots)
    second = service.prepare_fix(
        "page-check:job-1",
        snapshots.snapshots[("mg", "saka")]["content_sha256"],
        "cat",
        snapshots.snapshots[("en", "cat")]["content_sha256"],
        "==Malagasy==\nanother\n",
    )

    third = _prepare(service, snapshots)

    assert service.get_fix_proposal(first["proposal_id"])["state"] == "superseded"
    assert service.get_fix_proposal(second["proposal_id"])["state"] == "superseded"
    assert third["state"] == "prepared"
    assert third["proposal_id"] not in {
        first["proposal_id"],
        second["proposal_id"],
    }


def test_queue_reviewed_fix_publishes_expected_guarded_payload(tmp_path: Path) -> None:
    service, snapshots, publisher = _service(tmp_path)
    proposal = _prepare(service, snapshots)

    result = service.queue_reviewed_fix(
        proposal["proposal_id"], proposal["approval_digest"]
    )

    assert publisher.published == [
        {
            "content": "==Malagasy==\nnew\n",
            "page_title": "saka",
            "summary": "fanitsiana saka",
            "minor": False,
            "expected_content_sha256": snapshots.snapshots[("mg", "saka")][
                "content_sha256"
            ],
        }
    ]
    assert result["status"] == "queued_for_publication"
    assert result["published"] is False
    assert result["queue"] == DEFAULT_PAGE_CHECK_PUBLICATION_QUEUE
    assert service.get_unchecked_entry("page-check:job-1")["state"] == "queued"
    assert service.list_unchecked_entries() == {"tasks": []}


def test_queue_reviewed_fix_requires_exact_approval_digest(tmp_path: Path) -> None:
    service, snapshots, publisher = _service(tmp_path)
    proposal = _prepare(service, snapshots)

    with pytest.raises(WiktionaryReviewError, match="does not match"):
        service.queue_reviewed_fix(proposal["proposal_id"], "0" * 64)

    assert publisher.published == []


def test_expired_proposal_requires_fresh_review(
    monkeypatch: Any, tmp_path: Path
) -> None:
    service, snapshots, publisher = _service(tmp_path)
    proposal = _prepare(service, snapshots)
    monkeypatch.setattr(
        review_service_module.time,
        "time",
        lambda: proposal["expires_at"] + 1,
    )

    with pytest.raises(WiktionaryReviewError, match="expired"):
        service.queue_reviewed_fix(
            proposal["proposal_id"], proposal["approval_digest"]
        )

    assert publisher.published == []


def test_queue_reviewed_fix_rejects_different_publication_environment(
    tmp_path: Path,
) -> None:
    snapshots = DummySnapshotClient()
    store = _review_store(tmp_path / "reviews.sqlite3")
    store.accept_task(_review_message())
    first = WiktionaryReviewService(
        DummyReviewQueue(None),  # type: ignore[arg-type]
        store,
        snapshots,
        DummyPublisher(),
    )
    proposal = _prepare(first, snapshots)
    other = WiktionaryReviewService(
        DummyReviewQueue(None),  # type: ignore[arg-type]
        store,
        snapshots,
        DummyPublisher(),
        publication_queue_name="other-edits",
    )

    with pytest.raises(WiktionaryReviewError, match="different publication queue"):
        other.queue_reviewed_fix(
            proposal["proposal_id"], proposal["approval_digest"]
        )


def test_queued_task_cannot_be_prepared_or_queued_again(tmp_path: Path) -> None:
    service, snapshots, _publisher = _service(tmp_path)
    proposal = _prepare(service, snapshots)
    service.queue_reviewed_fix(proposal["proposal_id"], proposal["approval_digest"])

    with pytest.raises(WiktionaryReviewError, match="already queued"):
        _prepare(service, snapshots)
    with pytest.raises(WiktionaryReviewError, match="Only a prepared"):
        service.queue_reviewed_fix(
            proposal["proposal_id"], proposal["approval_digest"]
        )


def test_queue_reviewed_fix_revalidates_both_live_pages(tmp_path: Path) -> None:
    service, snapshots, publisher = _service(tmp_path)
    proposal = _prepare(service, snapshots)
    snapshots.snapshots[("en", "cat")] = _snapshot("en", "cat", "changed")

    with pytest.raises(WiktionaryReviewError, match="English source changed"):
        service.queue_reviewed_fix(
            proposal["proposal_id"], proposal["approval_digest"]
        )

    assert publisher.published == []


def test_queue_reviewed_fix_rejects_changed_target(tmp_path: Path) -> None:
    service, snapshots, publisher = _service(tmp_path)
    proposal = _prepare(service, snapshots)
    snapshots.snapshots[("mg", "saka")] = _snapshot("mg", "saka", "changed")

    with pytest.raises(WiktionaryReviewError, match="target changed after review"):
        service.queue_reviewed_fix(
            proposal["proposal_id"], proposal["approval_digest"]
        )

    assert publisher.published == []


def test_queue_reviewed_fix_rejects_tampered_local_content(tmp_path: Path) -> None:
    database = tmp_path / "reviews.sqlite3"
    service, snapshots, publisher = _service(tmp_path)
    proposal = _prepare(service, snapshots)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE fix_proposals SET replacement_content = 'tampered'"
        )

    with pytest.raises(WiktionaryReviewError, match="stored replacement"):
        service.queue_reviewed_fix(
            proposal["proposal_id"], proposal["approval_digest"]
        )

    assert publisher.published == []


def test_queue_reviewed_fix_recomputes_complete_approval_contract(
    tmp_path: Path,
) -> None:
    database = tmp_path / "reviews.sqlite3"
    service, snapshots, publisher = _service(tmp_path)
    proposal = _prepare(service, snapshots)
    tampered = "different reviewed bytes"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            UPDATE fix_proposals
            SET replacement_content = ?, replacement_content_sha256 = ?
            """,
            (tampered, _sha256(tampered)),
        )

    with pytest.raises(WiktionaryReviewError, match="approval contract"):
        service.queue_reviewed_fix(
            proposal["proposal_id"], proposal["approval_digest"]
        )

    assert publisher.published == []


def test_queue_reviewed_fix_recomputes_displayed_diff(tmp_path: Path) -> None:
    database = tmp_path / "reviews.sqlite3"
    service, snapshots, publisher = _service(tmp_path)
    proposal = _prepare(service, snapshots)
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE fix_proposals SET diff = 'misleading diff'")

    with pytest.raises(WiktionaryReviewError, match="diff hash is invalid"):
        service.queue_reviewed_fix(
            proposal["proposal_id"], proposal["approval_digest"]
        )

    assert publisher.published == []


def test_queue_reviewed_fix_rejects_concurrent_queue_attempt(tmp_path: Path) -> None:
    database = tmp_path / "reviews.sqlite3"
    service, snapshots, publisher = _service(tmp_path)
    proposal = _prepare(service, snapshots)
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            UPDATE fix_proposals
            SET state = 'queueing', queue_started_at = strftime('%s', 'now')
            """
        )
        connection.execute("UPDATE review_tasks SET state = 'queueing'")

    with pytest.raises(WiktionaryReviewError, match="already being queued"):
        service.queue_reviewed_fix(
            proposal["proposal_id"], proposal["approval_digest"]
        )

    assert publisher.published == []


def test_queue_reviewed_fix_marks_abandoned_attempt_unknown(tmp_path: Path) -> None:
    database = tmp_path / "reviews.sqlite3"
    service, snapshots, publisher = _service(tmp_path)
    proposal = _prepare(service, snapshots)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE fix_proposals SET state = 'queueing', queue_started_at = 0"
        )
        connection.execute("UPDATE review_tasks SET state = 'queueing'")

    with pytest.raises(WiktionaryReviewError, match="unknown outcome"):
        service.queue_reviewed_fix(
            proposal["proposal_id"], proposal["approval_digest"]
        )

    assert service.get_fix_proposal(proposal["proposal_id"])["state"] == "queue_unknown"
    assert publisher.published == []


def test_expired_queue_claim_becomes_unknown_without_new_owner(tmp_path: Path) -> None:
    database = tmp_path / "reviews.sqlite3"
    snapshots = DummySnapshotClient()
    store = _review_store(database)
    store.accept_task(_review_message())
    service = WiktionaryReviewService(
        DummyReviewQueue(None),  # type: ignore[arg-type]
        store,
        snapshots,
        DummyPublisher(),
    )
    proposal = _prepare(service, snapshots)
    first = store.claim_for_queue(proposal["proposal_id"])
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE fix_proposals SET queue_started_at = 0 WHERE proposal_id = ?",
            (proposal["proposal_id"],),
        )
    with pytest.raises(WiktionaryReviewError, match="unknown outcome"):
        store.claim_for_queue(proposal["proposal_id"])

    store.release_queue_claim(proposal["proposal_id"], first["queue_claim_token"])
    uncertain = store.get_proposal(proposal["proposal_id"])
    assert uncertain["state"] == "queue_unknown"
    assert uncertain["queue_claim_token"] is None
    with pytest.raises(WiktionaryReviewError, match="Unknown Wiktionary fix"):
        store.mark_queued(proposal["proposal_id"], first["queue_claim_token"])


def test_queue_failure_marks_proposal_outcome_unknown(tmp_path: Path) -> None:
    publisher = DummyPublisher(WiktionaryRabbitMqPublisherError("offline"))
    service, snapshots, _publisher = _service(tmp_path, publisher=publisher)
    proposal = _prepare(service, snapshots)

    with pytest.raises(WiktionaryReviewError, match="outcome is unknown"):
        service.queue_reviewed_fix(
            proposal["proposal_id"], proposal["approval_digest"]
        )

    assert service.get_fix_proposal(proposal["proposal_id"])["state"] == "queue_unknown"


def test_definite_broker_rejection_releases_proposal_for_retry(tmp_path: Path) -> None:
    publisher = DummyPublisher(
        WiktionaryRabbitMqPublisherRejectedError("invalid request")
    )
    service, snapshots, _publisher = _service(tmp_path, publisher=publisher)
    proposal = _prepare(service, snapshots)

    with pytest.raises(WiktionaryReviewError, match="rejected before RabbitMQ"):
        service.queue_reviewed_fix(
            proposal["proposal_id"], proposal["approval_digest"]
        )

    assert service.get_fix_proposal(proposal["proposal_id"])["state"] == "prepared"

def test_confirmed_queue_mark_failure_records_unknown(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    service, snapshots, publisher = _service(tmp_path)
    proposal = _prepare(service, snapshots)
    store = service._store  # pylint: disable=protected-access
    monkeypatch.setattr(
        store,
        "mark_queued",
        lambda *_args: (_ for _ in ()).throw(sqlite3.OperationalError("locked")),
    )

    with pytest.raises(WiktionaryReviewError, match="requires reconciliation"):
        service.queue_reviewed_fix(
            proposal["proposal_id"], proposal["approval_digest"]
        )

    assert len(publisher.published) == 1
    assert service.get_fix_proposal(proposal["proposal_id"])["state"] == "queue_unknown"
    assert service.get_fix_proposal(proposal["proposal_id"])[
        "publication_status"
    ] == "queue_outcome_unknown"
    assert service.get_unchecked_entry("page-check:job-1")["state"] == "queue_unknown"


def test_confirmed_queue_state_failure_forbids_retry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    service, snapshots, publisher = _service(tmp_path)
    proposal = _prepare(service, snapshots)
    store = service._store  # pylint: disable=protected-access
    monkeypatch.setattr(
        store,
        "mark_queued",
        lambda *_args: (_ for _ in ()).throw(sqlite3.OperationalError("locked")),
    )
    monkeypatch.setattr(
        store,
        "mark_queue_unknown",
        lambda *_args: (_ for _ in ()).throw(sqlite3.OperationalError("locked")),
    )

    with pytest.raises(WiktionaryReviewError, match="could not be persisted"):
        service.queue_reviewed_fix(
            proposal["proposal_id"], proposal["approval_digest"]
        )
    with pytest.raises(WiktionaryReviewError, match="already being queued"):
        service.queue_reviewed_fix(
            proposal["proposal_id"], proposal["approval_digest"]
        )

    assert len(publisher.published) == 1
    assert service.get_fix_proposal(proposal["proposal_id"])["state"] == "queueing"


def test_review_service_rejects_non_malagasy_task(tmp_path: Path) -> None:
    store = _review_store(tmp_path / "reviews.sqlite3")
    store.accept_task({**_review_message(), "language": "en"})
    service = WiktionaryReviewService(
        DummyReviewQueue(None),  # type: ignore[arg-type]
        store,
        DummySnapshotClient(),
        DummyPublisher(),
    )

    with pytest.raises(WiktionaryReviewError, match="Only Malagasy"):
        service.get_malagasy_snapshot("page-check:job-1")
    with pytest.raises(WiktionaryReviewError, match="Only Malagasy"):
        service.prepare_fix(
            "page-check:job-1", "0" * 64, "cat", "0" * 64, "replacement"
        )


def test_snapshot_accessors_delegate_to_expected_language(tmp_path: Path) -> None:
    service, snapshots, _publisher = _service(tmp_path)

    assert service.get_english_snapshot("cat")["language"] == "en"
    assert service.get_malagasy_snapshot("page-check:job-1")["language"] == "mg"
    assert snapshots.calls == [("en", "cat"), ("mg", "saka")]


def test_build_default_review_service_wires_runtime_boundaries(
    monkeypatch: Any, tmp_path: Path
) -> None:
    created: Dict[str, Any] = {}

    def queue_factory(name: str) -> SimpleNamespace:
        created["queue"] = name
        return SimpleNamespace(queue_name=name)

    def store_factory(
        path: Path, *, environment_fingerprint: str
    ) -> SimpleNamespace:
        created["store"] = (path, environment_fingerprint)
        return SimpleNamespace(environment_fingerprint=environment_fingerprint)

    def publisher_factory(name: str) -> SimpleNamespace:
        created["publisher"] = name
        return SimpleNamespace()

    monkeypatch.setattr(
        review_service_module,
        "RabbitMqPageCheckReviewQueue",
        queue_factory,
    )
    monkeypatch.setattr(
        review_service_module,
        "SqliteWiktionaryReviewStore",
        store_factory,
    )
    monkeypatch.setattr(
        review_service_module,
        "EntryTranslatorSnapshotClient",
        lambda url: created.setdefault("snapshot", url),
    )
    monkeypatch.setattr(
        review_service_module,
        "WiktionaryRabbitMqPublisher",
        publisher_factory,
    )

    service = build_default_review_service(
        review_queue_name="reviews",
        state_path=tmp_path / "state.sqlite3",
        entry_translator_url="http://translator:8000",
        environment_fingerprint=ENVIRONMENT_FINGERPRINT,
    )

    assert isinstance(service, WiktionaryReviewService)
    assert created == {
        "queue": "reviews",
        "store": (tmp_path / "state.sqlite3", ENVIRONMENT_FINGERPRINT),
        "snapshot": "http://translator:8000",
        "publisher": DEFAULT_PAGE_CHECK_PUBLICATION_QUEUE,
    }
