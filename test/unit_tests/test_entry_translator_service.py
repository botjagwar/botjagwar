from __future__ import annotations

import hashlib
import json
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field as dataclass_field
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional

import pytest

from api.services import entry_translator_service as service_module
from api.services.entry_translator_service import (
    CheckJobStoreError,
    EntryTranslatorService,
    JobErrorStore,
    QueueCounter,
    RedisCheckJobStore,
    RedisQueueCounter,
    RedisTranslationJobStore,
    ServiceError,
    TranslationJobStoreError,
)
from api.services.page_checker_settings import PageCheckerSettings, PageCheckerSettingsStore
from api.services.page_check_review_queue import PageCheckReviewQueueError
from api.services.definition_translation_settings import (
    DefinitionTranslationSettings,
    DefinitionTranslationSettingsStore,
)
from api.translation_v2.core import TranslationPageResult
from api.wikimedia_rate_limiter import WikimediaRateLimitError


EMPTY_EXECUTOR_STATUS = {
    "process_admitted_jobs": 0,
    "process_running_jobs": 0,
    "process_queued_jobs": 0,
    "process_job_capacity": 25,
    "available_job_slots": 25,
    "max_async_workers": 4,
    "accepting_async_jobs": True,
    "rejected_job_count": 0,
    "completed_job_count": 0,
    "failed_job_count": 0,
}


class DummyTranslation:
    def __init__(self) -> None:
        self.processed_pages: List[Any] = []
        self.translations: List[Any] = []
        self.process_result: Any = TranslationPageResult(
            title="hello",
            language="en",
            status="published",
            message="Translated entries were published.",
            entries_count=1,
            published=True,
        )

    def process_wiktionary_wiki_page(self, page: Any, custom_publish_function=None) -> Any:
        self.processed_pages.append(page)
        if custom_publish_function:
            custom_publish_function(page.title(), [])
        return self.process_result

    def translate_wiktionary_page(self, processor: Any) -> List[Any]:
        return self.translations


class DummyPublisher:
    def __init__(self) -> None:
        self.published: List[Dict[str, Any]] = []

    def publish_to_wiktionary(
        self,
        translation: Any,
        publication_guard: Optional[Callable[[], None]] = None,
        publication_filter: Optional[Callable[[str, str], bool]] = None,
    ) -> Callable[[str, List[Any]], None]:
        del publication_filter
        def _publish(title: str, entries: List[Any]) -> None:
            if publication_guard is not None:
                publication_guard()
            self.published.append({"title": title, "entries": entries})

        return _publish


class DummyReviewQueue:
    """Capture page-check jobs sent for manual review."""

    def __init__(self, error: Exception | None = None) -> None:
        """Initialize the captured jobs and optional transport failure."""
        self.jobs: List[Dict[str, Any]] = []
        self.error = error

    def publish_job(self, job: Dict[str, Any]) -> str:
        """Capture one review job or raise the configured failure."""
        return self.publish_message(
            service_module.build_page_check_review_message(job)
        )

    def publish_message(self, message: Dict[str, Any]) -> str:
        """Capture one immutable review message or raise the configured failure."""
        if self.error is not None:
            raise self.error
        self.jobs.append(json.loads(json.dumps(message)))
        return str(message["event_id"])


@dataclass
class DummyTranslationData:
    part_of_speech: str
    payload: Dict[str, Any]

    def serialise(self) -> Dict[str, Any]:
        return self.payload


@dataclass
class DummyEntry:
    language: str
    part_of_speech: str
    definitions: List[str]
    additional_data: Dict[str, Any] = dataclass_field(default_factory=dict)

    def serialise(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "language": self.language,
            "part_of_speech": self.part_of_speech,
        }
        if self.additional_data:
            data["additional_data"] = dict(self.additional_data)
        return data


class DummyProcessor:
    def __init__(self) -> None:
        self.text: str | None = None
        self.title_value: str | None = None
        self.processed_page: Any | None = None
        self.entries: List[DummyEntry] = []
        self.translations: List[DummyTranslationData] = []
        self.descendants: List[Dict[str, Any]] = []
        self.descendant_requests: List[tuple[str, str, int | None]] = []

    def set_text(self, text: str) -> None:
        self.text = text

    def set_title(self, title: str) -> None:
        self.title_value = title

    def process(self, page: Any) -> None:
        self.processed_page = page

    def get_all_entries(self, **_kwargs: Any) -> List[DummyEntry]:
        return self.entries

    def advanced_extract_definition(self, part_of_speech: str, definition: str) -> str:
        return f"{part_of_speech}:{definition}"

    def retrieve_translations(self) -> List[DummyTranslationData]:
        return self.translations

    def get_descendant_tree(
        self,
        language: str,
        part_of_speech: str,
        max_nodes: int | None = None,
    ) -> List[Dict[str, Any]]:
        self.descendant_requests.append((language, part_of_speech, max_nodes))
        return self.descendants


class DummyPage:
    def __init__(self, title: str, text: str = "body") -> None:
        self._title = title
        self._text = text
        self.force_refreshes: List[bool] = []

    def title(self) -> str:
        return self._title

    def get(self, force_refresh: bool = False) -> str:
        self.force_refreshes.append(force_refresh)
        return self._text

    @staticmethod
    def namespace() -> Any:
        return type("Namespace", (), {"id": 0})()


class FakeRedis:
    """Small Redis test double used by queue and error-store tests."""

    def __init__(self) -> None:
        self.values: Dict[str, Any] = {}
        self.expirations: Dict[str, Optional[int]] = {}
        self.lists: Dict[str, List[str]] = {}
        self.hashes: Dict[str, Dict[str, str]] = {}
        self._eval_lock = threading.Lock()

    def incr(self, key: str) -> int:
        self.values[key] = int(self.values.get(key, 0)) + 1
        return self.values[key]

    def decr(self, key: str) -> int:
        self.values[key] = int(self.values.get(key, 0)) - 1
        return self.values[key]

    def get(self, key: str) -> Any:
        return self.values.get(key)

    def set(
        self,
        key: str,
        value: Any,
        ex: Optional[int] = None,
        nx: bool = False,
    ) -> bool:
        if nx and key in self.values:
            return False
        self.values[key] = value
        self.expirations[key] = ex
        return True

    def mget(self, keys: List[str]) -> List[Any]:
        """Return multiple string values in key order."""
        return [self.values.get(key) for key in keys]

    def mset(self, values: Dict[str, Any]) -> None:
        """Replace multiple string values atomically for settings tests."""
        self.values.update(values)

    def hset(
        self,
        key: str,
        field: Optional[str] = None,
        value: Optional[str] = None,
        mapping: Optional[Dict[str, str]] = None,
    ) -> None:
        values = self.hashes.setdefault(key, {})
        if mapping is not None:
            values.update(mapping)
        elif field is not None and value is not None:
            values[field] = value

    def hgetall(self, key: str) -> Dict[str, str]:
        return dict(self.hashes.get(key, {}))

    def hget(self, key: str, field: str) -> Any:
        return self.hashes.get(key, {}).get(field)

    def hlen(self, key: str) -> int:
        return len(self.hashes.get(key, {}))

    def hdel(self, key: str, *fields: str) -> None:
        for field in fields:
            self.hashes.get(key, {}).pop(field, None)

    def eval(self, script: str, number_of_keys: int, *keys_and_arguments: Any) -> Any:
        """Emulate the Redis scripts used by job stores and active records."""
        if script == RedisQueueCounter._CLAIM_JOB_SCRIPT:
            assert number_of_keys == 2
            key, heartbeat_key, job_id, payload, started_at = keys_and_arguments
            with self._eval_lock:
                if str(job_id) in self.hashes.get(str(key), {}):
                    return 0
                self.hset(str(key), str(job_id), str(payload))
                self.hset(str(heartbeat_key), str(job_id), str(started_at))
            return 1
        if script == RedisQueueCounter._TOUCH_JOB_SCRIPT:
            assert number_of_keys == 2
            key, heartbeat_key, job_id, touched_at, owner_token = keys_and_arguments
            with self._eval_lock:
                record = self.hashes.get(str(key), {}).get(str(job_id))
                if record is None:
                    self.hdel(str(heartbeat_key), str(job_id))
                    return 0
                if owner_token and json.loads(record).get("_owner_token") != owner_token:
                    return 0
                self.hset(str(heartbeat_key), str(job_id), str(touched_at))
                return 1
        if script == RedisQueueCounter._FINISH_JOB_SCRIPT:
            assert number_of_keys == 2
            key, heartbeat_key, job_id, owner_token = keys_and_arguments
            with self._eval_lock:
                record = self.hashes.get(str(key), {}).get(str(job_id))
                if record is None:
                    self.hdel(str(heartbeat_key), str(job_id))
                    return 0
                if owner_token and json.loads(record).get("_owner_token") != owner_token:
                    return 0
                self.hdel(str(key), str(job_id))
                self.hdel(str(heartbeat_key), str(job_id))
                return 1
        if script == RedisQueueCounter._OWNS_JOB_SCRIPT:
            assert number_of_keys == 1
            key, job_id, owner_token = keys_and_arguments
            with self._eval_lock:
                record = self.hashes.get(str(key), {}).get(str(job_id))
                return int(
                    record is not None
                    and json.loads(record).get("_owner_token") == owner_token
                )
        if script == RedisQueueCounter._RECOVER_JOB_SCRIPT:
            assert number_of_keys == 2
            key, heartbeat_key, job_id, observed_heartbeat = keys_and_arguments
            with self._eval_lock:
                if str(job_id) not in self.hashes.get(str(key), {}):
                    return 0
                current = self.hashes.get(str(heartbeat_key), {}).get(str(job_id))
                if observed_heartbeat == "__missing__":
                    if current is not None:
                        return 0
                elif current != observed_heartbeat:
                    return 0
                self.hdel(str(key), str(job_id))
                self.hdel(str(heartbeat_key), str(job_id))
                return 1

        if script == RedisTranslationJobStore._PUT_OWNED_SCRIPT:
            assert number_of_keys == 1
            key, owner_token, payload, ttl_seconds = keys_and_arguments
            with self._eval_lock:
                raw_job = self.values.get(str(key))
                if raw_job is None:
                    return -1
                try:
                    current = json.loads(raw_job)
                except (json.JSONDecodeError, TypeError):
                    return -2
                if not isinstance(current, dict):
                    return -2
                if current.get("_owner_token") != owner_token:
                    return 0
                if current.get("status") in ("done", "error"):
                    return 0
                self.values[str(key)] = payload
                self.expirations[str(key)] = int(ttl_seconds)
                return 1

        if script == RedisCheckJobStore._COMPARE_AND_SET_SCRIPT:
            assert number_of_keys == 1
            key, job_id, observed, replacement = keys_and_arguments
            with self._eval_lock:
                current = self.hashes.get(str(key), {}).get(str(job_id))
                if current is None:
                    return 0
                observed_text = (
                    observed.decode() if isinstance(observed, bytes) else str(observed)
                )
                if current != observed_text:
                    return -1
                replacement_text = (
                    replacement.decode()
                    if isinstance(replacement, bytes)
                    else str(replacement)
                )
                self.hashes[str(key)][str(job_id)] = replacement_text
                return 1

        if script == RedisCheckJobStore._REMOVE_TERMINAL_SCRIPT:
            assert number_of_keys == 1
            key, job_id = keys_and_arguments
            with self._eval_lock:
                raw_job = self.hashes.get(str(key), {}).get(str(job_id))
                if raw_job is None:
                    return 0
                try:
                    job = json.loads(raw_job)
                except (json.JSONDecodeError, TypeError):
                    return -1
                if not isinstance(job, dict):
                    return -1
                if job.get("status") in {"done", "error"} and job.get(
                    "review_queue_state"
                ) not in {"pending", "failed", "publishing"}:
                    self.hdel(str(key), str(job_id))
                    return 1
                return 0

        # RedisCheckJobStore's bounded insertion script.
        assert number_of_keys == 1
        key = str(keys_and_arguments[0])
        maximum_jobs = int(keys_and_arguments[1])
        maximum_unfinished_jobs = int(keys_and_arguments[2])
        job_arguments = keys_and_arguments[3:]
        with self._eval_lock:
            terminal = []
            unfinished_count = 0
            for job_id, payload in self.hashes.get(key, {}).items():
                try:
                    job = json.loads(payload)
                except json.JSONDecodeError:
                    return -2
                if not isinstance(job, dict):
                    return -2
                if not isinstance(job.get("created_at"), (int, float)):
                    return -2
                if job.get("status") in ("pending", "running"):
                    unfinished_count += 1
                elif job.get("status") in ("done", "error"):
                    if job.get("review_queue_state") not in {
                        "pending",
                        "failed",
                        "publishing",
                    }:
                        terminal.append((float(job["created_at"]), job_id))
                else:
                    return -2
            if unfinished_count + len(job_arguments) // 2 > maximum_unfinished_jobs:
                return -1
            overflow = max(
                0,
                len(self.hashes.get(key, {})) + len(job_arguments) // 2 - maximum_jobs,
            )
            if overflow > len(terminal):
                return -3
            for index in range(0, len(job_arguments), 2):
                self.hset(key, str(job_arguments[index]), str(job_arguments[index + 1]))
            terminal.sort()
            for _created_at, job_id in terminal[:overflow]:
                self.hdel(key, job_id)
            return len(self.hashes.get(key, {}))

    def lpush(self, key: str, value: str) -> None:
        self.lists.setdefault(key, []).insert(0, value)

    def ltrim(self, key: str, start: int, end: int) -> None:
        self.lists[key] = self.lists.get(key, [])[start : end + 1]

    def lrange(self, key: str, start: int, end: int) -> List[str]:
        return self.lists.get(key, [])[start : end + 1]


class FailingRedis:
    """Redis test double that raises on every operation."""

    def incr(self, _key: str) -> int:
        raise service_module.redis.RedisError("down")

    def decr(self, _key: str) -> int:
        raise service_module.redis.RedisError("down")

    def get(self, _key: str) -> Any:
        raise service_module.redis.RedisError("down")

    def set(
        self,
        _key: str,
        _value: Any,
        ex: Optional[int] = None,
        nx: bool = False,
    ) -> None:
        """Fail a Redis string write."""
        del ex, nx
        raise service_module.redis.RedisError("down")

    def mget(self, _keys: List[str]) -> List[Any]:
        """Fail a multi-value Redis read."""
        raise service_module.redis.RedisError("down")

    def mset(self, _values: Dict[str, Any]) -> None:
        """Fail a multi-value Redis write."""
        raise service_module.redis.RedisError("down")

    def hset(
        self,
        _key: str,
        _field: Optional[str] = None,
        _value: Optional[str] = None,
        mapping: Optional[Dict[str, str]] = None,
    ) -> None:
        del mapping
        raise service_module.redis.RedisError("down")

    def hgetall(self, _key: str) -> Dict[str, str]:
        raise service_module.redis.RedisError("down")

    def hget(self, _key: str, _field: str) -> Any:
        raise service_module.redis.RedisError("down")

    def hdel(self, _key: str, *_fields: str) -> None:
        raise service_module.redis.RedisError("down")

    def eval(self, _script: str, _number_of_keys: int, *_arguments: Any) -> int:
        raise service_module.redis.RedisError("down")

    def lpush(self, _key: str, _value: str) -> None:
        raise service_module.redis.RedisError("down")

    def ltrim(self, _key: str, _start: int, _end: int) -> None:
        raise service_module.redis.RedisError("down")

    def lrange(self, _key: str, _start: int, _end: int) -> List[str]:
        raise service_module.redis.RedisError("down")


class RecordingTranslationJobStore:
    """In-memory recorder for observable translation job transitions."""

    def __init__(self) -> None:
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.writes: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def create(self, job: Dict[str, Any]) -> bool:
        """Create one record atomically for idempotency tests."""
        with self._lock:
            if job["job_id"] in self.jobs:
                return False
            self.put(job)
            return True

    def put_owned(self, job: Dict[str, Any], owner_token: str) -> bool:
        """Update one active record only for its current owner."""
        with self._lock:
            current = self.jobs.get(job["job_id"])
            if (
                current is None
                or current.get("_owner_token") != owner_token
                or current.get("status") in ("done", "error")
            ):
                return False
            self.put(job)
            return True

    def put(self, job: Dict[str, Any]) -> None:
        snapshot = json.loads(json.dumps(job))
        self.jobs[job["job_id"]] = snapshot
        self.writes.append(snapshot)

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        job = self.jobs.get(job_id)
        return None if job is None else dict(job)


def test_service_error_string() -> None:
    error = ServiceError("boom")

    assert str(error) == "boom"


def test_translation_job_store_uses_per_job_json_keys_with_24_hour_ttl() -> None:
    redis_client = FakeRedis()
    store = RedisTranslationJobStore(redis_client=redis_client, key_prefix="jobs")
    job = {
        "job_id": "job-1",
        "language": "en",
        "title": "hello",
        "status": "pending",
        "stage": "queued",
        "publication_state": "not_queued",
        "created_at": 1.0,
        "last_updated_at": 1.0,
        "result": None,
        "error": None,
        "message": "Translation job queued.",
    }

    store.put(job)

    assert json.loads(redis_client.values["jobs:job-1"]) == job
    assert redis_client.expirations["jobs:job-1"] == 24 * 60 * 60
    assert store.get("job-1") == job
    assert store.get("missing") is None

    duplicate = dict(job, title="other")
    assert store.create(duplicate) is False
    assert store.get("job-1") == job


def test_translation_job_store_rejects_invalid_records_and_redis_failures() -> None:
    with pytest.raises(ValueError, match="ttl_seconds"):
        RedisTranslationJobStore(redis_client=FakeRedis(), ttl_seconds=0)

    store = RedisTranslationJobStore(redis_client=FakeRedis(), key_prefix="jobs")
    with pytest.raises(TranslationJobStoreError, match="record is invalid"):
        store.put({})
    with pytest.raises(TranslationJobStoreError, match="record is invalid"):
        store.put({"job_id": "", "created_at": float("nan")})

    store._redis_client.values["jobs:bad-json"] = "{"
    store._redis_client.values["jobs:not-an-object"] = "[]"
    with pytest.raises(TranslationJobStoreError, match="invalid data"):
        store.get("bad-json")
    with pytest.raises(TranslationJobStoreError, match="invalid data"):
        store.get("not-an-object")

    unavailable = RedisTranslationJobStore(redis_client=FailingRedis())
    with pytest.raises(TranslationJobStoreError, match="written"):
        unavailable.put({"job_id": "job-1"})
    with pytest.raises(TranslationJobStoreError, match="read"):
        unavailable.get("job-1")


def test_translation_job_store_fences_updates_after_a_terminal_transition() -> None:
    store = RedisTranslationJobStore(redis_client=FakeRedis(), key_prefix="jobs")
    pending = {
        "job_id": "job-1",
        "language": "en",
        "title": "hello",
        "status": "pending",
        "_owner_token": "owner-1",
    }
    assert store.create(pending) is True

    failed = dict(pending, status="error", error="lease expired")
    assert store.put_owned(failed, "owner-1") is True

    stale_completion = dict(pending, status="done", result={"status": "ok"})
    assert store.put_owned(stale_completion, "owner-1") is False
    assert store.get("job-1") == failed


def test_translation_job_store_reports_owned_update_failures() -> None:
    store = RedisTranslationJobStore(redis_client=FakeRedis(), key_prefix="jobs")
    job = {"job_id": "missing", "status": "running", "_owner_token": "owner-1"}

    with pytest.raises(TranslationJobStoreError, match="invalid data"):
        store.put_owned(job, "owner-1")

    store._redis_client.values["jobs:missing"] = "[]"
    with pytest.raises(TranslationJobStoreError, match="invalid data"):
        store.put_owned(job, "owner-1")

    unavailable = RedisTranslationJobStore(redis_client=FailingRedis())
    with pytest.raises(TranslationJobStoreError, match="written"):
        unavailable.put_owned(job, "owner-1")


def test_check_result_counts_empty_and_unknown_results() -> None:
    assert service_module._count_check_results(None) == {
        "good": 0,
        "fixed": 0,
        "unverifiable": 0,
        "error": 0,
    }
    assert service_module._count_check_results([{"status": "unexpected"}])["error"] == 1


def test_page_check_period_helpers_cover_month_ends_and_grade_boundaries() -> None:
    as_of = datetime(2024, 5, 31, 12, 30, tzinfo=timezone.utc)

    assert service_module._subtract_calendar_months(as_of, 3) == datetime(
        2024, 2, 29, 12, 30, tzinfo=timezone.utc
    )
    with pytest.raises(ValueError, match="must not be negative"):
        service_module._subtract_calendar_months(as_of, -1)

    bounds = service_module._page_check_period_bounds(as_of.timestamp())
    assert [period for period, _start, _end in bounds] == [
        "today",
        "last_7_days",
        "current_week",
        "current_month",
        "last_3_months",
        "last_6_months",
    ]
    by_period = {period: start for period, start, _end in bounds}
    assert datetime.fromtimestamp(by_period["today"], timezone.utc) == datetime(
        2024, 5, 31, tzinfo=timezone.utc
    )
    assert datetime.fromtimestamp(by_period["current_week"], timezone.utc) == datetime(
        2024, 5, 27, tzinfo=timezone.utc
    )
    assert datetime.fromtimestamp(by_period["current_month"], timezone.utc) == datetime(
        2024, 5, 1, tzinfo=timezone.utc
    )

    assert [service_module._page_check_grade(value) for value in (None, 90, 80, 70, 60, 59.9)] == [
        None,
        "A",
        "B",
        "C",
        "D",
        "E",
    ]


def test_page_check_job_outcome_defensively_counts_terminal_failures() -> None:
    assert service_module._page_check_job_outcome({"status": "pending"}) is None
    assert service_module._page_check_job_outcome({"status": "error"}) == "error"
    assert service_module._page_check_job_outcome({"status": "done", "results": None}) == "error"
    assert service_module._page_check_job_outcome({"status": "done", "results": []}) == "error"
    assert service_module._page_check_job_outcome({"status": "done", "results": ["bad"]}) == "error"
    assert service_module._page_check_job_outcome(
        {"status": "done", "results": [{"status": "unknown"}]}
    ) == "error"
    assert service_module._page_check_job_outcome(
        {"status": "done", "results": [{"status": "fixed"}]}
    ) == "fixed"


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"max_async_workers": 0}, "max_async_workers"),
        ({"max_pending_jobs": -1}, "max_pending_jobs"),
        ({"max_check_workers": 0}, "max_check_workers"),
        ({"max_check_jobs_kept": 0}, "max_check_jobs_kept"),
        ({"stale_job_timeout_seconds": 0}, "stale_job_timeout_seconds"),
    ],
)
def test_service_rejects_invalid_worker_limits(
    arguments: Dict[str, int], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        EntryTranslatorService(translation=DummyTranslation(), **arguments)


def test_health_and_job_count() -> None:
    translation = DummyTranslation()
    counter = QueueCounter()
    error_store = JobErrorStore(redis_client=FakeRedis())
    service = EntryTranslatorService(
        translation=translation,
        queue_counter=counter,
        job_error_store=error_store,
    )

    assert service.health_status() == {
        "status": "healthy",
        "jobs": 0,
        "counter_source": "local",
        "average_job_duration_seconds": None,
        "recent_job_error_count": 0,
        "recent_job_errors": [],
        "message": "Service is operating normally.",
        **EMPTY_EXECUTOR_STATUS,
    }
    assert service.job_count() == 0
    for _ in range(25):
        counter.increment()
    assert service.health_status() == {
        "status": "degraded",
        "jobs": 25,
        "counter_source": "local",
        "average_job_duration_seconds": None,
        "recent_job_error_count": 0,
        "recent_job_errors": [],
        "message": "High job queue length (over 25) indicates potential overload.",
        **EMPTY_EXECUTOR_STATUS,
    }
    assert service.job_count() == 25


def test_health_degraded_for_slow_jobs() -> None:
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        queue_counter=QueueCounter(),
        job_error_store=JobErrorStore(redis_client=FakeRedis()),
    )
    service._record_job_duration(301)

    assert service.health_status()["message"] == "Average job duration exceeds 5 minutes."


def test_health_degraded_for_recent_errors() -> None:
    error_store = JobErrorStore(redis_client=FakeRedis())
    error_store.record_error({"message": "bad", "error": "x", "type": "ValueError"})
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        queue_counter=QueueCounter(),
        job_error_store=error_store,
    )

    status = service.health_status()

    assert status["status"] == "degraded"
    assert status["recent_job_error_count"] == 1


def test_enqueue_translation_job_success() -> None:
    translation = DummyTranslation()
    publisher = DummyPublisher()
    counter = QueueCounter()
    store = RecordingTranslationJobStore()
    page = DummyPage("hello")

    def get_page(_title: str, _language: str):
        return page

    def run_immediately(task: Callable[[], None]):
        task()

    service = EntryTranslatorService(
        translation=translation,
        publisher=publisher,
        queue_counter=counter,
        job_error_store=JobErrorStore(redis_client=FakeRedis()),
        get_page_func=get_page,
        task_runner=run_immediately,
        translation_job_store=store,
    )

    pending = service.enqueue_translation_job("en", "hello")

    assert pending == {
        "job_id": pending["job_id"],
        "language": "en",
        "title": "hello",
        "status": "pending",
        "stage": "queued",
        "publication_state": "not_queued",
        "created_at": pending["created_at"],
        "last_updated_at": pending["created_at"],
        "result": None,
        "error": None,
        "message": "Translation job queued.",
    }
    assert publisher.published == [{"title": "hello", "entries": []}]
    assert counter.get() == 0
    assert [write["stage"] for write in store.writes] == [
        "queued",
        "loading_source",
        "translating",
        "queueing_publication",
        "publication_queued",
        "completed",
    ]
    finished = service.get_translation_job("en", pending["job_id"])
    assert finished["status"] == "done"
    assert finished["stage"] == "completed"
    assert finished["message"] == "Translation job completed."
    assert finished["publication_state"] == "queued"
    assert finished["result"]["status"] == "publication_queued"
    assert finished["result"]["published"] is False
    assert finished["result"]["message"] == (
        "Translated entries were queued for publication."
    )


@pytest.mark.parametrize(
    ("verdict", "expected_state", "expected_publications"),
    [
        ("good", "queued", ["hello"]),
        ("unverifiable", "filtered_out", []),
    ],
)
def test_translation_prefilter_only_queues_good_candidates(
    verdict: str,
    expected_state: str,
    expected_publications: List[str],
) -> None:
    """Enabled prefiltering checks exact candidate text and discards non-good pages."""
    checked: List[tuple[str, str, str, bool]] = []
    publications: List[str] = []

    class CandidateChecker:
        def check_page(
            self,
            language: str,
            title: str,
            *,
            candidate_content: str,
            repair: bool,
        ) -> Any:
            checked.append((language, title, candidate_content, repair))
            return SimpleNamespace(status=verdict)

    class CandidatePublisher:
        def publish_to_wiktionary(
            self,
            _translation: Any,
            publication_guard: Optional[Callable[[], None]] = None,
            publication_filter: Optional[Callable[[str, str], bool]] = None,
        ) -> Callable[[str, List[Any]], bool]:
            def publish(title: str, _entries: List[Any]) -> bool:
                content = "=={{=en=}}==\n# candidate\n{{wikibolana|en|hello}}"
                assert publication_filter is not None
                if not publication_filter(title, content):
                    return False
                if publication_guard is not None:
                    publication_guard()
                publications.append(title)
                return True

            return publish

    settings_store = PageCheckerSettingsStore(redis_client=FakeRedis())
    settings_store.set_translation_prefilter_enabled(True)
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        publisher=CandidatePublisher(),  # type: ignore[arg-type]
        page_check_service=CandidateChecker(),  # type: ignore[arg-type]
        page_checker_settings_store=settings_store,
        queue_counter=QueueCounter(),
        job_error_store=JobErrorStore(redis_client=FakeRedis()),
        get_page_func=lambda title, _language: DummyPage(title),
        task_runner=lambda task: task(),
        translation_job_store=RecordingTranslationJobStore(),
    )

    pending = service.enqueue_translation_job("en", "hello")
    finished = service.get_translation_job("en", pending["job_id"])

    assert checked == [
        (
            "mg",
            "hello",
            "=={{=en=}}==\n# candidate\n{{wikibolana|en|hello}}",
            False,
        )
    ]
    assert publications == expected_publications
    assert finished["publication_state"] == expected_state
    if verdict == "good":
        assert finished["result"]["status"] == "publication_queued"
    else:
        assert finished["result"]["status"] == "publication_filtered"
        assert finished["result"]["published"] is False


def test_enqueue_translation_job_is_idempotent_for_a_client_request_id() -> None:
    tasks: List[Callable[[], None]] = []
    counter = QueueCounter()
    store = RecordingTranslationJobStore()
    request_id = "9c9a6a48-2304-4505-9cfe-57fbddc88bb1"
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        publisher=DummyPublisher(),
        queue_counter=counter,
        job_error_store=JobErrorStore(redis_client=FakeRedis()),
        get_page_func=lambda title, _language: DummyPage(title),
        task_runner=tasks.append,
        translation_job_store=store,
    )

    first = service.enqueue_translation_job("en", "hello", request_id)
    duplicate = service.enqueue_translation_job("en", "hello", request_id.upper())

    assert first == duplicate
    assert first["job_id"] == request_id
    assert len(tasks) == 1
    assert counter.get() == 1

    with pytest.raises(ServiceError) as conflict:
        service.enqueue_translation_job("fr", "bonjour", request_id)
    assert conflict.value.status_code == 409

    tasks[0]()
    assert counter.get() == 0


def test_enqueue_translation_job_rejects_invalid_request_id_before_admission() -> None:
    tasks: List[Callable[[], None]] = []
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        publisher=DummyPublisher(),
        queue_counter=QueueCounter(),
        task_runner=tasks.append,
        translation_job_store=RecordingTranslationJobStore(),
    )

    with pytest.raises(ServiceError) as raised:
        service.enqueue_translation_job("en", "hello", "not-a-uuid")

    assert raised.value.status_code == 400
    assert tasks == []
    assert service.health_status()["available_job_slots"] == 25


def test_enqueue_translation_job_rejects_an_active_request_without_history() -> None:
    request_id = "9c9a6a48-2304-4505-9cfe-57fbddc88bb1"
    counter = QueueCounter()
    assert counter.claim_job("hello", "en", 1, request_id, "other-owner")
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        publisher=DummyPublisher(),
        queue_counter=counter,
        translation_job_store=RecordingTranslationJobStore(),
    )

    with pytest.raises(ServiceError) as raised:
        service.enqueue_translation_job("en", "hello", request_id)

    assert raised.value.status_code == 503
    assert raised.value.headers == {"Retry-After": "1"}
    assert service.health_status()["available_job_slots"] == 25


def test_enqueue_translation_job_handles_duplicate_store_without_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request_id = "9c9a6a48-2304-4505-9cfe-57fbddc88bb1"
    store = RecordingTranslationJobStore()
    calls = 0

    def disappearing_get(_job_id: str) -> Optional[Dict[str, Any]]:
        nonlocal calls
        calls += 1
        return None

    monkeypatch.setattr(store, "get", disappearing_get)
    monkeypatch.setattr(store, "create", lambda _job: False)
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        publisher=DummyPublisher(),
        queue_counter=QueueCounter(),
        translation_job_store=store,
    )

    with pytest.raises(ServiceError) as raised:
        service.enqueue_translation_job("en", "hello", request_id)

    assert raised.value.status_code == 503
    assert calls == 2
    assert service.health_status()["available_job_slots"] == 25


def test_stale_recovery_fences_a_paused_worker_before_publication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = [100.0]
    monkeypatch.setattr(service_module.time, "time", lambda: now[0])
    tasks: List[Callable[[], None]] = []
    counter = QueueCounter()
    store = RecordingTranslationJobStore()
    publisher = DummyPublisher()
    first_service = EntryTranslatorService(
        translation=DummyTranslation(),
        publisher=publisher,
        queue_counter=counter,
        job_error_store=JobErrorStore(redis_client=FakeRedis()),
        get_page_func=lambda title, _language: DummyPage(title),
        task_runner=tasks.append,
        translation_job_store=store,
        stale_job_timeout_seconds=30,
    )
    recovery_service = EntryTranslatorService(
        translation=DummyTranslation(),
        queue_counter=counter,
        job_error_store=JobErrorStore(redis_client=FakeRedis()),
        translation_job_store=store,
        stale_job_timeout_seconds=30,
    )

    pending = first_service.enqueue_translation_job("en", "hello")
    now[0] = 130.0
    recovered = recovery_service._recover_stale_jobs()
    tasks[0]()

    assert [job["job_id"] for job in recovered] == [pending["job_id"]]
    assert first_service.get_translation_job("en", pending["job_id"])["status"] == "error"
    assert publisher.published == []


def test_publication_guard_fences_recovery_at_the_external_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = [100.0]
    monkeypatch.setattr(service_module.time, "time", lambda: now[0])
    tasks: List[Callable[[], None]] = []
    counter = QueueCounter()
    store = RecordingTranslationJobStore()
    published: List[str] = []
    recovery_service: EntryTranslatorService

    class RecoveringPublisher:
        def publish_to_wiktionary(
            self,
            _translation: Any,
            publication_guard: Optional[Callable[[], None]] = None,
            publication_filter: Optional[Callable[[str, str], bool]] = None,
        ) -> Callable[[str, List[Any]], None]:
            del publication_filter
            def publish(title: str, _entries: List[Any]) -> None:
                now[0] = 130.0
                recovery_service._recover_stale_jobs()
                assert publication_guard is not None
                publication_guard()
                published.append(title)

            return publish

    service = EntryTranslatorService(
        translation=DummyTranslation(),
        publisher=RecoveringPublisher(),  # type: ignore[arg-type]
        queue_counter=counter,
        job_error_store=JobErrorStore(redis_client=FakeRedis()),
        get_page_func=lambda title, _language: DummyPage(title),
        task_runner=tasks.append,
        translation_job_store=store,
        stale_job_timeout_seconds=30,
    )
    recovery_service = EntryTranslatorService(
        translation=DummyTranslation(),
        queue_counter=counter,
        job_error_store=JobErrorStore(redis_client=FakeRedis()),
        translation_job_store=store,
        stale_job_timeout_seconds=30,
    )

    pending = service.enqueue_translation_job("en", "hello")
    tasks[0]()

    assert published == []
    assert service.get_translation_job("en", pending["job_id"])["status"] == "error"


def test_enqueue_translation_job_records_error_result() -> None:
    translation = DummyTranslation()
    translation.process_result = TranslationPageResult(
        title="hello",
        language="en",
        status="error",
        message="failed",
        error_type="TranslationError",
    )
    page = DummyPage("hello")
    error_store = JobErrorStore(redis_client=FakeRedis())
    job_store = RecordingTranslationJobStore()

    def get_page(_title: str, _language: str):
        return page

    def run_immediately(task: Callable[[], None]):
        task()

    service = EntryTranslatorService(
        translation=translation,
        publisher=DummyPublisher(),
        queue_counter=QueueCounter(),
        job_error_store=error_store,
        get_page_func=get_page,
        task_runner=run_immediately,
        translation_job_store=job_store,
    )

    pending = service.enqueue_translation_job("en", "hello")

    errors = service.recent_job_errors()
    assert errors[0]["title"] == "hello"
    assert errors[0]["type"] == "TranslationError"
    assert errors[0]["job_id"] == pending["job_id"]
    finished = service.get_translation_job("en", pending["job_id"])
    assert finished["status"] == "error"
    assert finished["stage"] == "failed"
    assert finished["result"]["status"] == "error"
    assert finished["error"] == "failed"


def test_enqueue_translation_job_records_exception() -> None:
    translation = DummyTranslation()

    def failing_process(_page: Any, custom_publish_function=None) -> None:
        raise RuntimeError("boom")

    translation.process_wiktionary_wiki_page = failing_process
    page = DummyPage("hello")
    error_store = JobErrorStore(redis_client=FakeRedis())
    job_store = RecordingTranslationJobStore()

    def get_page(_title: str, _language: str):
        return page

    def run_immediately(task: Callable[[], None]):
        task()

    service = EntryTranslatorService(
        translation=translation,
        publisher=DummyPublisher(),
        queue_counter=QueueCounter(),
        job_error_store=error_store,
        get_page_func=get_page,
        task_runner=run_immediately,
        translation_job_store=job_store,
    )

    pending = service.enqueue_translation_job("en", "hello")

    error = service.recent_job_errors()[0]
    assert error["type"] == "RuntimeError"
    assert error["job_id"] == pending["job_id"]
    finished = service.get_translation_job("en", pending["job_id"])
    assert finished["status"] == "error"
    assert finished["result"] is None
    assert finished["error"] == "boom"


def test_enqueue_translation_job_requires_publisher() -> None:
    translation = DummyTranslation()
    service = EntryTranslatorService(translation=translation)

    with pytest.raises(ServiceError) as exc:
        service.enqueue_translation_job("en", "hello")

    assert exc.value.status_code == 503


def test_enqueue_translation_job_defers_page_fetch_until_worker_runs() -> None:
    tasks: List[Callable[[], None]] = []
    fetches: List[tuple[str, str]] = []
    store = RecordingTranslationJobStore()

    def get_page(title: str, language: str) -> DummyPage:
        fetches.append((title, language))
        return DummyPage(title)

    service = EntryTranslatorService(
        translation=DummyTranslation(),
        publisher=DummyPublisher(),
        queue_counter=QueueCounter(),
        job_error_store=JobErrorStore(redis_client=FakeRedis()),
        get_page_func=get_page,
        task_runner=tasks.append,
        translation_job_store=store,
    )

    pending = service.enqueue_translation_job("en", "hello")

    assert fetches == []
    assert service.get_translation_job("en", pending["job_id"])["status"] == "pending"
    tasks[0]()
    assert fetches == [("hello", "en")]
    assert service.get_translation_job("en", pending["job_id"])["status"] == "done"


def test_translation_job_marks_publication_only_after_publisher_returns() -> None:
    store = RecordingTranslationJobStore()
    observed_states: List[tuple[str, str]] = []

    class InspectingPublisher:
        def publish_to_wiktionary(
            self,
            _translation: Any,
            publication_guard: Optional[Callable[[], None]] = None,
            publication_filter: Optional[Callable[[str, str], bool]] = None,
        ) -> Callable[[str, List[Any]], None]:
            del publication_filter
            def publish(_title: str, _entries: List[Any]) -> None:
                if publication_guard is not None:
                    publication_guard()
                latest = store.writes[-1]
                observed_states.append(
                    (latest["stage"], latest["publication_state"])
                )

            return publish

    service = EntryTranslatorService(
        translation=DummyTranslation(),
        publisher=InspectingPublisher(),
        queue_counter=QueueCounter(),
        job_error_store=JobErrorStore(redis_client=FakeRedis()),
        get_page_func=lambda title, _language: DummyPage(title),
        task_runner=lambda task: task(),
        translation_job_store=store,
    )

    pending = service.enqueue_translation_job("en", "hello")

    assert observed_states == [("queueing_publication", "not_queued")]
    assert service.get_translation_job("en", pending["job_id"])[
        "publication_state"
    ] == "queued"


def test_translation_job_fetch_failure_is_persisted_by_worker() -> None:
    tasks: List[Callable[[], None]] = []
    error_store = JobErrorStore(redis_client=FakeRedis())
    job_store = RecordingTranslationJobStore()

    def fail_fetch(_title: str, _language: str) -> DummyPage:
        raise RuntimeError("wiki unavailable")

    service = EntryTranslatorService(
        translation=DummyTranslation(),
        publisher=DummyPublisher(),
        queue_counter=QueueCounter(),
        job_error_store=error_store,
        get_page_func=fail_fetch,
        task_runner=tasks.append,
        translation_job_store=job_store,
    )

    pending = service.enqueue_translation_job("en", "hello")
    assert pending["status"] == "pending"

    tasks[0]()

    finished = service.get_translation_job("en", pending["job_id"])
    assert finished["status"] == "error"
    assert finished["stage"] == "failed"
    assert finished["publication_state"] == "not_queued"
    assert finished["result"] is None
    assert finished["error"] == "Unable to retrieve the requested page."
    assert service.recent_job_errors()[0]["job_id"] == pending["job_id"]


def test_translation_job_status_is_language_scoped_and_authoritative() -> None:
    store = RecordingTranslationJobStore()
    store.put(
        {
            "job_id": "job-1",
            "language": "en",
            "title": "hello",
            "status": "pending",
        }
    )
    service = EntryTranslatorService(
        translation=DummyTranslation(), translation_job_store=store
    )

    assert service.get_translation_job("en", "job-1")["title"] == "hello"
    for language, job_id in (("fr", "job-1"), ("en", "missing")):
        with pytest.raises(ServiceError) as exc:
            service.get_translation_job(language, job_id)
        assert exc.value.status_code == 404

    unavailable_service = EntryTranslatorService(
        translation=DummyTranslation(),
        translation_job_store=RedisTranslationJobStore(
            redis_client=FailingRedis()
        ),
    )
    with pytest.raises(ServiceError) as unavailable:
        unavailable_service.get_translation_job("en", "job-1")
    assert unavailable.value.status_code == 503
    assert unavailable.value.message == (
        "Translation job history is temporarily unavailable."
    )


def test_translation_job_status_recovers_a_durable_job_without_a_lease(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = RecordingTranslationJobStore()
    store.put(
        {
            "job_id": "job-1",
            "language": "en",
            "title": "hello",
            "status": "pending",
            "stage": "queued",
            "publication_state": "not_queued",
            "created_at": 10,
            "last_updated_at": 10,
            "result": None,
            "error": None,
            "message": "Translation job queued.",
            "_owner_token": "owner-1",
        }
    )
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        queue_counter=QueueCounter(),
        job_error_store=JobErrorStore(redis_client=FakeRedis()),
        translation_job_store=store,
        stale_job_timeout_seconds=30,
    )
    monkeypatch.setattr(service_module.time, "time", lambda: 40)

    recovered = service.get_translation_job("en", "job-1")

    assert recovered["status"] == "error"
    assert recovered["stage"] == "failed"
    assert "_owner_token" not in recovered
    assert service.recent_job_errors()[0]["type"] == "MissingJobLease"


def test_translation_job_status_preserves_active_and_legacy_records() -> None:
    counter = QueueCounter()
    store = RecordingTranslationJobStore()
    active = {
        "job_id": "active",
        "language": "en",
        "title": "hello",
        "status": "running",
        "last_updated_at": 1,
        "_owner_token": "owner-1",
    }
    legacy = {
        "job_id": "legacy",
        "language": "en",
        "title": "world",
        "status": "pending",
        "last_updated_at": 1,
    }
    assert counter.claim_job("hello", "en", 1, "active", "owner-1")
    store.put(active)
    store.put(legacy)
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        queue_counter=counter,
        translation_job_store=store,
    )

    assert service.get_translation_job("en", "active")["status"] == "running"
    assert service.get_translation_job("en", "legacy")["status"] == "pending"


def test_translation_job_status_rejects_invalid_unleased_timestamp() -> None:
    store = RecordingTranslationJobStore()
    store.put(
        {
            "job_id": "job-1",
            "language": "en",
            "title": "hello",
            "status": "pending",
            "last_updated_at": "invalid",
            "_owner_token": "owner-1",
        }
    )
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        queue_counter=QueueCounter(),
        translation_job_store=store,
    )

    with pytest.raises(ServiceError) as raised:
        service.get_translation_job("en", "job-1")

    assert raised.value.status_code == 503


def test_translation_job_heartbeat_retries_a_transient_coordination_failure() -> None:
    class HeartbeatCounter(QueueCounter):
        def __init__(self) -> None:
            super().__init__()
            self.touches = 0

        def touch_job(
            self,
            job_id: str,
            touched_at: float,
            owner_token: Optional[str] = None,
        ) -> bool:
            del job_id, touched_at, owner_token
            self.touches += 1
            if self.touches == 1:
                raise TranslationJobStoreError("temporary Redis failure")
            return False

    class ImmediateEvent:
        def wait(self, _timeout: float) -> bool:
            return False

    counter = HeartbeatCounter()
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        queue_counter=counter,
    )

    service._heartbeat_translation_job(
        "job-1",
        "owner-1",
        ImmediateEvent(),  # type: ignore[arg-type]
    )

    assert counter.touches == 2


def test_translation_job_initial_store_failure_releases_admission() -> None:
    tasks: List[Callable[[], None]] = []
    counter = QueueCounter()
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        publisher=DummyPublisher(),
        queue_counter=counter,
        job_error_store=JobErrorStore(redis_client=FakeRedis()),
        get_page_func=lambda _title, _language: pytest.fail("must not fetch"),
        task_runner=tasks.append,
        translation_job_store=RedisTranslationJobStore(
            redis_client=FailingRedis()
        ),
    )

    with pytest.raises(ServiceError) as exc:
        service.enqueue_translation_job("en", "hello")

    assert exc.value.status_code == 503
    assert counter.get() == 0
    assert tasks == []
    assert service.health_status()["available_job_slots"] == 25


def test_translation_job_submission_failure_is_persisted_and_cleaned_up() -> None:
    store = RecordingTranslationJobStore()
    counter = QueueCounter()
    error_store = JobErrorStore(redis_client=FakeRedis())

    def fail_submission(_task: Callable[[], None]) -> None:
        raise RuntimeError("executor unavailable")

    service = EntryTranslatorService(
        translation=DummyTranslation(),
        publisher=DummyPublisher(),
        queue_counter=counter,
        job_error_store=error_store,
        task_runner=fail_submission,
        translation_job_store=store,
    )

    with pytest.raises(RuntimeError, match="executor unavailable"):
        service.enqueue_translation_job("en", "hello")

    finished = store.writes[-1]
    assert finished["status"] == "error"
    assert finished["stage"] == "failed"
    assert finished["error"] == "The translation job could not be started."
    assert counter.get() == 0
    assert service.health_status()["available_job_slots"] == 25
    assert error_store.recent_errors()[0]["job_id"] == finished["job_id"]


def test_cancelled_translation_job_is_persisted_and_cleaned_up() -> None:
    store = RecordingTranslationJobStore()
    counter = QueueCounter()
    cancelled_future: Future[Any] = Future()
    assert cancelled_future.cancel() is True
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        publisher=DummyPublisher(),
        queue_counter=counter,
        job_error_store=JobErrorStore(redis_client=FakeRedis()),
        task_runner=lambda _task: cancelled_future,
        translation_job_store=store,
    )

    pending = service.enqueue_translation_job("en", "hello")

    finished = service.get_translation_job("en", pending["job_id"])
    assert pending["status"] == "pending"
    assert finished["status"] == "error"
    assert finished["stage"] == "failed"
    assert finished["error"] == "Translation job was cancelled before it started."
    assert counter.get() == 0
    assert service.health_status()["available_job_slots"] == 25


def test_page_checker_settings_are_read_updated_and_canonicalised() -> None:
    """Service settings methods use the injected authoritative store."""
    settings_store = PageCheckerSettingsStore(redis_client=FakeRedis())
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        page_checker_settings_store=settings_store,
    )

    assert service.get_page_checker_settings() == {
        "watched_users": ["Bot-Jagwar"],
        "check_probability": 10,
        "cooldown_seconds": 5,
        "ignored_edit_summaries": [
            "fanitsiana famaritana",
            "Dikanteny: es",
        ],
        "job_history_limit": 2500,
        "autonomous_agent_enabled": False,
        "translation_prefilter_enabled": False,
    }
    settings_store.set_autonomous_agent_enabled(True)

    updated = service.update_page_checker_settings(
        {
            "watched_users": [" Bot_Jagwar ", "bot Jagwar", "Alice"],
            "check_probability": 35.5,
            "cooldown_seconds": 0,
            "ignored_edit_summaries": [" skip ", "skip", "Dikanteny: de"],
        }
    )

    assert updated == {
        "watched_users": ["Bot_Jagwar", "Alice"],
        "check_probability": 35.5,
        "cooldown_seconds": 0,
        "ignored_edit_summaries": ["skip", "Dikanteny: de"],
    }
    assert service.get_page_checker_settings() == {
        **updated,
        "job_history_limit": 2500,
        "autonomous_agent_enabled": True,
        "translation_prefilter_enabled": False,
    }

    assert service.update_page_check_job_history_limit({"limit": 7500}) == {
        "job_history_limit": 7500
    }
    assert service.get_page_checker_settings()["job_history_limit"] == 7500


def test_page_checker_settings_validation_maps_to_stable_400_error() -> None:
    """Invalid update payloads become a stable public client error."""
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        page_checker_settings_store=PageCheckerSettingsStore(
            redis_client=FakeRedis()
        ),
    )

    with pytest.raises(ServiceError) as exc:
        service.update_page_checker_settings(
            {
                "watched_users": ["Bot-Jagwar"],
                "check_probability": True,
                "cooldown_seconds": 5,
                "ignored_edit_summaries": [],
            }
        )

    assert exc.value.status_code == 400
    assert exc.value.message == "Invalid page checker settings."

    for invalid_limit in (True, 0, 1.5, 100_001):
        with pytest.raises(ServiceError) as history_error:
            service.update_page_check_job_history_limit({"limit": invalid_limit})
        assert history_error.value.status_code == 400
        assert history_error.value.message == "Invalid job history limit."


def test_page_checker_settings_store_failures_map_to_stable_503_error() -> None:
    """Read and write failures remain authoritative and have no local fallback."""
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        page_checker_settings_store=PageCheckerSettingsStore(
            redis_client=FailingRedis()
        ),
    )

    with pytest.raises(ServiceError) as get_error:
        service.get_page_checker_settings()
    with pytest.raises(ServiceError) as update_error:
        service.update_page_checker_settings(
            {
                "watched_users": [],
                "check_probability": 10,
                "cooldown_seconds": 5,
                "ignored_edit_summaries": [],
            }
        )
    with pytest.raises(ServiceError) as autonomy_error:
        service.update_page_checker_autonomous_agent({"enabled": True})
    with pytest.raises(ServiceError) as history_error:
        service.update_page_check_job_history_limit({"limit": 2500})
    with pytest.raises(ServiceError) as prefilter_error:
        service.update_translation_prefilter({"enabled": True})

    for error in (
        get_error.value,
        update_error.value,
        autonomy_error.value,
        history_error.value,
        prefilter_error.value,
    ):
        assert error.status_code == 503
        assert error.message == "Page checker settings are temporarily unavailable."


def test_page_checker_autonomous_agent_updates_only_its_flag() -> None:
    """The dedicated service mutation preserves monitoring settings."""
    settings_store = PageCheckerSettingsStore(redis_client=FakeRedis())
    settings_store.set_monitoring(PageCheckerSettings(check_probability=35))
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        page_checker_settings_store=settings_store,
    )

    assert service.update_page_checker_autonomous_agent({"enabled": True}) == {
        "autonomous_agent_enabled": True
    }
    assert service.get_page_checker_settings()["check_probability"] == 35
    assert service.get_page_checker_settings()["autonomous_agent_enabled"] is True

    with pytest.raises(ServiceError) as error:
        service.update_page_checker_autonomous_agent({"enabled": 1})
    assert error.value.status_code == 400
    assert error.value.message == "Invalid autonomous agent setting."


def test_translation_prefilter_updates_only_its_flag() -> None:
    """The dedicated prefilter mutation preserves monitoring settings."""
    settings_store = PageCheckerSettingsStore(redis_client=FakeRedis())
    settings_store.set_monitoring(PageCheckerSettings(check_probability=35))
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        page_checker_settings_store=settings_store,
    )

    assert service.update_translation_prefilter({"enabled": True}) == {
        "translation_prefilter_enabled": True
    }
    settings = service.get_page_checker_settings()
    assert settings["check_probability"] == 35
    assert settings["translation_prefilter_enabled"] is True

    with pytest.raises(ServiceError) as error:
        service.update_translation_prefilter({"enabled": 1})
    assert error.value.status_code == 400
    assert error.value.message == "Invalid translation prefilter setting."


def test_definition_translation_settings_are_read_and_updated() -> None:
    """Service methods expose both authoritative definition-translation settings."""
    settings_store = DefinitionTranslationSettingsStore(redis_client=FakeRedis())
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        definition_translation_settings_store=settings_store,
    )

    assert service.get_definition_translation_settings() == {
        "basic_english_gate_enabled": False,
        "nllb_roundtrip_validation_enabled": True,
    }
    assert service.update_definition_translation_settings(
        {
            "basic_english_gate_enabled": True,
            "nllb_roundtrip_validation_enabled": False,
        }
    ) == {
        "basic_english_gate_enabled": True,
        "nllb_roundtrip_validation_enabled": False,
    }
    assert service.get_definition_translation_settings() == {
        "basic_english_gate_enabled": True,
        "nllb_roundtrip_validation_enabled": False,
    }

    assert service.update_definition_translation_settings(
        {"basic_english_gate_enabled": False}
    ) == {
        "basic_english_gate_enabled": False,
        "nllb_roundtrip_validation_enabled": False,
    }

    with pytest.raises(ServiceError) as error:
        service.update_definition_translation_settings(
            {"basic_english_gate_enabled": 1}
        )
    assert error.value.status_code == 400
    assert error.value.message == "Invalid definition translation settings."


def test_definition_translation_settings_store_failure_is_503() -> None:
    """Definition settings remain unavailable rather than using a local fallback."""
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        definition_translation_settings_store=DefinitionTranslationSettingsStore(
            redis_client=FailingRedis()
        ),
    )

    with pytest.raises(ServiceError) as error:
        service.get_definition_translation_settings()
    assert error.value.status_code == 503
    assert error.value.message == "Definition translation settings are temporarily unavailable."


def test_check_pages_injects_the_page_check_publisher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A lazily built page checker receives its dedicated queue publisher."""
    publisher = object()
    captured: Dict[str, Any] = {}

    class FakePageCheckService:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

        def check_pages(
            self,
            language: str,
            titles: List[str],
            on_progress: Optional[Callable[[float], None]] = None,
        ) -> List[Dict[str, Any]]:
            return [{"word": titles[0], "status": "good", "message": language}]

    monkeypatch.setattr(service_module, "PageCheckService", FakePageCheckService)
    settings_store = DefinitionTranslationSettingsStore(redis_client=FakeRedis())
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        page_check_publisher=publisher,  # type: ignore[arg-type]
        task_runner=lambda task: task(),
        definition_translation_settings_store=settings_store,
    )

    assert service.check_pages("mg", ["alika"]) == [
        {"word": "alika", "status": "good", "message": "mg"}
    ]
    assert captured["publisher"] is publisher
    assert captured["nllb_roundtrip_validation_enabled"]() is True
    settings_store.set(
        DefinitionTranslationSettings(nllb_roundtrip_validation_enabled=False)
    )
    assert captured["nllb_roundtrip_validation_enabled"]() is False


def test_enqueue_page_check_creates_one_job_per_title() -> None:
    def run_immediately(task: Callable[[], None]):
        task()

    class FakePageCheckService:
        def check_pages(
            self,
            language: str,
            titles: List[str],
            on_progress: Optional[Callable[[float], None]] = None,
            publication_guard: Optional[Callable[[], None]] = None,
        ) -> List[Dict[str, Any]]:
            del publication_guard
            if on_progress:
                on_progress(1.0)
            return [
                {"word": title, "status": "good", "message": "ok"}
                for title in titles
            ]

    service = EntryTranslatorService(
        translation=DummyTranslation(),
        page_check_service=FakePageCheckService(),
        task_runner=run_immediately,
        check_job_store=RedisCheckJobStore(redis_client=FakeRedis()),
    )

    result = service.enqueue_page_check("mg", ["alika", "soa"])

    jobs = result["jobs"]
    assert len(jobs) == 2
    assert [job["titles"] for job in jobs] == [["alika"], ["soa"]]
    assert all(job["status"] in ("pending", "done") for job in jobs)
    for job in jobs:
        finished = service.get_page_check_job(job["job_id"])
        assert finished["status"] == "done"
        assert finished["progress"] == 100
        assert [entry["word"] for entry in finished["results"]] == job["titles"]
        assert finished["error"] is None


def test_stale_page_check_is_fenced_at_publication_boundary() -> None:
    """A recovered worker cannot publish after its last progress update."""
    store = RedisCheckJobStore(redis_client=FakeRedis())

    class PublishingPageCheckService:
        published = False

        def check_pages(
            self,
            _language: str,
            _titles: List[str],
            on_progress: Optional[Callable[[float], None]] = None,
            publication_guard: Optional[Callable[[], None]] = None,
        ) -> List[Dict[str, Any]]:
            del on_progress
            current = store.all()[0]
            assert store.claim_stale_job(
                current["job_id"],
                current["last_updated_at"],
                current["last_updated_at"] + 901,
                900,
                "replacement-worker",
            ) is not None
            assert publication_guard is not None
            publication_guard()
            self.published = True
            return []

    page_check_service = PublishingPageCheckService()
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        page_check_service=page_check_service,
        task_runner=lambda task: task(),
        check_job_store=store,
    )

    submitted = service.enqueue_page_check("mg", ["alika"])
    stored = store.get(submitted["jobs"][0]["job_id"])

    assert page_check_service.published is False
    assert stored is not None
    assert stored["status"] == "pending"
    assert stored["execution_token"] == "replacement-worker"


def test_enqueue_page_check_records_exception() -> None:
    def run_immediately(task: Callable[[], None]):
        task()

    class FailingPageCheckService:
        def check_pages(
            self,
            language: str,
            titles: List[str],
            on_progress: Optional[Callable[[float], None]] = None,
            publication_guard: Optional[Callable[[], None]] = None,
        ) -> List[Dict[str, Any]]:
            del publication_guard
            raise RuntimeError("boom")

    review_queue = DummyReviewQueue()
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        page_check_service=FailingPageCheckService(),
        task_runner=run_immediately,
        check_job_store=RedisCheckJobStore(redis_client=FakeRedis()),
        page_check_review_queue=review_queue,  # type: ignore[arg-type]
    )

    result = service.enqueue_page_check("mg", ["alika"])

    job = service.get_page_check_job(result["jobs"][0]["job_id"])
    assert job["status"] == "error"
    assert job["error"] == "boom"
    assert job["review_queue_state"] == "queued"
    assert review_queue.jobs[0]["outcome"] == "error"


def test_unverifiable_page_check_is_queued_for_manual_review() -> None:
    """Terminal uncheckable evidence is sent once to the dedicated review queue."""

    class UnverifiablePageCheckService:
        def check_pages(
            self,
            language: str,
            titles: List[str],
            on_progress: Optional[Callable[[float], None]] = None,
            publication_guard: Optional[Callable[[], None]] = None,
        ) -> List[Dict[str, Any]]:
            del publication_guard
            return [
                {
                    "word": titles[0],
                    "status": "unverifiable",
                    "message": f"No source for {language}.",
                    "source_language": "en",
                    "source_title": "dog",
                    "issues": [],
                    "mg_entry": None,
                }
            ]

    review_queue = DummyReviewQueue()
    store = RedisCheckJobStore(redis_client=FakeRedis())
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        page_check_service=UnverifiablePageCheckService(),
        task_runner=lambda task: task(),
        check_job_store=store,
        page_check_review_queue=review_queue,  # type: ignore[arg-type]
    )

    submitted = service.enqueue_page_check("mg", ["alika"])
    job = service.get_page_check_job(submitted["jobs"][0]["job_id"])

    assert job["status"] == "done"
    assert job["review_queue_state"] == "queued"
    assert job["review_event_id"] == f"page-check:{job['job_id']}"
    assert job["review_queue_error"] is None
    assert len(review_queue.jobs) == 1
    assert review_queue.jobs[0]["outcome"] == "unverifiable"


def test_non_malagasy_page_check_is_not_added_to_review_queue() -> None:
    class UnverifiablePageCheckService:
        @staticmethod
        def check_pages(
            _language: str,
            titles: List[str],
            on_progress: Optional[Callable[[float], None]] = None,
            publication_guard: Optional[Callable[[], None]] = None,
        ) -> List[Dict[str, Any]]:
            del on_progress, publication_guard
            return [{"word": titles[0], "status": "unverifiable"}]

    review_queue = DummyReviewQueue()
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        page_check_service=UnverifiablePageCheckService(),
        task_runner=lambda task: task(),
        check_job_store=RedisCheckJobStore(redis_client=FakeRedis()),
        page_check_review_queue=review_queue,  # type: ignore[arg-type]
    )

    submitted = service.enqueue_page_check("en", ["dog"])
    job = service.get_page_check_job(submitted["jobs"][0]["job_id"])

    assert job["review_queue_state"] == "not_needed"
    assert review_queue.jobs == []


def test_malformed_terminal_result_is_not_retried_forever() -> None:
    class MalformedPageCheckService:
        @staticmethod
        def check_pages(
            _language: str,
            _titles: List[str],
            on_progress: Optional[Callable[[float], None]] = None,
            publication_guard: Optional[Callable[[], None]] = None,
        ) -> List[Dict[str, Any]]:
            del on_progress, publication_guard
            return []

    review_queue = DummyReviewQueue()
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        page_check_service=MalformedPageCheckService(),
        task_runner=lambda task: task(),
        check_job_store=RedisCheckJobStore(redis_client=FakeRedis()),
        page_check_review_queue=review_queue,  # type: ignore[arg-type]
    )

    submitted = service.enqueue_page_check("mg", ["alika"])
    job = service.get_page_check_job(submitted["jobs"][0]["job_id"])

    assert job["review_queue_state"] == "invalid"
    assert "exactly one result" in job["review_queue_error"]
    assert review_queue.jobs == []


def test_malformed_persisted_review_event_becomes_invalid() -> None:
    """Deterministic evidence corruption cannot consume retry capacity forever."""
    store = RedisCheckJobStore(redis_client=FakeRedis())
    job = {
        "job_id": "malformed-review",
        "language": "mg",
        "titles": ["alika"],
        "status": "error",
        "created_at": 1.0,
        "last_updated_at": 2.0,
        "attempts": 0,
        "progress": 100,
        "results": None,
        "error": "worker failed",
        "review_queue_state": "pending",
        "review_event_id": "page-check:malformed-review",
        "review_queue_error": None,
    }
    message = service_module.build_page_check_review_message(job, queued_at=2.0)
    message["issues"] = {}
    job["review_message"] = message
    store.put_many([job])
    review_queue = DummyReviewQueue()
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        task_runner=lambda task: task(),
        check_job_store=store,
        page_check_review_queue=review_queue,  # type: ignore[arg-type]
    )

    service._publish_page_check_review(  # pylint: disable=protected-access
        store.get("malformed-review")
    )

    stored = store.get("malformed-review")
    assert stored is not None
    assert stored["review_queue_state"] == "invalid"
    assert "invalid" in stored["review_queue_error"]
    assert review_queue.jobs == []


def test_review_queue_failure_does_not_change_page_check_outcome(
    monkeypatch: Any,
) -> None:
    """RabbitMQ failure is visible without replacing the authoritative check result."""

    class UnverifiablePageCheckService:
        def check_pages(
            self,
            _language: str,
            titles: List[str],
            on_progress: Optional[Callable[[float], None]] = None,
            publication_guard: Optional[Callable[[], None]] = None,
        ) -> List[Dict[str, Any]]:
            del publication_guard
            return [
                {
                    "word": titles[0],
                    "status": "unverifiable",
                    "message": "No source.",
                }
            ]

    now = [100.0]
    monkeypatch.setattr(service_module.time, "time", lambda: now[0])
    review_queue = DummyReviewQueue(
        PageCheckReviewQueueError("review broker unavailable")
    )
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        page_check_service=UnverifiablePageCheckService(),
        task_runner=lambda task: task(),
        check_job_store=RedisCheckJobStore(redis_client=FakeRedis()),
        page_check_review_queue=review_queue,  # type: ignore[arg-type]
    )

    submitted = service.enqueue_page_check("mg", ["alika"])
    job = service.get_page_check_job(submitted["jobs"][0]["job_id"])

    assert job["status"] == "done"
    assert job["results"][0]["status"] == "unverifiable"
    assert job["review_queue_state"] == "failed"
    assert job["review_queue_error"] == "review broker unavailable"

    review_queue.error = None
    now[0] += 6
    service._recover_stale_check_jobs()  # pylint: disable=protected-access
    retried = service.get_page_check_job(job["job_id"])

    assert retried["review_queue_state"] == "queued"
    assert retried["review_queue_error"] is None
    assert len(review_queue.jobs) == 1


def test_unexpected_review_transport_failure_is_isolated() -> None:
    class UnverifiablePageCheckService:
        @staticmethod
        def check_pages(
            _language: str,
            titles: List[str],
            on_progress: Optional[Callable[[float], None]] = None,
            publication_guard: Optional[Callable[[], None]] = None,
        ) -> List[Dict[str, Any]]:
            del on_progress, publication_guard
            return [{"word": titles[0], "status": "unverifiable"}]

    service = EntryTranslatorService(
        translation=DummyTranslation(),
        page_check_service=UnverifiablePageCheckService(),
        task_runner=lambda task: task(),
        check_job_store=RedisCheckJobStore(redis_client=FakeRedis()),
        page_check_review_queue=DummyReviewQueue(  # type: ignore[arg-type]
            RuntimeError("unexpected")
        ),
    )

    submitted = service.enqueue_page_check("mg", ["alika"])
    job = service.get_page_check_job(submitted["jobs"][0]["job_id"])

    assert job["status"] == "done"
    assert job["review_queue_state"] == "failed"
    assert (
        job["review_queue_error"]
        == "Unexpected review transport failure: RuntimeError"
    )


def test_recovery_publishes_pending_review_left_by_interrupted_worker() -> None:
    """A crash after terminal persistence cannot strand a pending handoff."""
    store = RedisCheckJobStore(redis_client=FakeRedis())
    job = {
        "job_id": "interrupted-review",
        "language": "mg",
        "titles": ["alika"],
        "status": "done",
        "created_at": time.time(),
        "last_updated_at": time.time(),
        "attempts": 0,
        "progress": 100,
        "results": [
            {
                "word": "alika",
                "status": "unverifiable",
                "message": "No source.",
            }
        ],
        "error": None,
        "review_queue_state": "pending",
        "review_event_id": "page-check:interrupted-review",
        "review_queue_error": None,
    }
    store.put_many([job])
    review_queue = DummyReviewQueue()
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        task_runner=lambda task: task(),
        check_job_store=store,
        page_check_review_queue=review_queue,  # type: ignore[arg-type]
    )

    service._recover_stale_check_jobs()  # pylint: disable=protected-access

    recovered = store.get("interrupted-review")
    assert recovered["review_queue_state"] == "queued"
    assert len(review_queue.jobs) == 1


def test_shared_review_handoff_is_published_by_only_one_service() -> None:
    """The Redis lease prevents duplicate publication across translator processes."""
    store = RedisCheckJobStore(redis_client=FakeRedis())
    job = {
        "job_id": "shared-review",
        "language": "mg",
        "titles": ["alika"],
        "status": "error",
        "created_at": time.time(),
        "last_updated_at": time.time(),
        "attempts": 0,
        "progress": 0,
        "results": None,
        "error": "worker stopped",
        "review_queue_state": "pending",
        "review_event_id": "page-check:shared-review",
        "review_queue_error": None,
    }
    store.put_many([job])
    review_queue = DummyReviewQueue()
    first = EntryTranslatorService(
        translation=DummyTranslation(),
        task_runner=lambda task: task(),
        check_job_store=store,
        page_check_review_queue=review_queue,  # type: ignore[arg-type]
    )
    second = EntryTranslatorService(
        translation=DummyTranslation(),
        task_runner=lambda task: task(),
        check_job_store=store,
        page_check_review_queue=review_queue,  # type: ignore[arg-type]
    )
    first_snapshot = store.get("shared-review")
    second_snapshot = store.get("shared-review")

    assert first_snapshot is not None
    assert second_snapshot is not None
    first._publish_page_check_review(first_snapshot)  # pylint: disable=protected-access
    second._publish_page_check_review(second_snapshot)  # pylint: disable=protected-access

    assert len(review_queue.jobs) == 1
    assert store.get("shared-review")["review_queue_state"] == "queued"


def test_review_handoff_keeps_first_event_and_live_lease() -> None:
    """A late ordinary job write cannot replace evidence or erase its publisher."""
    store = RedisCheckJobStore(redis_client=FakeRedis())
    job = {
        "job_id": "immutable-review",
        "language": "mg",
        "titles": ["alika"],
        "status": "error",
        "created_at": 1.0,
        "last_updated_at": 2.0,
        "attempts": 0,
        "progress": 0,
        "results": None,
        "error": "first failure",
        "review_queue_state": "pending",
        "review_event_id": "page-check:immutable-review",
        "review_queue_error": None,
    }
    job["review_message"] = service_module.build_page_check_review_message(
        job, queued_at=2.0
    )
    store.put_many([job])
    claimed = store.claim_review_handoff(
        "immutable-review", "publisher", 3.0, 120.0
    )
    assert claimed is not None

    late_worker = {
        **job,
        "error": "different failure",
        "review_queue_state": "pending",
        "review_message": service_module.build_page_check_review_message(
            {**job, "error": "different failure"}, queued_at=4.0
        ),
    }
    store.put(late_worker)

    stored = store.get("immutable-review")
    assert stored is not None
    assert stored["review_queue_state"] == "publishing"
    assert stored["review_queue_claim"] == "publisher"
    assert stored["review_message"]["message"] == "first failure"
    assert store.finish_review_handoff(
        "immutable-review",
        "publisher",
        "queued",
        "page-check:immutable-review",
        None,
    )


def test_enqueue_page_check_records_task_submission_failure() -> None:
    def fail_to_submit(_task: Callable[[], None]) -> None:
        raise RuntimeError("executor unavailable")

    store = RedisCheckJobStore(redis_client=FakeRedis())
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        task_runner=fail_to_submit,
        check_job_store=store,
    )

    result = service.enqueue_page_check("mg", ["alika"])

    job = store.get(result["jobs"][0]["job_id"])
    assert job["status"] == "error"
    assert job["error"] == "The page check job could not be started."


def test_enqueue_page_check_rejects_when_store_is_full() -> None:
    store = RedisCheckJobStore(redis_client=FakeRedis())
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        check_job_store=store,
    )

    now = time.time()
    for index in range(service._MAX_UNFINISHED_CHECK_JOBS):
        job_id = f"pending-{index}"
        store.put_many(
            [
                {
                    "job_id": job_id,
                    "language": "mg",
                    "titles": [f"title-{index}"],
                    "status": "pending",
                    "created_at": now,
                    "last_updated_at": now,
                    "attempts": 0,
                    "progress": 0,
                    "results": None,
                    "error": None,
                }
            ]
        )

    with pytest.raises(ServiceError) as exc:
        service.enqueue_page_check("mg", ["alika"])

    assert exc.value.status_code == 503


def test_enqueue_page_check_uses_configured_job_retention_limit() -> None:
    store = RedisCheckJobStore(redis_client=FakeRedis())
    store.put_many(
        [
            {
                "job_id": f"completed-{index}",
                "language": "mg",
                "titles": [f"title-{index}"],
                "status": "done",
                "created_at": float(index),
                "last_updated_at": float(index),
                "attempts": 0,
                "progress": 100,
                "results": [{"status": "good"}],
                "error": None,
            }
            for index in range(3)
        ]
    )
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        task_runner=lambda _task: None,
        check_job_store=store,
        max_check_jobs_kept=3,
    )

    result = service.enqueue_page_check("mg", ["new-page"])

    retained = store.all()
    assert len(retained) == 3
    assert store.get("completed-0") is None
    assert store.get(result["jobs"][0]["job_id"]) is not None


def test_page_check_retention_preserves_unfinished_review_handoff() -> None:
    store = RedisCheckJobStore(redis_client=FakeRedis())
    base_job = {
        "language": "mg",
        "titles": ["alika"],
        "status": "done",
        "last_updated_at": 1.0,
        "attempts": 0,
        "progress": 100,
        "results": [{"status": "unverifiable"}],
        "error": None,
    }
    store.put_many(
        [
            {
                **base_job,
                "job_id": "review-pending",
                "created_at": 0.0,
                "review_queue_state": "pending",
            },
            {
                **base_job,
                "job_id": "removable",
                "created_at": 1.0,
                "review_queue_state": "queued",
            },
        ]
    )
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        task_runner=lambda _task: None,
        check_job_store=store,
        max_check_jobs_kept=2,
    )

    service.enqueue_page_check("mg", ["new-page"])

    assert store.get("review-pending") is not None


def test_page_check_capacity_rejects_when_only_unresolved_reviews_remain() -> None:
    store = RedisCheckJobStore(redis_client=FakeRedis())
    store.put_many(
        [{
            "job_id": "review-pending",
            "language": "mg",
            "titles": ["alika"],
            "status": "done",
            "created_at": 0.0,
            "last_updated_at": 1.0,
            "attempts": 0,
            "progress": 100,
            "results": [{"status": "unverifiable"}],
            "error": None,
            "review_queue_state": "pending",
        }]
    )
    incoming = {
        "job_id": "new-job",
        "language": "mg",
        "titles": ["saka"],
        "status": "pending",
        "created_at": 2.0,
        "last_updated_at": 2.0,
        "attempts": 0,
        "progress": 0,
        "results": None,
        "error": None,
    }

    assert store.put_many_bounded([incoming], 1, 100) is False
    assert store.get("new-job") is None


def test_remove_terminal_rechecks_review_state_atomically() -> None:
    store = RedisCheckJobStore(redis_client=FakeRedis())
    job = {
        "job_id": "terminal",
        "language": "mg",
        "titles": ["alika"],
        "status": "done",
        "created_at": 0.0,
        "last_updated_at": 1.0,
        "attempts": 0,
        "progress": 100,
        "results": [{"status": "good"}],
        "error": None,
        "review_queue_state": "not_needed",
    }
    store.put_many(
        [
            job,
            {
                **job,
                "job_id": "removable",
                "created_at": 1.0,
            },
        ]
    )
    stored = store.get("terminal")
    assert stored is not None
    stored["review_queue_state"] = "pending"
    store.put(stored)

    assert store.remove_terminal("terminal") is False
    assert store.get("terminal") is not None
    assert store.remove_terminal("removable") is True
    assert store.get("removable") is None


def test_bounded_check_job_write_enforces_shared_unfinished_capacity() -> None:
    redis_client = FakeRedis()

    def submit_batch(batch: int) -> bool:
        store = RedisCheckJobStore(redis_client=redis_client)
        jobs = [
            {
                "job_id": f"batch-{batch}-job-{index}",
                "language": "mg",
                "titles": [f"title-{batch}-{index}"],
                "status": "pending",
                "created_at": float(batch),
                "last_updated_at": float(batch),
                "attempts": 0,
                "progress": 0,
                "results": None,
                "error": None,
            }
            for index in range(100)
        ]
        return store.put_many_bounded(jobs, 200, 100)

    with ThreadPoolExecutor(max_workers=3) as executor:
        accepted = list(executor.map(submit_batch, range(3)))

    assert accepted.count(True) == 1
    assert accepted.count(False) == 2
    assert redis_client.hlen("botjagwar:entry_translator:page_check_jobs") == 100


def test_get_page_check_job_unknown() -> None:
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        check_job_store=RedisCheckJobStore(redis_client=FakeRedis()),
    )

    with pytest.raises(ServiceError) as exc:
        service.get_page_check_job("missing")

    assert exc.value.status_code == 404


def test_list_page_check_jobs_summarises_and_filters() -> None:
    def run_immediately(task: Callable[[], None]):
        task()

    class StubPageCheckService:
        def check_pages(
            self,
            language: str,
            titles: List[str],
            on_progress: Optional[Callable[[float], None]] = None,
            publication_guard: Optional[Callable[[], None]] = None,
        ) -> List[Dict[str, Any]]:
            del publication_guard
            statuses = {"a": "good", "b": "fixed", "c": "unverifiable", "d": "error"}
            return [
                {"word": title, "status": statuses.get(title, "good")}
                for title in titles
            ]

    service = EntryTranslatorService(
        translation=DummyTranslation(),
        page_check_service=StubPageCheckService(),
        task_runner=run_immediately,
        check_job_store=RedisCheckJobStore(redis_client=FakeRedis()),
        page_checker_settings_store=PageCheckerSettingsStore(redis_client=FakeRedis()),
    )

    first = service.enqueue_page_check("mg", ["a", "b", "c", "d"])
    second = service.enqueue_page_check("en", ["x"])

    jobs = service.list_page_check_jobs(language="mg")
    assert len(jobs) == 4
    assert {job["titles"][0] for job in jobs} == {"a", "b", "c", "d"}
    by_title = {job["titles"][0]: job for job in jobs}
    assert by_title["a"]["result_counts"] == {"good": 1, "fixed": 0, "unverifiable": 0, "error": 0}
    assert by_title["b"]["result_counts"] == {"good": 0, "fixed": 1, "unverifiable": 0, "error": 0}
    assert by_title["c"]["result_counts"] == {"good": 0, "fixed": 0, "unverifiable": 1, "error": 0}
    assert by_title["d"]["result_counts"] == {"good": 0, "fixed": 0, "unverifiable": 0, "error": 1}

    all_jobs = service.list_page_check_jobs(limit=5)
    assert len(all_jobs) == 5
    assert all_jobs[0]["job_id"] == second["jobs"][0]["job_id"]
    assert all_jobs[0]["progress"] == 100
    assert {job["job_id"] for job in all_jobs} == {
        job["job_id"] for batch in (first, second) for job in batch["jobs"]
    }


def test_list_page_check_jobs_uses_configured_history_without_trimming() -> None:
    """Atlas history is capped independently from the physical Redis store."""
    store = RedisCheckJobStore(redis_client=FakeRedis())
    jobs = [
        {
            "job_id": f"job-{index}",
            "language": "mg",
            "titles": [f"title-{index}"],
            "status": "done",
            "created_at": float(index),
            "last_updated_at": float(index),
            "attempts": 0,
            "progress": 100,
            "results": [],
            "error": None,
        }
        for index in range(3)
    ]
    store.put_many(jobs)
    settings_store = PageCheckerSettingsStore(redis_client=FakeRedis())
    settings_store.set_job_history_limit(2)
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        check_job_store=store,
        page_checker_settings_store=settings_store,
    )

    assert [job["job_id"] for job in service.list_page_check_jobs(limit=10)] == [
        "job-2",
        "job-1",
    ]
    assert len(store.all()) == 3


def test_page_check_list_reports_waiting_order_and_current_stage() -> None:
    store = RedisCheckJobStore(redis_client=FakeRedis())
    store.put_many(
        [
            {
                "job_id": "second",
                "language": "mg",
                "titles": ["soa"],
                "status": "pending",
                "created_at": 2.0,
                "last_updated_at": 2.0,
                "attempts": 0,
                "progress": 0,
                "results": None,
                "error": None,
                "stage": "queued",
                "message": "Waiting for a page-check worker.",
                "timeline": [],
            },
            {
                "job_id": "first",
                "language": "mg",
                "titles": ["alika"],
                "status": "pending",
                "created_at": 1.0,
                "last_updated_at": 1.0,
                "attempts": 0,
                "progress": 0,
                "results": None,
                "error": None,
                "stage": "queued",
                "message": "Waiting for a page-check worker.",
                "timeline": [],
            },
            {
                "job_id": "running",
                "language": "mg",
                "titles": ["trano"],
                "status": "running",
                "created_at": 3.0,
                "last_updated_at": 4.0,
                "attempts": 0,
                "progress": 55,
                "results": None,
                "error": None,
                "stage": "verifying",
                "message": "Comparing definitions.",
                "timeline": [],
            },
        ]
    )
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        task_runner=lambda _task: None,
        check_job_store=store,
        page_checker_settings_store=PageCheckerSettingsStore(redis_client=FakeRedis()),
    )

    jobs = service.list_page_check_jobs(language="mg")
    by_id = {job["job_id"]: job for job in jobs}

    assert by_id["first"]["queue_position"] == 1
    assert by_id["second"]["queue_position"] == 2
    assert by_id["running"]["queue_position"] is None
    assert by_id["running"]["stage"] == "verifying"
    assert by_id["running"]["message"] == "Comparing definitions."


def test_page_check_status_reads_do_not_run_recovery_inline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = RedisCheckJobStore(redis_client=FakeRedis())
    store.put_many(
        [{
            "job_id": "job-1",
            "language": "mg",
            "titles": ["alika"],
            "status": "pending",
            "created_at": 1.0,
            "last_updated_at": 1.0,
            "attempts": 0,
            "progress": 0,
            "results": None,
            "error": None,
        }]
    )
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        task_runner=lambda _task: None,
        check_job_store=store,
        page_checker_settings_store=PageCheckerSettingsStore(redis_client=FakeRedis()),
    )
    monkeypatch.setattr(
        service,
        "_maybe_recover_stale_check_jobs",
        lambda: pytest.fail("status reads must not recover jobs inline"),
    )

    assert service.get_page_check_job("job-1")["status"] == "pending"
    assert service.list_page_check_jobs(language="mg")[0]["job_id"] == "job-1"


def test_scheduled_page_check_recovery_is_single_flight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tasks: List[Callable[[], None]] = []

    class CapturingExecutor:
        @staticmethod
        def submit(task: Callable[[], None]) -> None:
            tasks.append(task)

    service = EntryTranslatorService(
        translation=DummyTranslation(),
        task_runner=lambda _task: None,
    )
    service._check_executor = CapturingExecutor()  # type: ignore[assignment]  # pylint: disable=protected-access
    recovered: List[None] = []
    monkeypatch.setattr(
        service,
        "_recover_stale_check_jobs",
        lambda: recovered.append(None),
    )

    service._schedule_stale_check_recovery()  # pylint: disable=protected-access
    service._last_check_recovery = 0  # pylint: disable=protected-access
    service._schedule_stale_check_recovery()  # pylint: disable=protected-access

    assert len(tasks) == 1
    tasks[0]()
    assert recovered == [None]

    service._last_check_recovery = 0  # pylint: disable=protected-access
    service._schedule_stale_check_recovery()  # pylint: disable=protected-access
    assert len(tasks) == 2


def test_review_handoff_recovery_is_batch_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    jobs = [
        {
            "job_id": f"review-{index}",
            "status": "done",
            "last_updated_at": 0.0,
            "review_queue_state": "failed",
        }
        for index in range(25)
    ]
    store = SimpleNamespace(all=lambda: jobs)
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        task_runner=lambda _task: None,
        check_job_store=store,  # type: ignore[arg-type]
    )
    published: List[str] = []
    monkeypatch.setattr(
        service,
        "_publish_page_check_review",
        lambda job: published.append(job["job_id"]),
    )

    service._recover_stale_check_jobs()  # pylint: disable=protected-access

    assert published == [f"review-{index}" for index in range(20)]


def test_review_handoff_recovery_bounds_only_eligible_handoffs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = 1_000.0
    jobs = [
        {
            "job_id": f"backoff-{index}",
            "status": "done",
            "last_updated_at": 0.0,
            "review_queue_state": "failed",
            "review_queue_next_attempt_at": now + 1,
        }
        for index in range(10)
    ]
    jobs.extend(
        {
            "job_id": f"leased-{index}",
            "status": "done",
            "last_updated_at": 0.0,
            "review_queue_state": "publishing",
            "review_queue_claimed_at": now,
        }
        for index in range(10)
    )
    jobs.extend(
        {
            "job_id": f"eligible-{index}",
            "status": "done",
            "last_updated_at": 0.0,
            "review_queue_state": "pending",
        }
        for index in range(25)
    )
    store = SimpleNamespace(all=lambda: jobs)
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        task_runner=lambda _task: None,
        check_job_store=store,  # type: ignore[arg-type]
    )
    published: List[str] = []
    monkeypatch.setattr(service_module.time, "time", lambda: now)
    monkeypatch.setattr(
        service,
        "_publish_page_check_review",
        lambda job: published.append(job["job_id"]),
    )

    service._recover_stale_check_jobs()  # pylint: disable=protected-access

    assert published == [f"eligible-{index}" for index in range(20)]


def test_page_check_job_records_detailed_stage_timeline() -> None:
    class ProgressPageCheckService:
        def check_pages(
            self,
            language: str,
            titles: List[str],
            on_progress: Optional[Callable[[float], None]] = None,
            publication_guard: Optional[Callable[[], None]] = None,
        ) -> List[Dict[str, Any]]:
            del language, publication_guard
            if on_progress:
                for ratio in (0.01, 0.15, 0.55, 0.94, 0.95, 1.0):
                    on_progress(ratio)
            return [{"word": titles[0], "status": "good", "message": "ok"}]

    service = EntryTranslatorService(
        translation=DummyTranslation(),
        page_check_service=ProgressPageCheckService(),
        task_runner=lambda task: task(),
        check_job_store=RedisCheckJobStore(redis_client=FakeRedis()),
    )

    result = service.enqueue_page_check("mg", ["alika"])
    job = service.get_page_check_job(result["jobs"][0]["job_id"])
    stages = [event["stage"] for event in job["timeline"]]

    assert job["stage"] == "completed"
    assert job["message"] == "Page check completed; the full result is available."
    assert stages == [
        "queued",
        "loading_target",
        "resolving_source",
        "verifying",
        "generating_fix",
        "queueing_publication",
        "finalising",
        "completed",
    ]


def test_stale_check_job_is_relaunched() -> None:
    def run_immediately(task: Callable[[], None]):
        task()

    class StubPageCheckService:
        def check_pages(
            self,
            language: str,
            titles: List[str],
            on_progress: Optional[Callable[[float], None]] = None,
            publication_guard: Optional[Callable[[], None]] = None,
        ) -> List[Dict[str, Any]]:
            del publication_guard
            return [{"word": title, "status": "good", "message": "ok"} for title in titles]

    service = EntryTranslatorService(
        translation=DummyTranslation(),
        page_check_service=StubPageCheckService(),
        task_runner=run_immediately,
        check_job_store=RedisCheckJobStore(redis_client=FakeRedis()),
    )

    result = service.enqueue_page_check("mg", ["alika"])
    job_id = result["jobs"][0]["job_id"]

    job = service._check_job_store.get(job_id)
    job["status"] = "pending"
    job["last_updated_at"] = 0
    job["attempts"] = 0
    service._check_job_store.put(job)

    service._last_check_recovery = 0
    service._maybe_recover_stale_check_jobs()

    job = service.get_page_check_job(job_id)
    assert job["status"] == "done"
    assert job["attempts"] == 1
    assert job["results"] == [{"word": "alika", "status": "good", "message": "ok"}]


def test_stale_check_job_gives_up_after_max_attempts() -> None:
    store = RedisCheckJobStore(redis_client=FakeRedis())
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        check_job_store=store,
    )

    now = time.time()
    job_id = "stale-job"
    store.put_many(
        [{
            "job_id": job_id,
            "language": "mg",
            "titles": ["alika"],
            "status": "running",
            "created_at": now,
            "last_updated_at": 0,
            "attempts": service._CHECK_JOB_MAX_ATTEMPTS,
            "progress": 40,
            "results": None,
            "error": None,
        }]
    )

    service._last_check_recovery = 0
    service._maybe_recover_stale_check_jobs()

    job = service.get_page_check_job(job_id)
    assert job["status"] == "error"
    assert job["attempts"] == service._CHECK_JOB_MAX_ATTEMPTS + 1
    assert "retry limit" in job["error"]


def test_stale_check_job_records_relaunch_failure() -> None:
    def fail_to_submit(_task: Callable[[], None]) -> None:
        raise RuntimeError("executor unavailable")

    store = RedisCheckJobStore(redis_client=FakeRedis())
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        task_runner=fail_to_submit,
        check_job_store=store,
    )
    stale_job = {
        "job_id": "stale-job",
        "language": "mg",
        "titles": ["alika"],
        "status": "running",
        "created_at": 0.0,
        "last_updated_at": 0.0,
        "attempts": 0,
        "progress": 40,
        "results": None,
        "error": None,
    }
    store.put_many([stale_job])

    service._recover_stale_check_jobs()

    job = store.get(stale_job["job_id"])
    assert job["status"] == "error"
    assert job["attempts"] == 1
    assert job["error"] == "The page check job could not be relaunched."


def test_check_jobs_survive_service_restart() -> None:
    def run_immediately(task: Callable[[], None]):
        task()

    class StubPageCheckService:
        def check_pages(
            self,
            language: str,
            titles: List[str],
            on_progress: Optional[Callable[[float], None]] = None,
            publication_guard: Optional[Callable[[], None]] = None,
        ) -> List[Dict[str, Any]]:
            del publication_guard
            return [{"word": title, "status": "good", "message": "ok"} for title in titles]

    redis_client = FakeRedis()
    first_service = EntryTranslatorService(
        translation=DummyTranslation(),
        page_check_service=StubPageCheckService(),
        task_runner=run_immediately,
        check_job_store=RedisCheckJobStore(redis_client=redis_client),
    )

    result = first_service.enqueue_page_check("mg", ["alika", "soa"])
    job_ids = [job["job_id"] for job in result["jobs"]]

    second_service = EntryTranslatorService(
        translation=DummyTranslation(),
        page_check_service=StubPageCheckService(),
        task_runner=run_immediately,
        check_job_store=RedisCheckJobStore(redis_client=redis_client),
        page_checker_settings_store=PageCheckerSettingsStore(redis_client=FakeRedis()),
    )

    jobs = second_service.list_page_check_jobs(limit=5)
    assert {job["job_id"] for job in jobs} == set(job_ids)
    for job_id in job_ids:
        finished = second_service.get_page_check_job(job_id)
        assert finished["status"] == "done"
        assert finished["progress"] == 100
        assert [entry["word"] for entry in finished["results"]] == [finished["titles"][0]]


def test_check_job_store_fails_when_redis_is_unavailable() -> None:
    store = RedisCheckJobStore(redis_client=FailingRedis())
    job = {
        "job_id": "unavailable-job",
        "language": "mg",
        "titles": ["alika"],
        "status": "pending",
        "created_at": 0.0,
        "last_updated_at": 0.0,
        "attempts": 0,
        "progress": 0,
        "results": None,
        "error": None,
    }

    with pytest.raises(CheckJobStoreError):
        store.put(job)
    with pytest.raises(CheckJobStoreError):
        store.put_many([job])
    with pytest.raises(CheckJobStoreError):
        store.put_many_bounded([job], 200, 100)
    with pytest.raises(CheckJobStoreError):
        store.get(job["job_id"])
    with pytest.raises(CheckJobStoreError):
        store.all()
    with pytest.raises(CheckJobStoreError):
        store.remove(job["job_id"])
    with pytest.raises(CheckJobStoreError):
        store.remove_terminal(job["job_id"])
    with pytest.raises(CheckJobStoreError):
        store.claim_review_handoff("job-1", "claim", 1.0, 120.0)
    with pytest.raises(CheckJobStoreError):
        store.claim_stale_job("job-1", 0.0, 1.0, 120.0, "execution")
    with pytest.raises(CheckJobStoreError):
        store.finish_review_handoff(
            "job-1", "claim", "queued", "page-check:job-1", None
        )
    with pytest.raises(CheckJobStoreError):
        store.touch_execution("job-1", "execution", 1.0)


def test_check_job_store_leases_review_handoff_atomically() -> None:
    redis_client = FakeRedis()
    store = RedisCheckJobStore(redis_client=redis_client)
    job = {
        "job_id": "review-job",
        "language": "mg",
        "titles": ["alika"],
        "status": "done",
        "created_at": 1.0,
        "last_updated_at": 2.0,
        "attempts": 0,
        "progress": 100,
        "results": [{"status": "unverifiable", "message": "review"}],
        "error": None,
        "review_queue_state": "pending",
        "review_event_id": "page-check:review-job",
        "review_queue_error": None,
    }
    store.put_many([job])

    first = store.claim_review_handoff("review-job", "owner-1", 10.0, 120.0)
    concurrent = store.claim_review_handoff("review-job", "owner-2", 11.0, 120.0)
    recovered = store.claim_review_handoff("review-job", "owner-2", 131.0, 120.0)

    assert first is not None
    assert recovered is not None
    assert first["review_queue_state"] == "publishing"
    assert first["review_queue_claim"] == "owner-1"
    assert concurrent is None
    assert recovered["review_queue_claim"] == "owner-2"
    assert (
        store.finish_review_handoff(
            "review-job", "owner-1", "queued", "page-check:review-job", None
        )
        is False
    )
    assert store.finish_review_handoff(
        "review-job", "owner-2", "queued", "page-check:review-job", None
    )
    finished = store.get("review-job")
    assert finished["review_queue_state"] == "queued"
    assert finished["review_queue_error"] is None
    assert "review_queue_claim" not in finished


def test_check_job_store_fences_stale_execution_atomically() -> None:
    store = RedisCheckJobStore(redis_client=FakeRedis())
    stale = {
        "job_id": "stale-execution",
        "execution_token": "old-worker",
        "language": "mg",
        "titles": ["alika"],
        "status": "running",
        "created_at": 0.0,
        "last_updated_at": 1.0,
        "attempts": 0,
        "progress": 20,
        "results": None,
        "error": None,
    }
    store.put_many([stale])

    claimed = store.claim_stale_job(
        "stale-execution", 1.0, 1_000.0, 900.0, "new-worker"
    )
    concurrent = store.claim_stale_job(
        "stale-execution", 1.0, 1_000.0, 900.0, "other-worker"
    )
    stale["status"] = "done"
    stale["results"] = [{"status": "unverifiable"}]

    assert claimed is not None
    assert claimed["execution_token"] == "new-worker"
    assert claimed["attempts"] == 1
    assert concurrent is None
    assert store.put(stale) is False
    stored = store.get("stale-execution")
    assert stored is not None
    assert stored["status"] == "pending"
    assert stored["execution_token"] == "new-worker"


def test_check_job_store_preserves_arrays_through_atomic_updates() -> None:
    """Redis mutations must not let Lua reinterpret empty arrays as objects."""
    store = RedisCheckJobStore(redis_client=FakeRedis())
    job = {
        "job_id": "array-job",
        "execution_token": "worker",
        "language": "mg",
        "titles": ["alika"],
        "status": "running",
        "created_at": 0.0,
        "last_updated_at": 1.0,
        "attempts": 0,
        "progress": 20,
        "results": [{"status": "error", "issues": []}],
        "error": None,
        "timeline": [],
        "metadata": {},
    }
    store.put_many([job])

    job["progress"] = 30
    assert store.put(job) is True
    claimed = store.claim_stale_job(
        "array-job", 1.0, 1_000.0, 900.0, "new-worker"
    )

    assert claimed is not None
    assert claimed["results"][0]["issues"] == []
    assert claimed["timeline"] == []
    assert claimed["metadata"] == {}
    assert "cjson" not in RedisCheckJobStore._COMPARE_AND_SET_SCRIPT


def test_review_handoff_preserves_empty_nested_arrays() -> None:
    """Immutable review evidence remains byte-equivalent across lease changes."""
    store = RedisCheckJobStore(redis_client=FakeRedis())
    job = {
        "job_id": "review-arrays",
        "language": "mg",
        "titles": ["alika"],
        "status": "error",
        "created_at": 1.0,
        "last_updated_at": 2.0,
        "attempts": 0,
        "progress": 100,
        "results": None,
        "error": "worker failed",
        "review_queue_state": "pending",
        "review_event_id": "page-check:review-arrays",
        "review_queue_error": None,
    }
    message = service_module.build_page_check_review_message(job, queued_at=2.0)
    message["mg_entry"] = {"definitions": [], "additional_data": {}}
    job["review_message"] = message
    store.put_many([job])

    claimed = store.claim_review_handoff("review-arrays", "owner", 3.0, 120.0)
    assert claimed is not None
    assert claimed["review_message"]["issues"] == []
    assert claimed["review_message"]["mg_entry"]["definitions"] == []
    assert store.finish_review_handoff(
        "review-arrays", "owner", "queued", "page-check:review-arrays", None
    )
    stored = store.get("review-arrays")
    assert stored is not None
    assert stored["review_message"] == message


def test_evicted_job_cannot_be_resurrected_by_stale_execution() -> None:
    """Retention deletion remains a permanent fence for an old worker."""
    store = RedisCheckJobStore(redis_client=FakeRedis())
    old_worker = {
        "job_id": "old-job",
        "execution_token": "old-worker",
        "language": "mg",
        "titles": ["alika"],
        "status": "running",
        "created_at": 0.0,
        "last_updated_at": 1.0,
        "attempts": 0,
        "progress": 20,
        "results": None,
        "error": None,
    }
    store.put_many([old_worker])
    successor = store.claim_stale_job(
        "old-job", 1.0, 1_000.0, 900.0, "new-worker"
    )
    assert successor is not None
    successor.update(
        status="done",
        results=[{"status": "good"}],
        review_queue_state="not_needed",
    )
    assert store.put(successor) is True
    incoming = {
        **successor,
        "job_id": "new-job",
        "execution_token": "current-worker",
        "status": "pending",
        "created_at": 2.0,
        "last_updated_at": 2.0,
        "results": None,
    }
    assert store.put_many_bounded([incoming], 1, 100) is True
    assert store.get("old-job") is None

    old_worker["status"] = "done"
    assert store.put(old_worker) is False
    assert store.get("old-job") is None
    assert len(store.all()) == 1


def test_check_job_store_touch_execution_requires_current_owner() -> None:
    """Publication lease refreshes only for the active execution token."""
    store = RedisCheckJobStore(redis_client=FakeRedis())
    job = {
        "job_id": "touch-job",
        "execution_token": "owner",
        "status": "running",
        "created_at": 1.0,
        "last_updated_at": 1.0,
    }
    store.put_many([job])

    assert store.touch_execution("touch-job", "other", 2.0) is False
    assert store.touch_execution("touch-job", "owner", 3.0) is True
    assert store.get("touch-job")["last_updated_at"] == 3.0
    stored = store.get("touch-job")
    stored["status"] = "done"
    assert store.put(stored) is True
    assert store.touch_execution("touch-job", "owner", 4.0) is False
    assert store.touch_execution("missing", "owner", 4.0) is False


def test_check_job_store_validates_review_handoff_transition() -> None:
    store = RedisCheckJobStore(redis_client=FakeRedis())

    assert store.claim_review_handoff("missing", "owner", 1.0, 120.0) is None
    with pytest.raises(ValueError, match="queued, failed, or invalid"):
        store.finish_review_handoff(
            "missing", "owner", "unexpected", "page-check:missing", None
        )


def test_check_job_store_rejects_invalid_records() -> None:
    redis_client = FakeRedis()
    store = RedisCheckJobStore(redis_client=redis_client, key="check-jobs")

    store.put_many([])
    assert store.put_many_bounded([], 200, 100) is True
    with pytest.raises(CheckJobStoreError):
        store.put({})
    with pytest.raises(CheckJobStoreError):
        store.put({"job_id": ""})

    redis_client.hashes["check-jobs"] = {"bad-json": "{"}
    with pytest.raises(CheckJobStoreError):
        store.get("bad-json")
    with pytest.raises(CheckJobStoreError):
        store.put({"job_id": "bad-json"})
    with pytest.raises(CheckJobStoreError):
        store.claim_stale_job("bad-json", 0.0, 1_000.0, 900.0, "owner")
    with pytest.raises(CheckJobStoreError):
        store.claim_review_handoff("bad-json", "owner", 1.0, 120.0)
    with pytest.raises(CheckJobStoreError):
        store.finish_review_handoff(
            "bad-json", "owner", "queued", "page-check:bad-json", None
        )
    with pytest.raises(CheckJobStoreError):
        store.remove_terminal("bad-json")
    with pytest.raises(CheckJobStoreError):
        store.put_many_bounded([{"job_id": "new-job"}], 200, 100)
    assert store.get("new-job") is None

    redis_client.hashes["check-jobs"] = {"not-an-object": "[]"}
    with pytest.raises(CheckJobStoreError):
        store.all()


def test_check_job_store_normalises_old_records_for_new_clients() -> None:
    redis_client = FakeRedis()
    redis_client.hashes["check-jobs"] = {
        "legacy": json.dumps(
            {
                "language": "mg",
                "titles": ["alika"],
                "status": "running",
                "created_at": 1.0,
                "last_updated_at": 2.0,
                "attempts": 0,
                "progress": 50,
                "results": None,
                "error": None,
            }
        )
    }
    store = RedisCheckJobStore(redis_client=redis_client, key="check-jobs")

    job = store.get("legacy")

    assert job["stage"] == "checking"
    assert job["message"] == "Checking the page against its sources."
    assert job["timeline"] == []


def test_check_job_timeline_is_bounded() -> None:
    job: Dict[str, Any] = {"last_updated_at": 0.0, "timeline": []}

    for index in range(40):
        job["last_updated_at"] = float(index)
        EntryTranslatorService._set_check_job_state(
            job, f"stage-{index}", f"message-{index}"
        )

    assert len(job["timeline"]) == 30
    assert job["timeline"][0]["stage"] == "stage-10"
    assert job["timeline"][-1]["stage"] == "stage-39"


def test_page_check_history_returns_503_when_redis_is_unavailable() -> None:
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        check_job_store=RedisCheckJobStore(redis_client=FailingRedis()),
    )

    with pytest.raises(ServiceError) as exc:
        service.list_page_check_jobs(language="mg")

    assert exc.value.status_code == 503
    assert exc.value.message == "Page check history is temporarily unavailable."

    with pytest.raises(ServiceError) as statistics_exc:
        service.get_page_check_statistics("mg")

    assert statistics_exc.value.status_code == 503
    assert statistics_exc.value.message == "Page check history is temporarily unavailable."


def test_page_check_statistics_aggregate_retained_jobs_by_utc_period(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    as_of = datetime(2026, 8, 18, 12, tzinfo=timezone.utc).timestamp()
    six_month_start = datetime(2026, 2, 18, 12, tzinfo=timezone.utc).timestamp()
    store = RedisCheckJobStore(redis_client=FakeRedis())

    def job(
        job_id: str,
        created_at: Any,
        status: str,
        outcome: Optional[str] = None,
        language: str = "mg",
    ) -> Dict[str, Any]:
        results = [{"status": outcome}] if outcome is not None else None
        return {
            "job_id": job_id,
            "language": language,
            "titles": [job_id],
            "status": status,
            "created_at": created_at,
            "last_updated_at": as_of - 1,
            "attempts": 0,
            "progress": 100 if status == "done" else 0,
            "results": results,
            "error": "failed" if status == "error" else None,
        }

    store.put_many(
        [
            job("good-today", as_of - 3600, "done", "good"),
            job("fixed-this-week", datetime(2026, 8, 17, 10, tzinfo=timezone.utc).timestamp(), "done", "fixed"),
            job("unverifiable", datetime(2026, 7, 20, tzinfo=timezone.utc).timestamp(), "done", "unverifiable"),
            job("job-error", datetime(2026, 4, 1, tzinfo=timezone.utc).timestamp(), "error"),
            job("pending", as_of - 1800, "pending"),
            job("malformed", as_of - 900, "done"),
            job("six-month-boundary", six_month_start, "done", "fixed"),
            job("at-period-end", as_of, "done", "good"),
            job("invalid-date", "unknown", "done", "good"),
            job("other-language", as_of - 600, "done", "good", language="en"),
        ]
    )
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        check_job_store=store,
        page_checker_settings_store=PageCheckerSettingsStore(redis_client=FakeRedis()),
    )
    monkeypatch.setattr(service_module.time, "time", lambda: as_of)

    response = service.get_page_check_statistics("mg")

    assert response["language"] == "mg"
    assert response["generated_at"] == as_of
    assert response["timezone"] == "UTC"
    assert response["retention_limit"] == 2500
    assert response["retained_job_count"] == 9
    statistics = {item["period"]: item for item in response["statistics"]}
    assert statistics["today"] == {
        "period": "today",
        "period_start": datetime(2026, 8, 18, tzinfo=timezone.utc).timestamp(),
        "period_end": as_of,
        "job_count": 3,
        "checked_count": 2,
        "assessable_count": 1,
        "result_counts": {"good": 1, "fixed": 0, "unverifiable": 0, "error": 1},
        "good_percentage": 33.3,
        "grade": "E",
    }
    for period in ("last_7_days", "current_week", "current_month"):
        assert statistics[period]["job_count"] == 4
        assert statistics[period]["result_counts"] == {
            "good": 1,
            "fixed": 1,
            "unverifiable": 0,
            "error": 1,
        }
        assert statistics[period]["good_percentage"] == 25.0
        assert statistics[period]["grade"] == "E"
    assert statistics["last_3_months"]["result_counts"] == {
        "good": 1,
        "fixed": 1,
        "unverifiable": 1,
        "error": 1,
    }
    assert statistics["last_6_months"]["job_count"] == 7
    assert statistics["last_6_months"]["checked_count"] == 6
    assert statistics["last_6_months"]["result_counts"] == {
        "good": 1,
        "fixed": 2,
        "unverifiable": 1,
        "error": 2,
    }
    assert statistics["last_6_months"]["good_percentage"] == 14.3


def test_page_check_statistics_return_empty_periods_without_jobs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    as_of = datetime(2026, 8, 18, 12, tzinfo=timezone.utc).timestamp()
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        check_job_store=RedisCheckJobStore(redis_client=FakeRedis()),
        page_checker_settings_store=PageCheckerSettingsStore(redis_client=FakeRedis()),
    )
    monkeypatch.setattr(service_module.time, "time", lambda: as_of)

    response = service.get_page_check_statistics("mg")

    assert len(response["statistics"]) == 6
    assert all(item["job_count"] == 0 for item in response["statistics"])
    assert all(item["good_percentage"] is None for item in response["statistics"])
    assert all(item["grade"] is None for item in response["statistics"])


def test_page_check_statistics_use_configured_history_without_trimming_storage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    as_of = datetime(2026, 8, 18, 12, tzinfo=timezone.utc).timestamp()
    store = RedisCheckJobStore(redis_client=FakeRedis())
    store.put_many(
        [
            {
                "job_id": f"job-{index}",
                "language": "mg",
                "titles": [f"title-{index}"],
                "status": "done",
                "created_at": as_of - 202 + index,
                "last_updated_at": as_of - 1,
                "attempts": 0,
                "progress": 100,
                "results": [{"status": "fixed" if index < 2 else "good"}],
                "error": None,
            }
            for index in range(202)
        ]
    )
    settings_store = PageCheckerSettingsStore(redis_client=FakeRedis())
    settings_store.set_job_history_limit(200)
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        check_job_store=store,
        page_checker_settings_store=settings_store,
    )
    monkeypatch.setattr(service_module.time, "time", lambda: as_of)

    response = service.get_page_check_statistics("mg")

    assert response["retained_job_count"] == 200
    today = response["statistics"][0]
    assert today["job_count"] == 200
    assert today["checked_count"] == 200
    assert today["result_counts"]["good"] == 200
    assert today["result_counts"]["fixed"] == 0
    assert len(store.all()) == 202


def test_page_check_endpoints_map_store_failures_to_503() -> None:
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        check_job_store=RedisCheckJobStore(redis_client=FailingRedis()),
    )

    with pytest.raises(ServiceError) as enqueue_error:
        service.enqueue_page_check("mg", ["alika"])
    assert enqueue_error.value.status_code == 503

    service._last_check_recovery = time.time()
    with pytest.raises(ServiceError) as get_error:
        service.get_page_check_job("job-1")
    assert get_error.value.status_code == 503


def test_enqueue_page_check_maps_initial_write_failure_to_503() -> None:
    class WriteFailingStore:
        def all(self) -> List[Dict[str, Any]]:
            return []

        def put_many_bounded(
            self,
            _jobs: List[Dict[str, Any]],
            _maximum_jobs: int,
            _maximum_unfinished_jobs: int,
        ) -> bool:
            raise CheckJobStoreError("write failed")

    service = EntryTranslatorService(
        translation=DummyTranslation(),
        check_job_store=WriteFailingStore(),
    )

    with pytest.raises(ServiceError) as exc:
        service.enqueue_page_check("mg", ["alika"])

    assert exc.value.status_code == 503


def test_check_job_retention_removes_oldest_completed_jobs() -> None:
    store = RedisCheckJobStore(redis_client=FakeRedis())
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        check_job_store=store,
        max_check_jobs_kept=2,
    )
    jobs = [
        {
            "job_id": f"job-{index}",
            "language": "mg",
            "titles": [f"title-{index}"],
            "status": "done",
            "created_at": float(index),
            "last_updated_at": float(index),
            "attempts": 0,
            "progress": 100,
            "results": [],
            "error": None,
        }
        for index in range(4)
    ]
    store.put_many(jobs)

    service._trim_check_jobs()

    remaining_ids = {job["job_id"] for job in store.all()}
    assert len(remaining_ids) == 2
    assert "job-0" not in remaining_ids
    assert "job-1" not in remaining_ids


def test_page_checks_use_the_dedicated_executor() -> None:
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        check_job_store=RedisCheckJobStore(redis_client=FakeRedis()),
    )

    future = service._run_check_task(lambda: None)
    future.result(timeout=1)
    service.shutdown(wait=True)

    assert future.done()


def test_translate_page_sync_error() -> None:
    translation = DummyTranslation()

    def failing_process(_page: Any, custom_publish_function=None) -> None:
        raise RuntimeError("boom")

    translation.process_wiktionary_wiki_page = failing_process
    page = DummyPage("hello")

    def get_page(_title: str, _language: str):
        return page

    service = EntryTranslatorService(
        translation=translation,
        job_error_store=JobErrorStore(redis_client=FakeRedis()),
        get_page_func=get_page,
    )

    with pytest.raises(ServiceError) as exc:
        service.translate_page_sync("en", "hello")

    assert exc.value.status_code == 500


def test_translate_page_sync_error_result() -> None:
    translation = DummyTranslation()
    translation.process_result = TranslationPageResult(
        title="hello",
        language="en",
        status="error",
        message="failed",
        error_type="TranslationError",
    )
    page = DummyPage("hello")

    def get_page(_title: str, _language: str):
        return page

    service = EntryTranslatorService(
        translation=translation,
        job_error_store=JobErrorStore(redis_client=FakeRedis()),
        get_page_func=get_page,
    )

    with pytest.raises(ServiceError) as exc:
        service.translate_page_sync("en", "hello")

    assert exc.value.status_code == 500
    assert exc.value.details["status"] == "error"


def test_translate_page_sync_returns_structured_result() -> None:
    translation = DummyTranslation()
    page = DummyPage("hello")

    def get_page(_title: str, _language: str):
        return page

    service = EntryTranslatorService(
        translation=translation,
        job_error_store=JobErrorStore(redis_client=FakeRedis()),
        get_page_func=get_page,
    )

    result = service.translate_page_sync("en", "hello")

    assert result["status"] == "published"
    assert result["entries_count"] == 1


def test_get_translations_success() -> None:
    translation = DummyTranslation()
    translation.translations = [
        DummyTranslationData("noun", {"t": "one"}),
        DummyTranslationData("verb", {"t": "two"}),
    ]

    page = DummyPage("hello")

    def get_page(_title: str, _language: str):
        return page

    def factory(_language: str):
        return DummyProcessor

    service = EntryTranslatorService(
        translation=translation,
        job_error_store=JobErrorStore(redis_client=FakeRedis()),
        get_page_func=get_page,
        processor_factory=factory,
    )

    result = service.get_translations("en", "hello")

    assert result == [{"t": "one"}, {"t": "two"}]


def test_get_translations_error() -> None:
    translation = DummyTranslation()

    def failing_translate(_processor: Any) -> List[Any]:
        raise RuntimeError("boom")

    translation.translate_wiktionary_page = failing_translate
    page = DummyPage("hello")

    def get_page(_title: str, _language: str):
        return page

    service = EntryTranslatorService(
        translation=translation,
        job_error_store=JobErrorStore(redis_client=FakeRedis()),
        get_page_func=get_page,
        processor_factory=lambda _language: DummyProcessor,
    )

    with pytest.raises(ServiceError) as exc:
        service.get_translations("en", "hello")

    assert exc.value.status_code == 500


def test_get_processed_page_builds_entries() -> None:
    translation = DummyTranslation()
    page = DummyPage("hello")

    def get_page(_title: str, _language: str):
        return page

    processor = DummyProcessor()
    processor.entries = [DummyEntry("en", "noun", ["one"]) ]
    processor.translations = [
        DummyTranslationData("noun", {"t": "ok"}),
        DummyTranslationData("verb", {"t": "skip"}),
    ]

    def factory(_language: str):
        return lambda: processor

    service = EntryTranslatorService(
        translation=translation,
        job_error_store=JobErrorStore(redis_client=FakeRedis()),
        get_page_func=get_page,
        processor_factory=factory,
    )

    result = service.get_processed_page("en", "hello")

    assert result == [
        {"language": "en", "part_of_speech": "noun", "translations": [{"t": "ok"}]}
    ]
    assert processor.text == "body"
    assert processor.title_value == "hello"


def test_get_page_snapshot_force_refreshes_and_hashes_exact_content() -> None:
    """Review snapshots parse and hash the same live Wiktionary content."""
    page = DummyPage("dog", "==English==\n# a domesticated animal")
    processor = DummyProcessor()
    processor.entries = [DummyEntry("en", "noun", ["a domesticated animal"])]
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        get_page_func=lambda _title, _language: page,
        processor_factory=lambda _language: lambda: processor,
    )

    snapshot = service.get_page_snapshot("en", "dog")

    assert snapshot == {
        "language": "en",
        "title": "dog",
        "namespace": 0,
        "content": "==English==\n# a domesticated animal",
        "content_sha256": hashlib.sha256(
            b"==English==\n# a domesticated animal"
        ).hexdigest(),
        "entries": [{"language": "en", "part_of_speech": "noun"}],
        "parsed": True,
        "parse_error": None,
        "content_trust": "untrusted_wiktionary_content",
    }
    assert page.force_refreshes == [True]
    assert processor.text == snapshot["content"]


def test_get_page_snapshot_returns_raw_evidence_when_parsing_fails() -> None:
    """A parser defect must not make its manual-review evidence inaccessible."""

    class FailingProcessor(DummyProcessor):
        def process(self, _page: Any) -> None:
            raise RuntimeError("malformed template")

    page = DummyPage("broken", "{{malformed")
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        get_page_func=lambda _title, _language: page,
        processor_factory=lambda _language: FailingProcessor,
    )

    snapshot = service.get_page_snapshot("mg", "broken")

    assert snapshot["content"] == "{{malformed"
    assert snapshot["content_sha256"] == hashlib.sha256(b"{{malformed").hexdigest()
    assert snapshot["entries"] == []
    assert snapshot["parsed"] is False
    assert snapshot["parse_error"] == "The live page content could not be parsed."


def test_get_page_snapshot_rejects_unsupported_language_and_large_page() -> None:
    """The MCP snapshot boundary is limited by wiki and response size."""
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        get_page_func=lambda title, _language: DummyPage(
            title,
            "x" * (EntryTranslatorService._MAX_PAGE_SNAPSHOT_BYTES + 1),
        ),
        processor_factory=lambda _language: DummyProcessor,
    )

    with pytest.raises(ServiceError) as unsupported:
        service.get_page_snapshot("fr", "chien")
    assert unsupported.value.status_code == 400

    with pytest.raises(ServiceError) as too_large:
        service.get_page_snapshot("en", "dog")
    assert too_large.value.status_code == 413


def test_snapshot_maps_missing_live_page_without_changing_existing_routes() -> None:
    """Only the new live-snapshot endpoint changes a Redis cache miss to 404."""

    class MissingPage(DummyPage):
        def get(self, force_refresh: bool = False) -> str:
            del force_refresh
            raise service_module.NoPage("missing")

    service = EntryTranslatorService(
        translation=DummyTranslation(),
        get_page_func=lambda _title, _language: MissingPage("missing"),
        processor_factory=lambda _language: DummyProcessor,
    )

    with pytest.raises(ServiceError) as existing_route:
        service.get_processed_page("en", "missing")
    with pytest.raises(ServiceError) as snapshot_route:
        service.get_page_snapshot("en", "missing")

    assert existing_route.value.status_code == 502
    assert snapshot_route.value.status_code == 404


def test_get_processed_page_adds_preview_only_recursive_descendants() -> None:
    """Expose trees at the response boundary without changing entry serialization."""

    translation = DummyTranslation()
    page = DummyPage("hello")
    processor = DummyProcessor()
    entry = DummyEntry(
        "fr", "noun", ["one"], additional_data={"descendant": ["mot", "motet"]}
    )
    processor.entries = [entry]
    processor.descendants = [
        {
            "lang": "French",
            "lang_code": "fr",
            "word": "mot",
            "descendants": [
                {"lang": "Middle French", "lang_code": "frm", "word": "motet"}
            ],
        }
    ]
    service = EntryTranslatorService(
        translation=translation,
        job_error_store=JobErrorStore(redis_client=FakeRedis()),
        get_page_func=lambda _title, _language: page,
        processor_factory=lambda _language: lambda: processor,
    )

    result = service.get_processed_page("en", "hello")

    assert result == [
        {
            "language": "fr",
            "part_of_speech": "noun",
            "additional_data": {"descendant": ["mot", "motet"]},
            "descendants": processor.descendants,
        }
    ]
    assert processor.descendant_requests == [("fr", "noun", 2_000)]
    assert entry.additional_data == {"descendant": ["mot", "motet"]}
    assert "descendants" not in entry.serialise()


def test_get_processed_page_bounds_descendants_across_entries() -> None:
    """Apply one recursive descendant budget to the entire response."""

    processor = DummyProcessor()
    processor.entries = [
        DummyEntry("fr", "noun", ["one"]),
        DummyEntry("de", "verb", ["two"]),
    ]
    processor.descendants = [
        {"lang": "French", "lang_code": "fr", "word": f"mot-{index}"}
        for index in range(2_001)
    ]
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        job_error_store=JobErrorStore(redis_client=FakeRedis()),
        get_page_func=lambda _title, _language: DummyPage("hello"),
        processor_factory=lambda _language: lambda: processor,
    )

    result = service.get_processed_page("en", "hello")

    assert len(result[0]["descendants"]) == 2_000
    assert "descendants" not in result[1]
    assert len(processor.descendants) == 2_001
    assert processor.descendant_requests == [("fr", "noun", 2_000)]


def test_get_processed_page_bounds_descendant_depth() -> None:
    """Defend response serialization from processors returning an unsafe depth."""

    root: Dict[str, Any] = {"lang": "French", "lang_code": "fr", "word": "0"}
    current = root
    for depth in range(1, 40):
        child: Dict[str, Any] = {
            "lang": "French",
            "lang_code": "fr",
            "word": str(depth),
        }
        current["descendants"] = [child]
        current = child
    processor = DummyProcessor()
    processor.entries = [DummyEntry("fr", "noun", ["one"])]
    processor.descendants = [root]
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        job_error_store=JobErrorStore(redis_client=FakeRedis()),
        get_page_func=lambda _title, _language: DummyPage("hello"),
        processor_factory=lambda _language: lambda: processor,
    )

    result = service.get_processed_page("en", "hello")

    descendants = result[0]["descendants"]
    depth = 0
    while descendants:
        depth += 1
        descendants = descendants[0].get("descendants", [])
    assert depth == 32


def test_get_processed_page_bounds_descendant_payload_size() -> None:
    """Prevent repeated metadata from amplifying the preview response."""

    processor = DummyProcessor()
    processor.entries = [
        DummyEntry("fr", "noun", ["one"]),
        DummyEntry("de", "verb", ["two"]),
    ]
    processor.descendants = [
        {
            "lang": "French",
            "lang_code": "fr",
            "word": f"mot-{index}",
            "raw_tags": ["x" * 2_000],
        }
        for index in range(1_000)
    ]
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        job_error_store=JobErrorStore(redis_client=FakeRedis()),
        get_page_func=lambda _title, _language: DummyPage("hello"),
        processor_factory=lambda _language: lambda: processor,
    )

    result = service.get_processed_page("en", "hello")

    payload_size = sum(
        len(
            json.dumps(section.get("descendants", []), separators=(",", ":")).encode(
                "utf-8"
            )
        )
        for section in result
    )
    assert payload_size <= 1_000_000
    assert sum(len(section.get("descendants", [])) for section in result) < 2_000


def test_descendant_bounds_reject_invalid_processor_values() -> None:
    """Malformed processor data cannot escape through preview-size helpers."""
    assert EntryTranslatorService._bounded_descendant_nodes(  # pylint: disable=protected-access
        None,
        10,
        1_000,
    ) == []
    assert EntryTranslatorService._bounded_descendant_nodes(  # pylint: disable=protected-access
        [{"value": object()}],
        10,
        1_000,
    ) == []
    assert EntryTranslatorService._descendant_payload_size(  # pylint: disable=protected-access
        {"value": object()}
    ) == 0
    assert EntryTranslatorService._descendant_node_count(  # pylint: disable=protected-access
        [None, {"word": "valid"}]
    ) == 1


def test_get_processed_page_skips_translation_attachment_for_other_language() -> None:
    translation = DummyTranslation()
    page = DummyPage("hello")
    processor = DummyProcessor()
    processor.entries = [DummyEntry("fr", "noun", ["one"])]
    processor.translations = [DummyTranslationData("noun", {"t": "skip"})]

    service = EntryTranslatorService(
        translation=translation,
        job_error_store=JobErrorStore(redis_client=FakeRedis()),
        get_page_func=lambda _title, _language: page,
        processor_factory=lambda _language: lambda: processor,
    )

    result = service.get_processed_page("en", "hello")

    assert result == [{"language": "fr", "part_of_speech": "noun"}]


def test_fetch_page_not_found() -> None:
    translation = DummyTranslation()

    def get_page(_title: str, _language: str):
        return None

    service = EntryTranslatorService(
        translation=translation,
        job_error_store=JobErrorStore(redis_client=FakeRedis()),
        get_page_func=get_page,
    )

    with pytest.raises(ServiceError) as exc:
        service.get_translations("en", "missing")

    assert exc.value.status_code == 404


def test_fetch_page_error() -> None:
    translation = DummyTranslation()

    def get_page(_title: str, _language: str):
        raise RuntimeError("boom")

    service = EntryTranslatorService(
        translation=translation,
        job_error_store=JobErrorStore(redis_client=FakeRedis()),
        get_page_func=get_page,
    )

    with pytest.raises(ServiceError) as exc:
        service.translate_page_sync("en", "boom")

    assert exc.value.status_code == 502


def test_fetch_page_preserves_wikimedia_retry_after() -> None:
    page = DummyPage("busy")

    def limited_get() -> str:
        raise WikimediaRateLimitError(
            "Wikimedia is rate limited.",
            retry_after=2.1,
            status=429,
        )

    page.get = limited_get  # type: ignore[method-assign]
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        job_error_store=JobErrorStore(redis_client=FakeRedis()),
        get_page_func=lambda _title, _language: page,
    )

    with pytest.raises(ServiceError) as exc:
        service.get_translations("en", "busy")

    assert exc.value.status_code == 429
    assert exc.value.headers == {"Retry-After": "3"}
    assert exc.value.details == {
        "type": "WikimediaRateLimitError",
        "retry_after_seconds": 3,
    }


def test_run_task_uses_owned_executor() -> None:
    """Test task execution uses the bounded owned executor."""
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        job_error_store=JobErrorStore(redis_client=FakeRedis()),
    )
    flag = {"done": False}

    future = service._run_task(lambda: flag.update(done=True))
    future.result(timeout=1)
    service.shutdown()

    assert flag["done"] is True


def test_is_error_result_returns_false_for_unknown_result() -> None:
    """Test unknown translation result types are not treated as errors."""
    assert EntryTranslatorService._is_error_result(object()) is False


def test_run_task_uses_injected_runner() -> None:
    """Test injected task runners remain supported for deterministic callers."""
    calls: List[Callable[[], None]] = []
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        job_error_store=JobErrorStore(redis_client=FakeRedis()),
        task_runner=calls.append,
    )

    result = service._run_task(lambda: None)

    assert result is None
    assert len(calls) == 1


def test_enqueue_rejects_when_process_capacity_is_full() -> None:
    """Test admission control rejects work before performing page I/O."""
    tasks: List[Callable[[], None]] = []
    fetch_count = 0

    def get_page(_title: str, _language: str) -> DummyPage:
        nonlocal fetch_count
        fetch_count += 1
        return DummyPage("hello")

    service = EntryTranslatorService(
        translation=DummyTranslation(),
        publisher=DummyPublisher(),
        queue_counter=QueueCounter(),
        job_error_store=JobErrorStore(redis_client=FakeRedis()),
        get_page_func=get_page,
        task_runner=tasks.append,
        max_async_workers=1,
        max_pending_jobs=0,
        translation_job_store=RedisTranslationJobStore(redis_client=FakeRedis()),
    )

    service.enqueue_translation_job("en", "first")
    with pytest.raises(ServiceError) as exc:
        service.enqueue_translation_job("en", "second")

    assert exc.value.status_code == 503
    assert fetch_count == 0
    assert service.health_status()["available_job_slots"] == 0

    tasks[0]()
    assert fetch_count == 1
    assert service.health_status()["available_job_slots"] == 1


def test_shutdown_rejects_new_async_jobs() -> None:
    """Test shutdown closes admission without invoking the injected runner."""
    tasks: List[Callable[[], None]] = []
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        publisher=DummyPublisher(),
        queue_counter=QueueCounter(),
        job_error_store=JobErrorStore(redis_client=FakeRedis()),
        get_page_func=lambda _title, _language: DummyPage("hello"),
        task_runner=tasks.append,
        translation_job_store=RedisTranslationJobStore(redis_client=FakeRedis()),
    )

    service.shutdown()

    with pytest.raises(ServiceError) as exc:
        service.enqueue_translation_job("en", "hello")

    assert exc.value.status_code == 503
    assert tasks == []


def test_redis_queue_counter() -> None:
    redis_client = FakeRedis()
    counter = RedisQueueCounter(redis_client=redis_client, key="jobs")

    counter.increment()
    counter.increment()
    counter.decrement()

    assert counter.get() == 1
    assert counter.source == "redis"


def test_redis_queue_counter_fences_active_job_owners() -> None:
    counter = RedisQueueCounter(redis_client=FakeRedis(), key="jobs")

    assert counter.claim_job("hello", "en", 10, "job-1", "owner-1") is True
    assert counter.claim_job("hello", "en", 10, "job-1", "owner-2") is False
    assert counter.owns_job("job-1", "owner-1") is True
    assert counter.owns_job("job-1", "owner-2") is False
    assert counter.touch_job("job-1", 20, "owner-2") is False
    assert counter.finish_job("job-1", "owner-2") is False
    assert counter.touch_job("job-1", 20, "owner-1") is True
    assert counter.finish_job("job-1", "owner-1") is True
    assert counter.get() == 0


def test_queue_counter_rejects_duplicate_ids_and_unknown_finishes() -> None:
    counter = QueueCounter()
    counter.increment()
    counter.decrement()
    counter.decrement()
    counter.start_job("hello", "en", 1, "job-1")

    with pytest.raises(RuntimeError, match="already exists"):
        counter.start_job("hello", "en", 1, "job-1")

    assert counter.finish_job("missing", "owner") is False


def test_redis_queue_counter_reports_authoritative_lease_failures() -> None:
    counter = RedisQueueCounter(redis_client=FailingRedis(), key="jobs")

    with pytest.raises(TranslationJobStoreError, match="claim"):
        counter.claim_job("hello", "en", 1, "job-1", "owner-1")
    with pytest.raises(TranslationJobStoreError, match="verify"):
        counter.owns_job("job-1", "owner-1")


def test_redis_queue_counter_heartbeat_falls_back_only_for_legacy_jobs() -> None:
    fallback = QueueCounter()
    assert fallback.claim_job("hello", "en", 1, "job-1", "owner-1")
    counter = RedisQueueCounter(
        redis_client=FailingRedis(),
        key="jobs",
        fallback=fallback,
    )

    assert counter.touch_job("job-1", 2) is True
    assert counter.source == "local-fallback"

    with pytest.raises(TranslationJobStoreError, match="refresh"):
        counter.touch_job("job-1", 3, "owner-1")


def test_redis_queue_counter_clamps_negative_and_handles_empty_value() -> None:
    redis_client = FakeRedis()
    counter = RedisQueueCounter(redis_client=redis_client, key="jobs")

    assert counter.get() == 0
    counter.decrement()

    assert counter.get() == 0


def test_redis_queue_counter_falls_back() -> None:
    fallback = QueueCounter()
    counter = RedisQueueCounter(
        redis_client=FailingRedis(),
        key="jobs",
        fallback=fallback,
    )

    counter.increment()
    assert counter.get() == 1
    counter.decrement()

    assert counter.get() == 0
    assert counter.source == "local-fallback"


def test_redis_queue_counter_recovers_stale_jobs() -> None:
    redis_client = FakeRedis()
    counter = RedisQueueCounter(redis_client=redis_client, key="jobs")
    job_started_at = 10
    timeout_seconds = 30
    job_id = counter.start_job("hello", "en", started_at=job_started_at)

    assert counter.get() == 1
    assert counter.recover_stale_jobs(
        timeout_seconds=timeout_seconds, now=job_started_at + timeout_seconds
    ) == [
        {
            "job_id": job_id,
            "title": "hello",
            "language": "en",
            "started_at": job_started_at,
        }
    ]
    assert counter.get() == 0


def test_redis_queue_counter_uses_heartbeats_for_stale_recovery() -> None:
    redis_client = FakeRedis()
    counter = RedisQueueCounter(redis_client=redis_client, key="jobs")
    job_id = counter.start_job("hello", "en", started_at=10)

    counter.touch_job(job_id, touched_at=35)

    assert counter.recover_stale_jobs(timeout_seconds=30, now=40) == []
    assert counter.get() == 1
    assert counter.recover_stale_jobs(timeout_seconds=30, now=65) == [
        {
            "job_id": job_id,
            "title": "hello",
            "language": "en",
            "started_at": 10,
        }
    ]
    assert counter.get() == 0


def test_redis_queue_counter_recovery_does_not_delete_a_newer_heartbeat() -> None:
    redis_client = FakeRedis()
    counter = RedisQueueCounter(redis_client=redis_client, key="jobs")
    job_id = counter.start_job("hello", "en", started_at=10)
    observed_heartbeat = redis_client.hashes["jobs:heartbeats"][job_id]

    assert counter.touch_job(job_id, touched_at=35) is True
    recovered = redis_client.eval(
        RedisQueueCounter._RECOVER_JOB_SCRIPT,
        2,
        "jobs",
        "jobs:heartbeats",
        job_id,
        observed_heartbeat,
    )

    assert recovered == 0
    assert counter.get() == 1


def test_queue_counter_preserves_protected_stale_jobs() -> None:
    """Active process-owned records are not mistaken for orphaned jobs."""
    counter = QueueCounter()
    protected_job_id = counter.start_job("active", "en", started_at=10)
    orphaned_job_id = counter.start_job("orphaned", "en", started_at=10)

    recovered = counter.recover_stale_jobs(
        timeout_seconds=30,
        now=40,
        protected_job_ids={protected_job_id},
    )

    assert [job["job_id"] for job in recovered] == [orphaned_job_id]
    assert counter.get() == 1


def test_redis_queue_counter_recovers_stale_fallback_jobs() -> None:
    fallback = QueueCounter()
    counter = RedisQueueCounter(redis_client=FailingRedis(), fallback=fallback)
    job_id = counter.start_job("hello", "en", started_at=10)

    assert counter.recover_stale_jobs(timeout_seconds=30, now=40) == [
        {
            "job_id": job_id,
            "title": "hello",
            "language": "en",
            "started_at": 10,
        }
    ]
    assert counter.get() == 0
    assert counter.source == "local-fallback"


def test_health_recovers_stale_job_and_records_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    counter = QueueCounter()
    job_id = "9c9a6a48-2304-4505-9cfe-57fbddc88bb1"
    owner_token = "owner-1"
    assert counter.claim_job(
        "stuck",
        "en",
        started_at=10,
        job_id=job_id,
        owner_token=owner_token,
    )
    error_store = JobErrorStore(redis_client=FakeRedis())
    job_store = RecordingTranslationJobStore()
    job_store.put(
        {
            "job_id": job_id,
            "language": "en",
            "title": "stuck",
            "status": "running",
            "stage": "translating",
            "publication_state": "not_queued",
            "created_at": 10,
            "last_updated_at": 10,
            "result": None,
                "error": None,
                "message": "translation job queued",
                "_owner_token": owner_token,
            }
    )
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        queue_counter=counter,
        job_error_store=error_store,
        stale_job_timeout_seconds=30,
        translation_job_store=job_store,
    )

    monkeypatch.setattr(service_module.time, "time", lambda: 40)
    status = service.health_status()

    assert status["jobs"] == 0
    assert service.recent_job_errors()[0]["title"] == "stuck"
    assert service.recent_job_errors()[0]["type"] == "StaleJobTimeout"
    assert service.recent_job_errors()[0]["job_id"] == job_id
    assert service.get_translation_job("en", job_id)["status"] == "error"


def test_build_redis_client(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyConfig:
        def get(self, key: str, section: str) -> str:
            return {"host": "redis.local", "password": ""}[key]

    calls: Dict[str, Any] = {}

    def fake_redis(**kwargs: Any) -> Dict[str, Any]:
        calls.update(kwargs)
        return kwargs

    monkeypatch.setattr(service_module, "BotjagwarConfig", lambda: DummyConfig())
    monkeypatch.setattr(service_module.redis, "Redis", fake_redis)

    client = RedisQueueCounter._build_redis_client()

    assert client["host"] == "redis.local"
    assert calls["password"] is None


def test_job_error_store_records_recent_errors() -> None:
    store = JobErrorStore(redis_client=FakeRedis(), max_entries=2)

    store.record_error({"message": "one", "error": "x", "type": "ValueError"})
    store.record_error({"message": "two", "error": "y", "type": "RuntimeError"})
    store.record_error({"message": "three", "error": "z", "type": "Exception"})

    assert [error["message"] for error in store.recent_errors()] == ["three", "two"]


def test_job_error_store_falls_back() -> None:
    store = JobErrorStore(redis_client=FailingRedis(), max_entries=1)

    store.record_error({"message": "one", "error": "x", "type": "ValueError"})
    store.record_error({"message": "two", "error": "y", "type": "RuntimeError"})

    assert store.recent_errors() == [
        {"message": "two", "error": "y", "type": "RuntimeError"}
    ]


def test_record_job_error_dict_and_unknown_result() -> None:
    error_store = JobErrorStore(redis_client=FakeRedis())
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        queue_counter=QueueCounter(),
        job_error_store=error_store,
    )

    assert service._serialise_translation_result({"status": "ok"}, "title", "en") == {"status": "ok"}
    assert service._serialise_translation_result(None, "title", "en")["status"] == "unknown"
    assert service._serialise_translation_result(0, "title", "en")["status"] == "no_entries"
    assert service._is_error_result({"status": "error"}) is True
    service._record_job_error(
        "dict error",
        {"message": "bad", "error_type": "ValueError", "title": "t", "language": "en"},
    )

    assert service.recent_job_errors()[0]["type"] == "ValueError"


def test_record_job_duration_ignores_negative_values() -> None:
    service = EntryTranslatorService(
        translation=DummyTranslation(),
        queue_counter=QueueCounter(),
        job_error_store=JobErrorStore(redis_client=FakeRedis()),
    )

    service._record_job_duration(-1)
    service._record_job_duration(10)
    service._record_job_duration(20)

    assert service._get_average_job_duration() == 12.0


def test_default_get_page(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: Dict[str, Any] = {}

    class DummySite:
        def __init__(self, language: str, wiki: str) -> None:
            calls["site"] = (language, wiki)

    class DummyPage:
        def __init__(self, site: DummySite, title: str) -> None:
            calls["page"] = (site, title)

    monkeypatch.setattr(service_module, "Site", DummySite)
    monkeypatch.setattr(service_module, "Page", DummyPage)

    page = EntryTranslatorService._default_get_page("hello", "en")

    assert isinstance(page, DummyPage)
    assert calls["site"] == ("en", "wiktionary")
