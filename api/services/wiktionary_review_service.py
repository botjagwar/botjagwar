"""Safe local workflow for reviewing and queueing Wiktionary page fixes."""

from __future__ import annotations

import difflib
import hashlib
import json
import math
import re
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Protocol
from urllib.parse import urlsplit, urlunsplit

import requests

from api.http_client import DEFAULT_HTTP_TIMEOUT
from api.services.page_check_review_queue import (
    PageCheckReviewQueueError,
    RabbitMqPageCheckReviewQueue,
    validate_review_queue_separation,
    validate_page_check_review_message,
)
from api.services.reviewed_wiktionary_fix import (
    REVIEWED_FIX_SCHEMA_VERSION,
    REVIEWED_FIX_VALIDITY_SECONDS,
    approval_digest as reviewed_fix_approval_digest,
)
from api.translation_v2.publishers import (
    WiktionaryRabbitMqPublisher,
    WiktionaryRabbitMqPublisherError,
    WiktionaryRabbitMqPublisherRejectedError,
)


_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_MAX_TITLE_LENGTH = 512
_MAX_REPLACEMENT_BYTES = 1_000_000
_MAX_DIFF_CHARACTERS = 50_000
_MAX_SUMMARY_LENGTH = 500
_QUEUE_ATTEMPT_LEASE_SECONDS = 240.0
_QUEUE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,255}$")
_REVIEW_STORE_SCHEMA_VERSION = 2
DEFAULT_PAGE_CHECK_PUBLICATION_QUEUE = "translated"


class WiktionaryReviewError(RuntimeError):
    """Raised when a review operation violates the guarded workflow."""


class SnapshotClient(Protocol):
    """Boundary for live page snapshots retrieved from entry translator."""

    def get_snapshot(self, language: str, title: str) -> Dict[str, Any]:
        """Return one live Wiktionary snapshot."""


class ReviewedPagePublisher(Protocol):
    """Boundary for queueing one complete guarded Malagasy page edit."""

    def publish_wikipage(
        self,
        content: str,
        page_title: str,
        summary: str,
        minor: bool,
        expected_content_sha256: str,
    ) -> None:
        """Queue a full-page edit guarded by its current content hash."""


class EntryTranslatorSnapshotClient:
    """Read live Wiktionary snapshots only through entry translator v2."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        *,
        request_get: Any = requests.get,
        timeout: float | tuple[float, float] = DEFAULT_HTTP_TIMEOUT,
    ) -> None:
        """Initialize the client with an injectable offline HTTP boundary."""
        parsed = urlsplit(base_url.strip())
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("The entry-translator URL is invalid.")
        self._base_url = urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "")
        )
        self._request_get = request_get
        self._timeout = timeout

    def get_snapshot(self, language: str, title: str) -> Dict[str, Any]:
        """Return and independently validate one entry-translator snapshot."""
        if language not in {"en", "mg"}:
            raise WiktionaryReviewError(
                "Review snapshots are limited to English and Malagasy Wiktionary."
            )
        title = _validate_title(title)
        try:
            response = self._request_get(
                f"{self._base_url}/wiktionary-page-snapshots/{language}",
                params={"title": title},
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            raise WiktionaryReviewError(
                "Entry translator could not provide the Wiktionary snapshot."
            ) from exc
        if response.status_code != 200:
            raise WiktionaryReviewError(
                f"Entry translator rejected the snapshot request with status "
                f"{response.status_code}."
            )
        try:
            snapshot = response.json()
        except (TypeError, ValueError) as exc:
            raise WiktionaryReviewError(
                "Entry translator returned an invalid snapshot response."
            ) from exc
        return _validate_snapshot(snapshot, language, title)


class SqliteWiktionaryReviewStore:
    """Durably store claimed reviews and immutable fix proposals in SQLite."""

    def __init__(
        self,
        path: str | Path,
        *,
        environment_fingerprint: str,
    ) -> None:
        """Initialize the local database and its constrained schema."""
        _validate_sha256(environment_fingerprint, "environment_fingerprint")
        self._path = Path(path)
        self._environment_fingerprint = environment_fingerprint
        self._path.parent.mkdir(parents=True, exist_ok=True)
        connection = self._connect()
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("BEGIN IMMEDIATE")
            existing_tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS review_tasks (
                    event_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    state TEXT NOT NULL,
                    proposal_id TEXT,
                    received_at REAL NOT NULL,
                    completed_at REAL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS fix_proposals (
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
                    diff_sha256 TEXT NOT NULL,
                    publication_queue TEXT NOT NULL,
                    approval_digest TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    queue_started_at REAL,
                    queue_claim_token TEXT,
                    queued_at REAL,
                    environment_fingerprint TEXT NOT NULL,
                    expires_at REAL NOT NULL,
                    FOREIGN KEY(event_id) REFERENCES review_tasks(event_id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS review_store_metadata (
                    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                    schema_version INTEGER NOT NULL,
                    environment_fingerprint TEXT NOT NULL
                )
                """
            )
            metadata = connection.execute(
                "SELECT * FROM review_store_metadata WHERE singleton = 1"
            ).fetchone()
            if metadata is not None:
                if metadata["schema_version"] not in {
                    1,
                    _REVIEW_STORE_SCHEMA_VERSION,
                }:
                    raise WiktionaryReviewError(
                        "The Wiktionary review database schema is unsupported."
                    )
                if metadata["environment_fingerprint"] != environment_fingerprint:
                    raise WiktionaryReviewError(
                        "The Wiktionary review database belongs to another environment."
                    )
            proposal_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(fix_proposals)")
            }
            for column, definition in (
                ("queue_started_at", "REAL"),
                ("queue_claim_token", "TEXT"),
                ("diff_sha256", "TEXT"),
                ("publication_queue", "TEXT"),
                ("environment_fingerprint", "TEXT"),
                ("expires_at", "REAL"),
            ):
                if column not in proposal_columns:
                    connection.execute(
                        f"ALTER TABLE fix_proposals ADD COLUMN {column} {definition}"
                    )
            requires_v2_migration = (
                metadata is None or metadata["schema_version"] == 1
            )
            if requires_v2_migration:
                if "fix_proposals" in existing_tables:
                    connection.execute(
                        """
                        UPDATE fix_proposals SET state = 'superseded',
                            queue_started_at = NULL, queue_claim_token = NULL
                        WHERE state IN ('prepared', 'superseded')
                        """
                    )
                    connection.execute(
                        """
                        UPDATE fix_proposals SET state = 'queue_unknown',
                            queue_claim_token = NULL
                        WHERE state = 'queueing'
                        """
                    )
                if "review_tasks" in existing_tables:
                    connection.execute(
                        """
                        UPDATE review_tasks SET state = 'pending', proposal_id = NULL,
                            completed_at = NULL
                        WHERE state = 'proposed'
                        """
                    )
                    connection.execute(
                        """
                        UPDATE review_tasks SET state = 'queue_unknown'
                        WHERE state = 'queueing'
                        """
                    )
                if metadata is None:
                    connection.execute(
                        """
                        INSERT INTO review_store_metadata (
                            singleton, schema_version, environment_fingerprint
                        ) VALUES (1, ?, ?)
                        """,
                        (_REVIEW_STORE_SCHEMA_VERSION, environment_fingerprint),
                    )
                else:
                    connection.execute(
                        """
                        UPDATE review_store_metadata SET schema_version = ?
                        WHERE singleton = 1 AND schema_version = 1
                        """,
                        (_REVIEW_STORE_SCHEMA_VERSION,),
                    )
            connection.execute(f"PRAGMA user_version={_REVIEW_STORE_SCHEMA_VERSION}")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @property
    def environment_fingerprint(self) -> str:
        """Return the deployment identity bound to this state database."""
        return self._environment_fingerprint

    def accept_task(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Persist one RabbitMQ review before its delivery is acknowledged."""
        message = validate_page_check_review_message(message)
        event_id = message["event_id"]
        payload = json.dumps(
            message,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO review_tasks
                    (event_id, payload, state, proposal_id, received_at, completed_at)
                VALUES (?, ?, 'pending', NULL, ?, NULL)
                """,
                (event_id, payload, time.time()),
            )
            row = connection.execute(
                "SELECT * FROM review_tasks WHERE event_id = ?",
                (event_id,),
            ).fetchone()
        if row is None:
            raise WiktionaryReviewError("The claimed review task could not be stored.")
        if row["payload"] != payload:
            raise PageCheckReviewQueueError(
                "A conflicting page-check review message reused an existing event ID."
            )
        return self._task_from_row(row)

    def get_task(self, event_id: str) -> Dict[str, Any]:
        """Return one claimed review task."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM review_tasks WHERE event_id = ?",
                (event_id,),
            ).fetchone()
        if row is None:
            raise WiktionaryReviewError("Unknown page-check review event.")
        return self._task_from_row(row)

    def list_tasks(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return pending and proposed tasks, oldest first."""
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise WiktionaryReviewError("Review task limit must be between 1 and 100.")
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM review_tasks
                WHERE state IN ('pending', 'proposed', 'queueing', 'queue_unknown')
                ORDER BY received_at ASC, event_id ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._task_from_row(row) for row in rows]

    def save_proposal(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """Store a proposal and supersede any earlier unqueued proposal for its task."""
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            task = connection.execute(
                "SELECT state, proposal_id FROM review_tasks WHERE event_id = ?",
                (proposal["event_id"],),
            ).fetchone()
            if task is None:
                raise WiktionaryReviewError("Unknown page-check review event.")
            if task["state"] in {"queueing", "queued"}:
                raise WiktionaryReviewError(
                    "This review task is already being queued or was queued."
                )
            existing = connection.execute(
                "SELECT * FROM fix_proposals WHERE proposal_id = ?",
                (proposal["proposal_id"],),
            ).fetchone()
            if existing is not None:
                immutable_fields = (
                    "event_id",
                    "target_title",
                    "target_content_sha256",
                    "english_title",
                    "english_content_sha256",
                    "replacement_content",
                    "replacement_content_sha256",
                    "summary",
                    "diff",
                    "diff_sha256",
                    "publication_queue",
                    "approval_digest",
                    "environment_fingerprint",
                    "expires_at",
                )
                if any(existing[field] != proposal[field] for field in immutable_fields):
                    raise WiktionaryReviewError(
                        "A conflicting Wiktionary fix reused an existing proposal ID."
                    )
            connection.execute(
                """
                UPDATE fix_proposals SET state = 'superseded'
                WHERE event_id = ? AND proposal_id != ? AND state = 'prepared'
                """,
                (proposal["event_id"], proposal["proposal_id"]),
            )
            if existing is None:
                connection.execute(
                    """
                    INSERT INTO fix_proposals (
                        proposal_id, event_id, target_title,
                        target_content_sha256, english_title,
                        english_content_sha256, replacement_content,
                        replacement_content_sha256, summary, diff, diff_sha256,
                        publication_queue, approval_digest, state, created_at, queue_started_at,
                        queue_claim_token, queued_at, environment_fingerprint, expires_at
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        'prepared', ?, NULL, NULL, NULL, ?, ?
                    )
                    """,
                    (
                        proposal["proposal_id"],
                        proposal["event_id"],
                        proposal["target_title"],
                        proposal["target_content_sha256"],
                        proposal["english_title"],
                        proposal["english_content_sha256"],
                        proposal["replacement_content"],
                        proposal["replacement_content_sha256"],
                        proposal["summary"],
                        proposal["diff"],
                        proposal["diff_sha256"],
                        proposal["publication_queue"],
                        proposal["approval_digest"],
                        proposal["created_at"],
                        proposal["environment_fingerprint"],
                        proposal["expires_at"],
                    ),
                )
            elif existing["state"] != "prepared":
                raise WiktionaryReviewError(
                    "This Wiktionary fix proposal cannot be prepared again."
                )
            updated = connection.execute(
                """
                UPDATE review_tasks
                SET state = 'proposed', proposal_id = ?
                WHERE event_id = ? AND state IN ('pending', 'proposed')
                """,
                (proposal["proposal_id"], proposal["event_id"]),
            )
            if updated.rowcount != 1:
                raise WiktionaryReviewError(
                    "The review task changed while its proposal was being stored."
                )
            row = connection.execute(
                "SELECT * FROM fix_proposals WHERE proposal_id = ?",
                (proposal["proposal_id"],),
            ).fetchone()
        if row is None:
            raise WiktionaryReviewError("The fix proposal could not be stored.")
        return self._proposal_from_row(row)

    def get_proposal(self, proposal_id: str) -> Dict[str, Any]:
        """Return one immutable fix proposal."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM fix_proposals WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
        if row is None:
            raise WiktionaryReviewError("Unknown Wiktionary fix proposal.")
        return self._proposal_from_row(row)

    def claim_for_queue(
        self,
        proposal_id: str,
        *,
        lease_seconds: float = _QUEUE_ATTEMPT_LEASE_SECONDS,
    ) -> Dict[str, Any]:
        """Atomically claim one prepared queue attempt."""
        now = time.time()
        claim_token = uuid.uuid4().hex
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            proposal = connection.execute(
                "SELECT * FROM fix_proposals WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
            if proposal is None:
                raise WiktionaryReviewError("Unknown Wiktionary fix proposal.")
            if proposal["state"] == "queued":
                raise WiktionaryReviewError("This Wiktionary fix was already queued.")
            if proposal["state"] == "superseded":
                raise WiktionaryReviewError("This Wiktionary fix proposal was superseded.")
            if proposal["state"] == "queue_unknown":
                raise WiktionaryReviewError(
                    "This Wiktionary fix has an unknown queue outcome."
                )
            task = connection.execute(
                "SELECT state, proposal_id FROM review_tasks WHERE event_id = ?",
                (proposal["event_id"],),
            ).fetchone()
            expected_task_state = (
                "queueing" if proposal["state"] == "queueing" else "proposed"
            )
            if (
                task is None
                or task["proposal_id"] != proposal_id
                or task["state"] != expected_task_state
            ):
                raise WiktionaryReviewError(
                    "This proposal is no longer current for its review task."
                )
            if (
                proposal["state"] == "queueing"
                and isinstance(proposal["queue_started_at"], (int, float))
                and now - proposal["queue_started_at"] < lease_seconds
            ):
                raise WiktionaryReviewError(
                    "This Wiktionary fix is already being queued."
                )
            if proposal["state"] == "queueing":
                connection.execute(
                    """
                    UPDATE fix_proposals
                    SET state = 'queue_unknown', queue_claim_token = NULL
                    WHERE proposal_id = ? AND state = 'queueing'
                    """,
                    (proposal_id,),
                )
                connection.execute(
                    """
                    UPDATE review_tasks SET state = 'queue_unknown'
                    WHERE event_id = ? AND proposal_id = ? AND state = 'queueing'
                    """,
                    (proposal["event_id"], proposal_id),
                )
                connection.commit()
                raise WiktionaryReviewError(
                    "The previous queue attempt has an unknown outcome and requires reconciliation."
                )
            if proposal["state"] != "prepared":
                raise WiktionaryReviewError("This Wiktionary fix cannot be queued.")
            updated = connection.execute(
                """
                UPDATE fix_proposals
                SET state = 'queueing', queue_started_at = ?, queue_claim_token = ?
                WHERE proposal_id = ? AND state = 'prepared'
                """,
                (now, claim_token, proposal_id),
            )
            if updated.rowcount != 1:
                raise WiktionaryReviewError(
                    "The Wiktionary fix changed while it was being claimed."
                )
            task_updated = connection.execute(
                """
                UPDATE review_tasks SET state = 'queueing'
                WHERE event_id = ? AND proposal_id = ? AND state = 'proposed'
                """,
                (proposal["event_id"], proposal_id),
            )
            if task_updated.rowcount != 1:
                raise WiktionaryReviewError(
                    "The review task changed while its proposal was being claimed."
                )
            row = connection.execute(
                "SELECT * FROM fix_proposals WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
        if row is None:  # pragma: no cover - guarded by the transaction above
            raise WiktionaryReviewError("The queue attempt could not be stored.")
        return self._proposal_from_row(row)

    def release_queue_claim(self, proposal_id: str, claim_token: str) -> None:
        """Return a failed queue attempt to the prepared state."""
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            proposal = connection.execute(
                """
                SELECT event_id, state FROM fix_proposals
                WHERE proposal_id = ? AND queue_claim_token = ?
                """,
                (proposal_id, claim_token),
            ).fetchone()
            if proposal is None or proposal["state"] != "queueing":
                return
            updated = connection.execute(
                """
                UPDATE fix_proposals
                SET state = 'prepared', queue_started_at = NULL,
                    queue_claim_token = NULL
                WHERE proposal_id = ? AND queue_claim_token = ? AND state = 'queueing'
                """,
                (proposal_id, claim_token),
            )
            if updated.rowcount != 1:
                return
            task_updated = connection.execute(
                """
                UPDATE review_tasks SET state = 'proposed'
                WHERE event_id = ? AND proposal_id = ? AND state = 'queueing'
                """,
                (proposal["event_id"], proposal_id),
            )
            if task_updated.rowcount != 1:
                raise WiktionaryReviewError(
                    "The review task changed while its queue claim was released."
                )

    def mark_queued(self, proposal_id: str, claim_token: str) -> Dict[str, Any]:
        """Atomically mark a proposal and its review task as queued."""
        queued_at = time.time()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            proposal = connection.execute(
                """
                SELECT * FROM fix_proposals
                WHERE proposal_id = ? AND queue_claim_token = ?
                """,
                (proposal_id, claim_token),
            ).fetchone()
            if proposal is None:
                raise WiktionaryReviewError("Unknown Wiktionary fix proposal.")
            if proposal["state"] != "queueing":
                raise WiktionaryReviewError(
                    "Only a claimed Wiktionary fix proposal can be marked queued."
                )
            updated = connection.execute(
                """
                UPDATE fix_proposals
                SET state = 'queued', queued_at = ?, queue_claim_token = NULL
                WHERE proposal_id = ? AND queue_claim_token = ? AND state = 'queueing'
                """,
                (queued_at, proposal_id, claim_token),
            )
            if updated.rowcount != 1:
                raise WiktionaryReviewError(
                    "The queue claim changed before it could be completed."
                )
            task_updated = connection.execute(
                """
                UPDATE review_tasks
                SET state = 'queued', completed_at = ?
                WHERE event_id = ? AND proposal_id = ? AND state = 'queueing'
                """,
                (queued_at, proposal["event_id"], proposal_id),
            )
            if task_updated.rowcount != 1:
                raise WiktionaryReviewError(
                    "The review task changed before queue completion."
                )
            row = connection.execute(
                "SELECT * FROM fix_proposals WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
        if row is None:  # pragma: no cover - guarded by the transaction above
            raise WiktionaryReviewError("The queued proposal state could not be stored.")
        return self._proposal_from_row(row)

    def mark_queue_unknown(self, proposal_id: str, claim_token: str) -> None:
        """Record that a started publication attempt has an uncertain outcome."""
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            proposal = connection.execute(
                """
                SELECT event_id FROM fix_proposals
                WHERE proposal_id = ? AND queue_claim_token = ? AND state = 'queueing'
                """,
                (proposal_id, claim_token),
            ).fetchone()
            if proposal is None:
                return
            updated = connection.execute(
                """
                UPDATE fix_proposals
                SET state = 'queue_unknown', queue_claim_token = NULL
                WHERE proposal_id = ? AND queue_claim_token = ? AND state = 'queueing'
                """,
                (proposal_id, claim_token),
            )
            if updated.rowcount != 1:
                return
            task_updated = connection.execute(
                """
                UPDATE review_tasks SET state = 'queue_unknown'
                WHERE event_id = ? AND proposal_id = ? AND state = 'queueing'
                """,
                (proposal["event_id"], proposal_id),
            )
            if task_updated.rowcount != 1:
                raise WiktionaryReviewError(
                    "The review task changed while queue uncertainty was recorded."
                )

    def _connect(self) -> sqlite3.Connection:
        """Open one short-lived, thread-safe SQLite connection."""
        connection = sqlite3.connect(self._path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @staticmethod
    def _task_from_row(row: sqlite3.Row) -> Dict[str, Any]:
        """Serialize one SQLite task row."""
        payload = json.loads(row["payload"])
        return {
            **payload,
            "state": row["state"],
            "proposal_id": row["proposal_id"],
            "received_at": row["received_at"],
            "completed_at": row["completed_at"],
            "content_trust": "untrusted_page_check_evidence",
        }

    @staticmethod
    def _proposal_from_row(row: sqlite3.Row) -> Dict[str, Any]:
        """Serialize one SQLite proposal row."""
        proposal = {key: row[key] for key in row.keys()}
        proposal["prepared_at"] = row["created_at"]
        return proposal


class WiktionaryReviewService:
    """Coordinate review claims, snapshots, proposals, and guarded queueing."""

    def __init__(
        self,
        review_queue: RabbitMqPageCheckReviewQueue,
        store: SqliteWiktionaryReviewStore,
        snapshot_client: SnapshotClient,
        publisher: ReviewedPagePublisher,
        publication_queue_name: str = DEFAULT_PAGE_CHECK_PUBLICATION_QUEUE,
        environment_fingerprint: str | None = None,
    ) -> None:
        """Initialize the workflow with injectable I/O boundaries."""
        if not _QUEUE_NAME_PATTERN.fullmatch(publication_queue_name):
            raise ValueError("The reviewed-edit publication queue name is invalid.")
        review_queue_name = getattr(review_queue, "queue_name", None)
        if isinstance(review_queue_name, str):
            validate_review_queue_separation(
                review_queue_name, {publication_queue_name}
            )
        resolved_fingerprint = (
            store.environment_fingerprint
            if environment_fingerprint is None
            else environment_fingerprint
        )
        _validate_sha256(resolved_fingerprint, "environment_fingerprint")
        if resolved_fingerprint != store.environment_fingerprint:
            raise ValueError("The review service environment does not match its store.")
        self._review_queue = review_queue
        self._store = store
        self._snapshot_client = snapshot_client
        self._publisher = publisher
        self._publication_queue_name = publication_queue_name
        self._environment_fingerprint = resolved_fingerprint

    def claim_unchecked_entry(self) -> Dict[str, Any]:
        """Durably claim one page-check review event from RabbitMQ."""
        task = self._review_queue.transfer_next(self._store.accept_task)
        if task is None:
            return {"status": "empty", "task": None}
        return {"status": "claimed", "task": task}

    def list_unchecked_entries(self, limit: int = 20) -> Dict[str, Any]:
        """List locally claimed review work that has not been queued yet."""
        return {"tasks": self._store.list_tasks(limit)}

    def get_unchecked_entry(self, event_id: str) -> Dict[str, Any]:
        """Return one locally claimed page-check review event."""
        return self._store.get_task(event_id)

    def get_english_snapshot(self, title: str) -> Dict[str, Any]:
        """Return live English Wiktionary content as untrusted reference data."""
        return self._snapshot_client.get_snapshot("en", title)

    def get_malagasy_snapshot(self, event_id: str) -> Dict[str, Any]:
        """Return the live Malagasy target for one claimed review event."""
        task = self._store.get_task(event_id)
        if task["language"] != "mg":
            raise WiktionaryReviewError(
                "Only Malagasy Wiktionary review targets can be published."
            )
        return self._snapshot_client.get_snapshot("mg", task["title"])

    def prepare_fix(
        self,
        event_id: str,
        target_content_sha256: str,
        english_title: str,
        english_content_sha256: str,
        replacement_content: str,
        summary: str = "fanitsiana famaritana",
    ) -> Dict[str, Any]:
        """Prepare an immutable, non-publishing fix proposal from live snapshots."""
        task = self._store.get_task(event_id)
        if task["state"] == "queued":
            raise WiktionaryReviewError("This review task was already queued.")
        if task["language"] != "mg":
            raise WiktionaryReviewError(
                "Only Malagasy Wiktionary review targets can be published."
            )
        _validate_sha256(target_content_sha256, "target_content_sha256")
        _validate_sha256(english_content_sha256, "english_content_sha256")
        english_title = _validate_title(english_title)
        replacement_content = _validate_replacement(replacement_content)
        summary = _validate_summary(summary)

        target = self._snapshot_client.get_snapshot("mg", task["title"])
        english = self._snapshot_client.get_snapshot("en", english_title)
        _require_main_namespace(target, "Malagasy target")
        _require_main_namespace(english, "English source")
        if target["content_sha256"] != target_content_sha256:
            raise WiktionaryReviewError(
                "The Malagasy target changed; fetch a new snapshot before proposing a fix."
            )
        if english["content_sha256"] != english_content_sha256:
            raise WiktionaryReviewError(
                "The English source changed; fetch a new snapshot before proposing a fix."
            )
        if target["content"] == replacement_content:
            raise WiktionaryReviewError("The proposed replacement does not change the page.")

        diff = _build_review_diff(
            task["title"],
            target["content"],
            replacement_content,
        )
        replacement_hash = _sha256(replacement_content)
        diff_hash = _sha256(diff)
        proposal_fields = {
            "event_id": event_id,
            "target_title": task["title"],
            "target_content_sha256": target_content_sha256,
            "english_title": english_title,
            "english_content_sha256": english_content_sha256,
            "replacement_content": replacement_content,
            "replacement_content_sha256": replacement_hash,
            "diff": diff,
            "diff_sha256": diff_hash,
            "summary": summary,
            "publication_queue": self._publication_queue_name,
            "environment_fingerprint": self._environment_fingerprint,
        }
        current_proposal_id = task.get("proposal_id")
        if isinstance(current_proposal_id, str):
            current = self._store.get_proposal(current_proposal_id)
            if (
                current["state"] == "prepared"
                and current["expires_at"] > time.time()
                and all(
                    current[field] == value
                    for field, value in proposal_fields.items()
                )
            ):
                _validate_stored_proposal(current)
                return _public_proposal(current)
        prepared_at = time.time()
        proposal_contract = {
            "schema_version": REVIEWED_FIX_SCHEMA_VERSION,
            **{
                field: proposal_fields[field]
                for field in (
                    "event_id",
                    "target_title",
                    "target_content_sha256",
                    "english_title",
                    "english_content_sha256",
                    "replacement_content_sha256",
                    "diff_sha256",
                    "summary",
                )
            },
            "minor": False,
            "publication_queue": self._publication_queue_name,
            "publication_action": "edit_malagasy_wiktionary_page",
            "environment_fingerprint": self._environment_fingerprint,
            "prepared_at": prepared_at,
            "expires_at": prepared_at + REVIEWED_FIX_VALIDITY_SECONDS,
        }
        approval_digest = _approval_digest(proposal_contract)
        proposal = {
            **proposal_contract,
            "proposal_id": f"wiktionary-fix:{approval_digest}",
            "replacement_content": proposal_fields["replacement_content"],
            "diff": proposal_fields["diff"],
            "approval_digest": approval_digest,
            "created_at": prepared_at,
        }
        stored = self._store.save_proposal(proposal)
        return _public_proposal(stored)

    def get_fix_proposal(self, proposal_id: str) -> Dict[str, Any]:
        """Return the exact diff and digest for a stored fix proposal."""
        proposal = self._store.get_proposal(proposal_id)
        _validate_stored_proposal(proposal)
        _require_unexpired_proposal(proposal)
        if proposal["environment_fingerprint"] != self._environment_fingerprint:
            raise WiktionaryReviewError(
                "The proposal belongs to a different review environment."
            )
        return _public_proposal(proposal)

    def queue_reviewed_fix(
        self,
        proposal_id: str,
        approval_digest: str,
    ) -> Dict[str, Any]:
        """Revalidate and queue one explicitly approved immutable proposal."""
        proposal = self._store.get_proposal(proposal_id)
        if proposal["state"] not in {"prepared", "queueing"}:
            raise WiktionaryReviewError(
                "Only a prepared Wiktionary fix proposal can be queued."
            )
        _validate_stored_proposal(proposal)
        if proposal["publication_queue"] != self._publication_queue_name:
            raise WiktionaryReviewError(
                "The proposal belongs to a different publication queue."
            )
        if proposal["environment_fingerprint"] != self._environment_fingerprint:
            raise WiktionaryReviewError(
                "The proposal belongs to a different review environment."
            )
        if approval_digest != proposal["approval_digest"]:
            raise WiktionaryReviewError("The proposal approval digest does not match.")
        proposal = self._store.claim_for_queue(proposal_id)
        claim_token = proposal["queue_claim_token"]
        publication_attempted = False
        try:
            _validate_stored_proposal(proposal)
            _require_unexpired_proposal(proposal)
            if approval_digest != proposal["approval_digest"]:
                raise WiktionaryReviewError(
                    "The proposal approval digest does not match."
                )
            target = self._snapshot_client.get_snapshot(
                "mg", proposal["target_title"]
            )
            english = self._snapshot_client.get_snapshot(
                "en", proposal["english_title"]
            )
            _require_main_namespace(target, "Malagasy target")
            _require_main_namespace(english, "English source")
            if target["content_sha256"] != proposal["target_content_sha256"]:
                raise WiktionaryReviewError(
                    "The Malagasy target changed after review; prepare and approve a new proposal."
                )
            if english["content_sha256"] != proposal["english_content_sha256"]:
                raise WiktionaryReviewError(
                    "The English source changed after review; prepare and approve a new proposal."
                )
            if (
                _build_review_diff(
                    proposal["target_title"],
                    target["content"],
                    proposal["replacement_content"],
                )
                != proposal["diff"]
            ):
                raise WiktionaryReviewError(
                    "The stored proposal diff no longer matches its replacement content."
                )
            publication_attempted = True
            self._publisher.publish_wikipage(
                proposal["replacement_content"],
                proposal["target_title"],
                summary=proposal["summary"],
                minor=False,
                expected_content_sha256=proposal["target_content_sha256"],
            )
        except WiktionaryReviewError:
            self._store.release_queue_claim(proposal_id, claim_token)
            raise
        except WiktionaryRabbitMqPublisherRejectedError as exc:
            self._store.release_queue_claim(proposal_id, claim_token)
            raise WiktionaryReviewError(
                "The reviewed edit was rejected before RabbitMQ accepted it."
            ) from exc
        except WiktionaryRabbitMqPublisherError as exc:
            self._store.mark_queue_unknown(proposal_id, claim_token)
            raise WiktionaryReviewError(
                "The reviewed fix queue outcome is unknown and requires reconciliation."
            ) from exc
        except Exception as exc:  # pylint: disable=broad-exception-caught
            if publication_attempted:
                self._store.mark_queue_unknown(proposal_id, claim_token)
            else:
                self._store.release_queue_claim(proposal_id, claim_token)
            raise WiktionaryReviewError(
                "The reviewed fix queue attempt failed unexpectedly."
            ) from exc
        try:
            queued = self._store.mark_queued(proposal_id, claim_token)
        except Exception as mark_exc:  # pylint: disable=broad-exception-caught
            try:
                self._store.mark_queue_unknown(proposal_id, claim_token)
            except Exception as unknown_exc:  # pylint: disable=broad-exception-caught
                raise WiktionaryReviewError(
                    "The reviewed fix queue outcome is unknown, and that state "
                    "could not be persisted; do not retry without operator "
                    "reconciliation."
                ) from unknown_exc
            raise WiktionaryReviewError(
                "The reviewed fix queue outcome is unknown and requires reconciliation."
            ) from mark_exc
        return {
            "status": "queued_for_publication",
            "published": False,
            "queue": self._publication_queue_name,
            "proposal_id": proposal_id,
            "event_id": queued["event_id"],
            "target_title": queued["target_title"],
            "expected_content_sha256": queued["target_content_sha256"],
            "message": (
                "The reviewed fix was accepted by the Wiktionary edit queue; "
                "the Wiktionary write has not been confirmed."
            ),
        }


def build_default_review_service(
    *,
    review_queue_name: str,
    state_path: str | Path,
    entry_translator_url: str,
    environment_fingerprint: str,
    publication_queue_name: str = DEFAULT_PAGE_CHECK_PUBLICATION_QUEUE,
) -> WiktionaryReviewService:
    """Build the local MCP review service from non-secret runtime locations."""
    validate_review_queue_separation(review_queue_name, {publication_queue_name})
    return WiktionaryReviewService(
        review_queue=RabbitMqPageCheckReviewQueue(review_queue_name),
        store=SqliteWiktionaryReviewStore(
            state_path,
            environment_fingerprint=environment_fingerprint,
        ),
        snapshot_client=EntryTranslatorSnapshotClient(entry_translator_url),
        publisher=WiktionaryRabbitMqPublisher(publication_queue_name),
        publication_queue_name=publication_queue_name,
        environment_fingerprint=environment_fingerprint,
    )


def _validate_snapshot(
    snapshot: Any,
    expected_language: str,
    expected_title: str,
) -> Dict[str, Any]:
    """Validate that entry translator returned an internally consistent snapshot."""
    if not isinstance(snapshot, dict):
        raise WiktionaryReviewError("Entry translator returned an invalid snapshot.")
    required = {
        "language",
        "title",
        "namespace",
        "content",
        "content_sha256",
        "entries",
        "parsed",
        "parse_error",
        "content_trust",
    }
    if not required.issubset(snapshot):
        raise WiktionaryReviewError("Entry translator returned an incomplete snapshot.")
    if (
        snapshot["language"] != expected_language
        or snapshot["title"] != expected_title
        or snapshot["namespace"] is not None
        and (isinstance(snapshot["namespace"], bool) or not isinstance(snapshot["namespace"], int))
        or not isinstance(snapshot["content"], str)
        or not isinstance(snapshot["entries"], list)
        or not isinstance(snapshot["parsed"], bool)
        or snapshot["parse_error"] is not None
        and not isinstance(snapshot["parse_error"], str)
        or snapshot["content_trust"] != "untrusted_wiktionary_content"
        or not isinstance(snapshot["content_sha256"], str)
        or not _SHA256_PATTERN.fullmatch(snapshot["content_sha256"])
        or _sha256(snapshot["content"]) != snapshot["content_sha256"]
    ):
        raise WiktionaryReviewError("Entry translator returned an invalid snapshot.")
    return dict(snapshot)


def _validate_title(title: Any) -> str:
    """Return one bounded non-empty Wiktionary title."""
    if not isinstance(title, str) or not title.strip():
        raise WiktionaryReviewError("A Wiktionary page title is required.")
    title = title.strip()
    if len(title) > _MAX_TITLE_LENGTH or "\x00" in title:
        raise WiktionaryReviewError("The Wiktionary page title is invalid.")
    return title


def _validate_sha256(value: Any, field: str) -> str:
    """Require a lowercase SHA-256 value used by a stale-content guard."""
    if not isinstance(value, str) or not _SHA256_PATTERN.fullmatch(value):
        raise WiktionaryReviewError(f"{field} must be a lowercase SHA-256 value.")
    return value


def _validate_replacement(content: Any) -> str:
    """Return bounded replacement wikitext without changing its exact bytes."""
    if (
        not isinstance(content, str)
        or not content
        or "\x00" in content
    ):
        raise WiktionaryReviewError("Replacement Wiktionary content is invalid.")
    if len(content.encode("utf-8")) > _MAX_REPLACEMENT_BYTES:
        raise WiktionaryReviewError("Replacement Wiktionary content is too large.")
    return content


def _validate_summary(summary: Any) -> str:
    """Return a bounded one-line edit summary."""
    if (
        not isinstance(summary, str)
        or not summary.strip()
        or len(summary) > _MAX_SUMMARY_LENGTH
        or "\n" in summary
        or "\r" in summary
        or "\x00" in summary
    ):
        raise WiktionaryReviewError("The Wiktionary edit summary is invalid.")
    return summary.strip()


def _require_main_namespace(snapshot: Dict[str, Any], label: str) -> None:
    """Reject review pages outside Wiktionary's main namespace."""
    if snapshot["namespace"] != 0:
        raise WiktionaryReviewError(f"{label} is not in the main namespace.")


def _build_review_diff(title: str, current: str, replacement: str) -> str:
    """Return an exact bounded unified diff suitable for explicit review."""
    lines = difflib.unified_diff(
        current.splitlines(keepends=True),
        replacement.splitlines(keepends=True),
        fromfile=f"mg.wiktionary/{title}:current",
        tofile=f"mg.wiktionary/{title}:proposed",
        n=3,
    )
    diff = "".join(
        line
        if line.endswith("\n")
        else f"{line}\n\\ No newline at end of file\n"
        for line in lines
    )
    if not diff:
        raise WiktionaryReviewError("The proposed replacement does not change the page.")
    if len(diff) > _MAX_DIFF_CHARACTERS:
        raise WiktionaryReviewError(
            "The proposed diff is too large for an explicit OpenCode review."
        )
    return diff


def _public_proposal(proposal: Dict[str, Any]) -> Dict[str, Any]:
    """Return proposal metadata and exact diff without duplicating full page content."""
    return {
        key: proposal[key]
        for key in (
            "proposal_id",
            "event_id",
            "target_title",
            "target_content_sha256",
            "english_title",
            "english_content_sha256",
            "replacement_content_sha256",
            "diff_sha256",
            "summary",
            "publication_queue",
            "environment_fingerprint",
            "prepared_at",
            "expires_at",
            "diff",
            "approval_digest",
            "state",
            "created_at",
            "queue_started_at",
            "queued_at",
        )
    } | {
        "schema_version": REVIEWED_FIX_SCHEMA_VERSION,
        "minor": False,
        "publication_action": "edit_malagasy_wiktionary_page",
        "content_trust": "proposal_diff_contains_untrusted_wiktionary_content",
        "publication_status": (
            "queued_not_published"
            if proposal["state"] == "queued"
            else "queue_attempt_in_progress"
            if proposal["state"] == "queueing"
            else "queue_outcome_unknown"
            if proposal["state"] == "queue_unknown"
            else "not_queued"
        ),
    }


def _approval_digest(proposal_contract: Dict[str, Any]) -> str:
    """Hash the complete immutable contract shown for explicit approval."""
    return reviewed_fix_approval_digest(proposal_contract)


def _validate_stored_proposal(proposal: Dict[str, Any]) -> None:
    """Verify every stored publication field against its approval contract."""
    target_title = _validate_title(proposal.get("target_title"))
    english_title = _validate_title(proposal.get("english_title"))
    target_hash = _validate_sha256(
        proposal.get("target_content_sha256"), "target_content_sha256"
    )
    english_hash = _validate_sha256(
        proposal.get("english_content_sha256"), "english_content_sha256"
    )
    replacement = _validate_replacement(proposal.get("replacement_content"))
    replacement_hash = _validate_sha256(
        proposal.get("replacement_content_sha256"),
        "replacement_content_sha256",
    )
    summary = _validate_summary(proposal.get("summary"))
    diff_hash = _validate_sha256(proposal.get("diff_sha256"), "diff_sha256")
    publication_queue = proposal.get("publication_queue")
    if not isinstance(publication_queue, str) or not _QUEUE_NAME_PATTERN.fullmatch(
        publication_queue
    ):
        raise WiktionaryReviewError("The stored publication queue is invalid.")
    event_id = proposal.get("event_id")
    if not isinstance(event_id, str) or not event_id:
        raise WiktionaryReviewError("The stored proposal event ID is invalid.")
    prepared_at = proposal.get("prepared_at")
    expires_at = proposal.get("expires_at")
    if (
        isinstance(prepared_at, bool)
        or not isinstance(prepared_at, (int, float))
        or not math.isfinite(prepared_at)
        or isinstance(expires_at, bool)
        or not isinstance(expires_at, (int, float))
        or not math.isfinite(expires_at)
        or expires_at <= prepared_at
        or expires_at - prepared_at > REVIEWED_FIX_VALIDITY_SECONDS
    ):
        raise WiktionaryReviewError("The stored proposal validity window is invalid.")
    if _sha256(replacement) != replacement_hash:
        raise WiktionaryReviewError("The stored replacement content is invalid.")
    if _sha256(str(proposal.get("diff"))) != diff_hash:
        raise WiktionaryReviewError("The stored proposal diff hash is invalid.")
    contract = {
        "schema_version": REVIEWED_FIX_SCHEMA_VERSION,
        "event_id": event_id,
        "target_title": target_title,
        "target_content_sha256": target_hash,
        "english_title": english_title,
        "english_content_sha256": english_hash,
        "replacement_content_sha256": replacement_hash,
        "diff_sha256": diff_hash,
        "summary": summary,
        "minor": False,
        "publication_queue": publication_queue,
        "publication_action": "edit_malagasy_wiktionary_page",
        "environment_fingerprint": _validate_sha256(
            proposal.get("environment_fingerprint"), "environment_fingerprint"
        ),
        "prepared_at": prepared_at,
        "expires_at": expires_at,
    }
    digest = _approval_digest(contract)
    if (
        proposal.get("approval_digest") != digest
        or proposal.get("proposal_id") != f"wiktionary-fix:{digest}"
    ):
        raise WiktionaryReviewError(
            "The stored proposal no longer matches its approval contract."
        )


def _require_unexpired_proposal(proposal: Dict[str, Any]) -> None:
    """Reject an approval after its bounded publication window closes."""
    if proposal["expires_at"] <= time.time():
        raise WiktionaryReviewError(
            "The reviewed proposal expired; prepare and approve a new proposal."
        )


def _sha256(content: str) -> str:
    """Return the UTF-8 SHA-256 for exact Wiktionary content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
