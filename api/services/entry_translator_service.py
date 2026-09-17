"""Business logic for entry translator v2."""
from __future__ import annotations

import calendar
import hashlib
import json
import logging
import math
import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterator, List, Optional, Protocol, Tuple

import redis

from api import entryprocessor
from api.config import BotjagwarConfig
from api.model.word import Entry
from api.services.page_check_service import (
    PageCheckPublicationSuperseded,
    PageCheckService,
)
from api.services.definition_translation_settings import (
    DefinitionTranslationSettings,
    DefinitionTranslationSettingsStore,
    DefinitionTranslationSettingsStoreError,
    DefinitionTranslationSettingsValidationError,
)
from api.services.page_checker_settings import (
    DEFAULT_JOB_HISTORY_LIMIT,
    PageCheckerSettings,
    PageCheckerSettingsStore,
    PageCheckerSettingsStoreError,
    PageCheckerSettingsValidationError,
)
from api.services.page_check_review_queue import (
    PageCheckReviewQueueError,
    RabbitMqPageCheckReviewQueue,
    REVIEWABLE_PAGE_CHECK_OUTCOMES,
    build_page_check_review_message,
    validate_page_check_review_message,
)
from api.translation_v2.core import Translation, TranslationPageResult
from api.translation_v2.publishers import WiktionaryRabbitMqPublisher
from api.wikimedia_rate_limiter import WikimediaRateLimitError
from redis_wikicache import NoPage, RedisPage as Page, RedisSite as Site

log = logging.getLogger(__name__)


@dataclass
class ServiceError(Exception):
    """Error raised by the service with HTTP status and details."""

    message: str
    status_code: int = 500
    details: Optional[Dict[str, Any]] = None
    headers: Optional[Dict[str, str]] = None

    def __str__(self) -> str:
        return self.message


class CheckJobStoreError(RuntimeError):
    """Raised when persistent page-check job storage is unavailable or invalid."""


class CheckJobExecutionSuperseded(PageCheckPublicationSuperseded):
    """Raised when stale recovery has fenced an older page-check execution."""


class TranslationJobStoreError(RuntimeError):
    """Raised when persistent translation job storage is unavailable or invalid."""


class TranslationJobLeaseLost(TranslationJobStoreError):
    """Raised when another process has fenced a translation job owner."""


_CHECK_JOB_TIMELINE_LIMIT = 30


def _normalise_check_job(job: Dict[str, Any]) -> Dict[str, Any]:
    """Add display fields missing from page-check jobs stored by older releases."""
    status = job.get("status", "pending")
    default_stage = {
        "pending": "queued",
        "running": "checking",
        "done": "completed",
        "error": "failed",
    }.get(status, "queued")
    default_message = {
        "pending": "Waiting for a page-check worker.",
        "running": "Checking the page against its sources.",
        "done": "Page check completed.",
        "error": str(job.get("error") or "Page check failed."),
    }.get(status, "Waiting for a page-check worker.")
    job.setdefault("stage", default_stage)
    job.setdefault("message", default_message)
    timeline = job.get("timeline")
    if not isinstance(timeline, list):
        job["timeline"] = []
    else:
        job["timeline"] = [
            event for event in timeline if isinstance(event, dict)
        ][-_CHECK_JOB_TIMELINE_LIMIT:]
    job.setdefault("review_queue_state", "not_needed")
    job.setdefault("review_event_id", None)
    job.setdefault("review_queue_error", None)
    return job


def _review_handoff_is_claimable(
    job: Dict[str, Any],
    now: float,
    lease_seconds: float,
) -> bool:
    """Return whether a review handoff is eligible for an atomic claim."""
    state = job.get("review_queue_state")
    if state not in {"pending", "failed", "publishing"}:
        return False
    next_attempt_at = job.get("review_queue_next_attempt_at")
    if (
        state == "failed"
        and isinstance(next_attempt_at, (int, float))
        and not isinstance(next_attempt_at, bool)
        and now < next_attempt_at
    ):
        return False
    claimed_at = job.get("review_queue_claimed_at")
    if (
        state == "publishing"
        and isinstance(claimed_at, (int, float))
        and not isinstance(claimed_at, bool)
        and now - claimed_at < lease_seconds
    ):
        return False
    return True


def _count_check_results(results: Optional[List[Dict[str, Any]]]) -> Dict[str, int]:
    """Count page check results by status.

    Args:
        results: Serialized page check results, or None for unfinished jobs.

    Returns:
        A dict with "good", "fixed", "unverifiable" and "error" counts.
    """
    counts = {"good": 0, "fixed": 0, "unverifiable": 0, "error": 0}
    if not results:
        return counts
    for result in results:
        status = result.get("status")
        if status in counts:
            counts[status] += 1
        else:
            counts["error"] += 1
    return counts


def _subtract_calendar_months(value: datetime, months: int) -> datetime:
    """Subtract calendar months while clamping invalid month-end days."""
    if months < 0:
        raise ValueError("months must not be negative")
    month_index = value.month - 1 - months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def _page_check_period_bounds(as_of: float) -> List[Tuple[str, float, float]]:
    """Return the canonical UTC periods for page-check statistics."""
    current = datetime.fromtimestamp(as_of, tz=timezone.utc)
    day_start = current.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = day_start - timedelta(days=current.weekday())
    month_start = day_start.replace(day=1)
    return [
        ("today", day_start.timestamp(), as_of),
        ("last_7_days", (current - timedelta(days=7)).timestamp(), as_of),
        ("current_week", week_start.timestamp(), as_of),
        ("current_month", month_start.timestamp(), as_of),
        ("last_3_months", _subtract_calendar_months(current, 3).timestamp(), as_of),
        ("last_6_months", _subtract_calendar_months(current, 6).timestamp(), as_of),
    ]


def _page_check_grade(percentage: Optional[float]) -> Optional[str]:
    """Return the A-E grade for a page-check quality percentage."""
    if percentage is None:
        return None
    if percentage >= 90:
        return "A"
    if percentage >= 80:
        return "B"
    if percentage >= 70:
        return "C"
    if percentage >= 60:
        return "D"
    return "E"


def _page_check_job_outcome(job: Dict[str, Any]) -> Optional[str]:
    """Return one effective terminal outcome for a one-page check job."""
    status = job.get("status")
    if status not in ("done", "error"):
        return None
    if status == "error":
        return "error"
    results = job.get("results")
    if not isinstance(results, list) or len(results) != 1:
        return "error"
    result = results[0]
    if not isinstance(result, dict):
        return "error"
    outcome = result.get("status")
    if outcome not in ("good", "fixed", "unverifiable", "error"):
        return "error"
    return outcome


def _aggregate_page_check_period(
    jobs: List[Dict[str, Any]],
    period: str,
    period_start: float,
    period_end: float,
) -> Dict[str, Any]:
    """Aggregate retained page-check jobs within one half-open period."""
    period_jobs = [
        job
        for job in jobs
        if isinstance(job.get("created_at"), (int, float))
        and period_start <= job["created_at"] < period_end
    ]
    result_counts = {
        "good": 0,
        "fixed": 0,
        "unverifiable": 0,
        "error": 0,
    }
    for job in period_jobs:
        outcome = _page_check_job_outcome(job)
        if outcome is not None:
            result_counts[outcome] += 1
    job_count = len(period_jobs)
    checked_count = sum(result_counts.values())
    assessable_count = result_counts["good"] + result_counts["fixed"]
    good_percentage = (
        round(result_counts["good"] * 100 / job_count, 1)
        if job_count
        else None
    )
    return {
        "period": period,
        "period_start": period_start,
        "period_end": period_end,
        "job_count": job_count,
        "checked_count": checked_count,
        "assessable_count": assessable_count,
        "result_counts": result_counts,
        "good_percentage": good_percentage,
        "grade": _page_check_grade(good_percentage),
    }


class JobCounter(Protocol):
    """Counter interface used for translator backpressure."""

    @property
    def source(self) -> str:
        """Return the counter backend name."""

    def increment(self) -> None:
        """Increment the active job count."""

    def decrement(self) -> None:
        """Decrement the active job count."""

    def get(self) -> int:
        """Return the active job count."""

    def start_job(
        self,
        title: str,
        language: str,
        started_at: float,
        job_id: Optional[str] = None,
    ) -> str:
        """Record an active translation job and return its identifier."""

    def claim_job(
        self,
        title: str,
        language: str,
        started_at: float,
        job_id: str,
        owner_token: str,
    ) -> bool:
        """Claim a new active job without replacing another owner."""

    def touch_job(
        self,
        job_id: str,
        touched_at: float,
        owner_token: Optional[str] = None,
    ) -> bool:
        """Refresh an active job's liveness timestamp and report ownership."""

    def owns_job(self, job_id: str, owner_token: str) -> bool:
        """Return whether the active lease still belongs to this owner."""

    def finish_job(self, job_id: str, owner_token: Optional[str] = None) -> bool:
        """Remove a completed translation job when its owner still matches."""

    def recover_stale_jobs(
        self,
        timeout_seconds: float,
        now: float,
        protected_job_ids: Optional[set[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Remove and return jobs that exceeded the configured timeout."""


class QueueCounter:
    """Thread-safe queue counter."""

    def __init__(self) -> None:
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._heartbeats: Dict[str, float] = {}
        self._owner_tokens: Dict[str, str] = {}
        self._legacy_job_ids: List[str] = []
        self._lock = threading.Lock()

    @property
    def source(self) -> str:
        """Return the counter backend name."""
        return "local"

    def increment(self) -> None:
        """Increment the queue counter."""
        with self._lock:
            job_id = str(uuid.uuid4())
            self._jobs[job_id] = self._build_job(job_id, "", "", time.time())
            self._legacy_job_ids.append(job_id)

    def decrement(self) -> None:
        """Decrement the queue counter."""
        with self._lock:
            job_id = self._legacy_job_ids.pop() if self._legacy_job_ids else None
            if job_id:
                self._jobs.pop(job_id, None)

    def get(self) -> int:
        """Get the current queue count."""
        with self._lock:
            return len(self._jobs)

    def start_job(
        self,
        title: str,
        language: str,
        started_at: float,
        job_id: Optional[str] = None,
    ) -> str:
        """Record an active job in local process memory."""
        job_id = job_id or str(uuid.uuid4())
        if not self.claim_job(
            title,
            language,
            started_at,
            job_id,
            "",
        ):
            raise RuntimeError(f"Active job {job_id} already exists.")
        return job_id

    def claim_job(
        self,
        title: str,
        language: str,
        started_at: float,
        job_id: str,
        owner_token: str,
    ) -> bool:
        """Claim a local active job without replacing another owner."""
        with self._lock:
            if job_id in self._jobs:
                return False
            self._jobs[job_id] = self._build_job(job_id, title, language, started_at)
            self._heartbeats[job_id] = started_at
            self._owner_tokens[job_id] = owner_token
            return True

    def touch_job(
        self,
        job_id: str,
        touched_at: float,
        owner_token: Optional[str] = None,
    ) -> bool:
        """Refresh a local active job's heartbeat when it still exists."""
        with self._lock:
            if job_id in self._jobs and (
                owner_token is None
                or self._owner_tokens.get(job_id) == owner_token
            ):
                self._heartbeats[job_id] = touched_at
                return True
            return False

    def owns_job(self, job_id: str, owner_token: str) -> bool:
        """Return whether a local active lease still belongs to this owner."""
        with self._lock:
            return (
                job_id in self._jobs
                and self._owner_tokens.get(job_id) == owner_token
            )

    @staticmethod
    def _build_job(
        job_id: str, title: str, language: str, started_at: float
    ) -> Dict[str, Any]:
        """Create a local active-job record."""
        return {
            "job_id": job_id,
            "title": title,
            "language": language,
            "started_at": started_at,
        }

    def finish_job(self, job_id: str, owner_token: Optional[str] = None) -> bool:
        """Remove a completed local job when its owner still matches."""
        with self._lock:
            if job_id not in self._jobs or (
                owner_token is not None
                and self._owner_tokens.get(job_id) != owner_token
            ):
                return False
            self._jobs.pop(job_id, None)
            self._heartbeats.pop(job_id, None)
            self._owner_tokens.pop(job_id, None)
            return True

    def recover_stale_jobs(
        self,
        timeout_seconds: float,
        now: float,
        protected_job_ids: Optional[set[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Remove local jobs whose runtime exceeds the timeout."""
        protected_job_ids = protected_job_ids or set()
        with self._lock:
            stale_jobs = [
                job
                for job in self._jobs.values()
                if job["job_id"] not in protected_job_ids
                and now
                - self._heartbeats.get(job["job_id"], float(job["started_at"]))
                >= timeout_seconds
            ]
            for job in stale_jobs:
                self._jobs.pop(job["job_id"], None)
                self._heartbeats.pop(job["job_id"], None)
                owner_token = self._owner_tokens.pop(job["job_id"], "")
                if owner_token:
                    job["_owner_token"] = owner_token
            return stale_jobs


class RedisQueueCounter:
    """Redis-backed active job counter with local fallback."""

    _CLAIM_JOB_SCRIPT = """
if redis.call('HSETNX', KEYS[1], ARGV[1], ARGV[2]) == 0 then
    return 0
end
redis.call('HSET', KEYS[2], ARGV[1], ARGV[3])
return 1
"""
    _TOUCH_JOB_SCRIPT = """
local record = redis.call('HGET', KEYS[1], ARGV[1])
if not record then
    redis.call('HDEL', KEYS[2], ARGV[1])
    return 0
end
if ARGV[3] ~= '' then
    local decoded = cjson.decode(record)
    if decoded['_owner_token'] ~= ARGV[3] then
        return 0
    end
end
redis.call('HSET', KEYS[2], ARGV[1], ARGV[2])
return 1
"""
    _FINISH_JOB_SCRIPT = """
local record = redis.call('HGET', KEYS[1], ARGV[1])
if not record then
    redis.call('HDEL', KEYS[2], ARGV[1])
    return 0
end
if ARGV[2] ~= '' then
    local decoded = cjson.decode(record)
    if decoded['_owner_token'] ~= ARGV[2] then
        return 0
    end
end
redis.call('HDEL', KEYS[1], ARGV[1])
redis.call('HDEL', KEYS[2], ARGV[1])
return 1
"""
    _OWNS_JOB_SCRIPT = """
local record = redis.call('HGET', KEYS[1], ARGV[1])
if not record then
    return 0
end
local decoded = cjson.decode(record)
if decoded['_owner_token'] == ARGV[2] then
    return 1
end
return 0
"""
    _RECOVER_JOB_SCRIPT = """
if redis.call('HEXISTS', KEYS[1], ARGV[1]) == 0 then
    return 0
end
local heartbeat = redis.call('HGET', KEYS[2], ARGV[1])
if ARGV[2] == '__missing__' then
    if heartbeat then
        return 0
    end
elseif not heartbeat or heartbeat ~= ARGV[2] then
    return 0
end
redis.call('HDEL', KEYS[1], ARGV[1])
redis.call('HDEL', KEYS[2], ARGV[1])
return 1
"""

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        key: str = "botjagwar:entry_translator:active_job_records",
        fallback: Optional[QueueCounter] = None,
    ) -> None:
        self._redis_client = redis_client or self._build_redis_client()
        self._key = key
        self._heartbeat_key = f"{key}:heartbeats"
        self._fallback = fallback or QueueCounter()
        self._using_fallback = False
        self._legacy_job_ids: List[str] = []
        self._legacy_job_ids_lock = threading.Lock()

    @property
    def source(self) -> str:
        """Return the active counter backend name."""
        return "local-fallback" if self._using_fallback else "redis"

    def increment(self) -> None:
        """Record an anonymous job for backward compatibility."""
        job_id = self.start_job("", "", time.time())
        with self._legacy_job_ids_lock:
            self._legacy_job_ids.append(job_id)

    def decrement(self) -> None:
        """Remove an anonymous job for backward compatibility."""
        with self._legacy_job_ids_lock:
            job_id = self._legacy_job_ids.pop() if self._legacy_job_ids else None
        if job_id:
            self.finish_job(job_id)

    def get(self) -> int:
        """Return the number of active Redis job records."""
        try:
            count = int(self._redis_client.hlen(self._key))
            self._using_fallback = False
            return count
        except (redis.RedisError, TypeError, ValueError, AttributeError) as exc:
            log.warning("Falling back to local job counter after Redis read failed: %s", exc)
            self._using_fallback = True
            return self._fallback.get()

    def start_job(
        self,
        title: str,
        language: str,
        started_at: float,
        job_id: Optional[str] = None,
    ) -> str:
        """Store an active job record in Redis, with local fallback."""
        job_id = job_id or str(uuid.uuid4())
        try:
            claimed = self._claim_redis_job(
                title,
                language,
                started_at,
                job_id,
                "",
            )
            if not claimed:
                raise RuntimeError(f"Active job {job_id} already exists.")
            self._using_fallback = False
            return job_id
        except (redis.RedisError, TypeError, ValueError, AttributeError) as exc:
            log.warning("Falling back to local job counter after Redis write failed: %s", exc)
            self._using_fallback = True
            return self._fallback.start_job(title, language, started_at, job_id)

    def claim_job(
        self,
        title: str,
        language: str,
        started_at: float,
        job_id: str,
        owner_token: str,
    ) -> bool:
        """Claim an authoritative Redis active record for a tracked job."""
        try:
            claimed = self._claim_redis_job(
                title,
                language,
                started_at,
                job_id,
                owner_token,
            )
            self._using_fallback = False
            return claimed
        except (redis.RedisError, TypeError, ValueError, AttributeError) as exc:
            self._using_fallback = False
            raise TranslationJobStoreError(
                "Redis could not claim the active translation job."
            ) from exc

    def _claim_redis_job(
        self,
        title: str,
        language: str,
        started_at: float,
        job_id: str,
        owner_token: str,
    ) -> bool:
        """Atomically create a Redis active record and initial heartbeat."""
        job = {
            "title": title,
            "language": language,
            "started_at": started_at,
        }
        if owner_token:
            job["_owner_token"] = owner_token
        return bool(
            self._redis_client.eval(
                self._CLAIM_JOB_SCRIPT,
                2,
                self._key,
                self._heartbeat_key,
                job_id,
                json.dumps(job),
                str(started_at),
            )
        )

    def touch_job(
        self,
        job_id: str,
        touched_at: float,
        owner_token: Optional[str] = None,
    ) -> bool:
        """Refresh an active Redis job heartbeat, with local fallback."""
        try:
            active = bool(
                self._redis_client.eval(
                    self._TOUCH_JOB_SCRIPT,
                    2,
                    self._key,
                    self._heartbeat_key,
                    job_id,
                    str(touched_at),
                    owner_token or "",
                )
            )
            self._using_fallback = False
            return active
        except (redis.RedisError, TypeError, ValueError, AttributeError) as exc:
            if owner_token is not None:
                self._using_fallback = False
                raise TranslationJobStoreError(
                    "Redis could not refresh the active translation job."
                ) from exc
            log.warning(
                "Falling back to local job heartbeat after Redis write failed: %s",
                exc,
            )
            self._using_fallback = True
            return self._fallback.touch_job(job_id, touched_at, owner_token)

    def owns_job(self, job_id: str, owner_token: str) -> bool:
        """Return whether Redis still assigns the active lease to this owner."""
        try:
            owned = bool(
                self._redis_client.eval(
                    self._OWNS_JOB_SCRIPT,
                    1,
                    self._key,
                    job_id,
                    owner_token,
                )
            )
            self._using_fallback = False
            return owned
        except (redis.RedisError, TypeError, ValueError, AttributeError) as exc:
            raise TranslationJobStoreError(
                "Redis could not verify the active translation job."
            ) from exc

    def finish_job(self, job_id: str, owner_token: Optional[str] = None) -> bool:
        """Remove a matching active job record from Redis or local fallback."""
        try:
            finished = bool(
                self._redis_client.eval(
                    self._FINISH_JOB_SCRIPT,
                    2,
                    self._key,
                    self._heartbeat_key,
                    job_id,
                    owner_token or "",
                )
            )
            self._using_fallback = False
            return finished
        except (redis.RedisError, TypeError, ValueError, AttributeError) as exc:
            log.warning("Falling back to local job counter after Redis delete failed: %s", exc)
            self._using_fallback = True
            return self._fallback.finish_job(job_id, owner_token)

    def recover_stale_jobs(
        self,
        timeout_seconds: float,
        now: float,
        protected_job_ids: Optional[set[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Delete Redis job records that have exceeded the configured timeout."""
        protected_job_ids = protected_job_ids or set()
        try:
            stale_candidates = []
            records = self._redis_client.hgetall(self._key)
            heartbeats = {
                self._decode_redis_value(raw_job_id): self._decode_redis_value(raw_time)
                for raw_job_id, raw_time in self._redis_client.hgetall(
                    self._heartbeat_key
                ).items()
            }
            for raw_job_id, raw_job in records.items():
                job_id = self._decode_redis_value(raw_job_id)
                job = json.loads(self._decode_redis_value(raw_job))
                job["job_id"] = job_id
                last_heartbeat = float(
                    heartbeats.get(job_id, job["started_at"])
                )
                if (
                    job_id not in protected_job_ids
                    and now - last_heartbeat >= timeout_seconds
                ):
                    stale_candidates.append(
                        (job, heartbeats.get(job_id, "__missing__"))
                    )
            stale_jobs = [
                job
                for job, observed_heartbeat in stale_candidates
                if self._redis_client.eval(
                    self._RECOVER_JOB_SCRIPT,
                    2,
                    self._key,
                    self._heartbeat_key,
                    job["job_id"],
                    observed_heartbeat,
                )
            ]
            self._using_fallback = False
            return stale_jobs
        except (redis.RedisError, TypeError, ValueError, KeyError, AttributeError) as exc:
            log.warning("Falling back to local job recovery after Redis read failed: %s", exc)
            self._using_fallback = True
            return self._fallback.recover_stale_jobs(
                timeout_seconds, now, protected_job_ids
            )

    @staticmethod
    def _decode_redis_value(value: Any) -> str:
        """Convert a Redis response value to text."""
        return value.decode() if isinstance(value, bytes) else str(value)

    @staticmethod
    def _build_redis_client() -> Any:
        """Build a Redis client from the repository configuration."""
        config = BotjagwarConfig()
        password = config.get("password", "redis") or None
        return redis.Redis(
            host=config.get("host", "redis"),
            port=6379,
            password=password,
            socket_timeout=3,
        )


class JobErrorStore:
    """Store recent job errors in Redis with local fallback."""

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        key: str = "botjagwar:entry_translator:recent_errors",
        max_entries: int = 25,
    ) -> None:
        self._redis_client = redis_client or RedisQueueCounter._build_redis_client()
        self._key = key
        self._max_entries = max_entries
        self._fallback_errors: List[Dict[str, str]] = []
        self._lock = threading.Lock()

    def record_error(self, error: Dict[str, str]) -> None:
        """Record a job error for health and diagnostics."""
        try:
            payload = json.dumps(error)
            self._redis_client.lpush(self._key, payload)
            self._redis_client.ltrim(self._key, 0, self._max_entries - 1)
        except redis.RedisError as exc:
            log.warning("Falling back to local job error store after Redis write failed: %s", exc)
            with self._lock:
                self._fallback_errors.insert(0, error)
                del self._fallback_errors[self._max_entries:]

    def recent_errors(self) -> List[Dict[str, str]]:
        """Return recent job errors."""
        try:
            raw_errors = self._redis_client.lrange(self._key, 0, self._max_entries - 1)
            return [json.loads(item) for item in raw_errors]
        except (redis.RedisError, json.JSONDecodeError, TypeError) as exc:
            log.warning("Falling back to local job error store after Redis read failed: %s", exc)
            with self._lock:
                return list(self._fallback_errors)


class RedisTranslationJobStore:
    """Authoritative Redis store for durable translation job records."""

    _DEFAULT_TTL_SECONDS = 24 * 60 * 60
    _PUT_OWNED_SCRIPT = """
local raw_job = redis.call('GET', KEYS[1])
if not raw_job then
    return -1
end
local decode_ok, current = pcall(cjson.decode, raw_job)
if not decode_ok or type(current) ~= 'table' then
    return -2
end
if current['_owner_token'] ~= ARGV[1] then
    return 0
end
if current['status'] == 'done' or current['status'] == 'error' then
    return 0
end
redis.call('SET', KEYS[1], ARGV[2], 'EX', ARGV[3])
return 1
"""

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        key_prefix: str = "botjagwar:entry_translator:translation_jobs",
        ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    ) -> None:
        if ttl_seconds < 1:
            raise ValueError("ttl_seconds must be at least 1")
        self._redis_client = (
            redis_client
            if redis_client is not None
            else RedisQueueCounter._build_redis_client()
        )
        self._key_prefix = key_prefix
        self._ttl_seconds = ttl_seconds

    def put(self, job: Dict[str, Any]) -> None:
        """Store a job as JSON and refresh its retention period."""
        job_id, payload = self._serialise_job(job)
        try:
            self._redis_client.set(
                self._job_key(job_id), payload, ex=self._ttl_seconds
            )
        except redis.RedisError as exc:
            raise TranslationJobStoreError(
                "The persistent translation job store could not be written."
            ) from exc

    def create(self, job: Dict[str, Any]) -> bool:
        """Atomically store a new job unless its request ID already exists."""
        job_id, payload = self._serialise_job(job)
        try:
            return bool(
                self._redis_client.set(
                    self._job_key(job_id),
                    payload,
                    ex=self._ttl_seconds,
                    nx=True,
                )
            )
        except redis.RedisError as exc:
            raise TranslationJobStoreError(
                "The persistent translation job store could not be written."
            ) from exc

    def put_owned(self, job: Dict[str, Any], owner_token: str) -> bool:
        """Update an active job only while its owner token remains authoritative."""
        job_id, payload = self._serialise_job(job)
        try:
            result = int(
                self._redis_client.eval(
                    self._PUT_OWNED_SCRIPT,
                    1,
                    self._job_key(job_id),
                    owner_token,
                    payload,
                    self._ttl_seconds,
                )
            )
        except redis.RedisError as exc:
            raise TranslationJobStoreError(
                "The persistent translation job store could not be written."
            ) from exc
        if result in (-1, -2):
            raise TranslationJobStoreError(
                "The persistent translation job store contains invalid data."
            )
        return result == 1

    @staticmethod
    def _serialise_job(job: Dict[str, Any]) -> Tuple[str, str]:
        """Validate and serialize a translation job for Redis."""
        try:
            job_id = job["job_id"]
            if not isinstance(job_id, str) or not job_id:
                raise ValueError("job_id must be a non-empty string")
            payload = json.dumps(job, allow_nan=False)
        except (KeyError, TypeError, ValueError) as exc:
            raise TranslationJobStoreError(
                "The translation job record is invalid."
            ) from exc
        return job_id, payload

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Return a durable translation job, if it exists."""
        try:
            raw_job = self._redis_client.get(self._job_key(job_id))
        except redis.RedisError as exc:
            raise TranslationJobStoreError(
                "The persistent translation job store could not be read."
            ) from exc
        if raw_job is None:
            return None
        try:
            decoded = raw_job.decode() if isinstance(raw_job, bytes) else str(raw_job)
            job = json.loads(decoded)
        except (json.JSONDecodeError, TypeError, UnicodeDecodeError) as exc:
            raise TranslationJobStoreError(
                "The persistent translation job store contains invalid data."
            ) from exc
        if not isinstance(job, dict):
            raise TranslationJobStoreError(
                "The persistent translation job store contains invalid data."
            )
        job["job_id"] = job_id
        return job

    def _job_key(self, job_id: str) -> str:
        """Return the Redis key for one translation job."""
        return f"{self._key_prefix}:{job_id}"


class RedisCheckJobStore:
    """Redis-backed persistent store for page check jobs.

    Job records are stored as JSON values in a single Redis hash so that they
    survive service restarts and are shared between entry translator
    instances. Redis is authoritative: operations fail instead of falling back
    to process-local memory, which would make jobs disappear behind the
    load-balanced entry translator service.
    """

    _COMPARE_AND_SET_SCRIPT = """
local raw_current = redis.call('HGET', KEYS[1], ARGV[1])
if not raw_current then
    return 0
end
if raw_current ~= ARGV[2] then
    return -1
end
redis.call('HSET', KEYS[1], ARGV[1], ARGV[3])
return 1
"""
    _PUT_MANY_BOUNDED_SCRIPT = """
local maximum = tonumber(ARGV[1])
local maximum_unfinished = tonumber(ARGV[2])
local incoming_count = (#ARGV - 2) / 2

local records = redis.call('HGETALL', KEYS[1])
local terminal = {}
local unfinished_count = 0
for index = 1, #records, 2 do
    local decoded, job = pcall(cjson.decode, records[index + 1])
    if not decoded or type(job) ~= 'table' or type(job.created_at) ~= 'number' then
        return -2
    end
    if job.status == 'pending' or job.status == 'running' then
        unfinished_count = unfinished_count + 1
    elseif job.status == 'done' or job.status == 'error' then
        local review_state = job.review_queue_state
        if review_state ~= 'pending' and review_state ~= 'failed'
            and review_state ~= 'publishing' then
            table.insert(terminal, {
                id = records[index],
                created_at = job.created_at
            })
        end
    else
        return -2
    end
end
if unfinished_count + incoming_count > maximum_unfinished then
    return -1
end

local record_count = (#records / 2) + incoming_count
local overflow = math.max(record_count - maximum, 0)
if overflow > #terminal then
    return -3
end

for index = 3, #ARGV, 2 do
    redis.call('HSET', KEYS[1], ARGV[index], ARGV[index + 1])
end

if record_count <= maximum then
    return record_count
end
table.sort(terminal, function(left, right)
    if left.created_at == right.created_at then
        return left.id < right.id
    end
    return left.created_at < right.created_at
end)

for index = 1, overflow do
    redis.call('HDEL', KEYS[1], terminal[index].id)
end
return record_count - overflow
"""
    _REMOVE_TERMINAL_SCRIPT = """
local raw_job = redis.call('HGET', KEYS[1], ARGV[1])
if not raw_job then
    return 0
end
local decode_ok, job = pcall(cjson.decode, raw_job)
if not decode_ok or type(job) ~= 'table' then
    return -1
end
local review_state = job['review_queue_state']
if (job['status'] == 'done' or job['status'] == 'error')
    and review_state ~= 'pending' and review_state ~= 'failed'
    and review_state ~= 'publishing' then
    return redis.call('HDEL', KEYS[1], ARGV[1])
end
return 0
"""

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        key: str = "botjagwar:entry_translator:page_check_jobs",
    ) -> None:
        self._redis_client = (
            redis_client
            if redis_client is not None
            else RedisQueueCounter._build_redis_client()
        )
        self._key = key

    def put(self, job: Dict[str, Any]) -> bool:
        """Update an existing job while preserving its immutable review event."""
        job_id = job.get("job_id")
        payload = self._serialise_job(job)
        incoming = self._deserialise_job(str(job_id), payload)
        observed: Dict[str, Any] = {}

        def update(current: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            observed.clear()
            observed.update(current)
            if isinstance(current.get("execution_token"), str) and current.get(
                "execution_token"
            ) != incoming.get("execution_token"):
                return None
            replacement = dict(incoming)
            if isinstance(current.get("review_message"), dict) or current.get(
                "review_queue_state"
            ) == "invalid":
                self._copy_review_fields(current, replacement)
            return replacement

        stored = self._update_existing(str(job_id), update)
        if stored is None:
            stored = observed
        accepted = bool(stored) and stored.get("execution_token") == job.get(
            "execution_token"
        )
        self._copy_review_fields(stored, job)
        return accepted

    @staticmethod
    def _copy_review_fields(source: Dict[str, Any], target: Dict[str, Any]) -> None:
        """Copy review lifecycle fields without rebuilding immutable evidence."""
        for field in (
            "review_queue_state",
            "review_event_id",
            "review_queue_error",
            "review_message",
            "review_queue_claim",
            "review_queue_claimed_at",
            "review_queue_attempts",
            "review_queue_next_attempt_at",
        ):
            if field in source:
                target[field] = source[field]
            else:
                target.pop(field, None)

    def _update_existing(
        self,
        job_id: str,
        update: Callable[[Dict[str, Any]], Optional[Dict[str, Any]]],
    ) -> Optional[Dict[str, Any]]:
        """Atomically replace one existing record without Lua JSON conversion."""
        for _attempt in range(8):
            try:
                raw_job = self._redis_client.hget(self._key, job_id)
            except redis.RedisError as exc:
                raise CheckJobStoreError(
                    "The persistent page check job store could not be read."
                ) from exc
            if raw_job is None:
                return None
            current = self._deserialise_job(job_id, raw_job)
            replacement = update(current)
            if replacement is None:
                return None
            payload = self._serialise_job(replacement)
            try:
                result = int(
                    self._redis_client.eval(
                        self._COMPARE_AND_SET_SCRIPT,
                        1,
                        self._key,
                        job_id,
                        raw_job,
                        payload,
                    )
                )
            except redis.RedisError as exc:
                raise CheckJobStoreError(
                    "The persistent page check job store could not be written."
                ) from exc
            if result == 1:
                return self._deserialise_job(job_id, payload)
            if result == 0:
                return None
        raise CheckJobStoreError(
            "The persistent page check job changed too often to update safely."
        )

    def put_many(self, jobs: List[Dict[str, Any]]) -> None:
        """Store several new job records in one Redis operation."""
        if not jobs:
            return
        payloads = {job["job_id"]: self._serialise_job(job) for job in jobs}
        try:
            self._redis_client.hset(self._key, mapping=payloads)
        except redis.RedisError as exc:
            raise CheckJobStoreError(
                "The persistent page check job store could not be written."
            ) from exc

    def put_many_bounded(
        self,
        jobs: List[Dict[str, Any]],
        maximum_jobs: int,
        maximum_unfinished_jobs: int,
    ) -> bool:
        """Atomically enforce capacity, store jobs, and trim terminal history."""
        if not jobs:
            return True
        arguments: List[Any] = [maximum_jobs, maximum_unfinished_jobs]
        for job in jobs:
            arguments.extend([job["job_id"], self._serialise_job(job)])
        try:
            result = int(
                self._redis_client.eval(
                    self._PUT_MANY_BOUNDED_SCRIPT,
                    1,
                    self._key,
                    *arguments,
                )
            )
        except redis.RedisError as exc:
            raise CheckJobStoreError(
                "The persistent page check job store could not be written."
            ) from exc
        if result == -2:
            raise CheckJobStoreError(
                "The persistent page check job store contains invalid data."
            )
        return result >= 0

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Return a job record from Redis, if any."""
        try:
            raw_job = self._redis_client.hget(self._key, job_id)
        except redis.RedisError as exc:
            raise CheckJobStoreError(
                "The persistent page check job store could not be read."
            ) from exc
        if raw_job is None:
            return None
        return self._deserialise_job(job_id, raw_job)

    def claim_stale_job(
        self,
        job_id: str,
        observed_last_updated_at: float,
        now: float,
        timeout_seconds: float,
        execution_token: str,
    ) -> Optional[Dict[str, Any]]:
        """Atomically fence and claim one unchanged stale page-check job."""
        def update(job: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            last_updated_at = job.get("last_updated_at")
            if (
                job.get("status") not in {"pending", "running"}
                or not isinstance(last_updated_at, (int, float))
                or isinstance(last_updated_at, bool)
                or last_updated_at != observed_last_updated_at
                or now - last_updated_at <= timeout_seconds
            ):
                return None
            attempts = job.get("attempts", 0)
            if not isinstance(attempts, (int, float)) or isinstance(attempts, bool):
                raise CheckJobStoreError(
                    "The persistent page check job store contains invalid data."
                )
            job["attempts"] = int(attempts) + 1
            job["status"] = "pending"
            job["progress"] = 0
            job["error"] = None
            job["last_updated_at"] = now
            job["execution_token"] = execution_token
            return job

        return self._update_existing(job_id, update)

    def claim_review_handoff(
        self,
        job_id: str,
        claim_token: str,
        now: float,
        lease_seconds: float,
    ) -> Optional[Dict[str, Any]]:
        """Atomically lease one pending or abandoned review handoff."""
        def update(job: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            if not _review_handoff_is_claimable(job, now, lease_seconds):
                return None
            attempts = job.get("review_queue_attempts", 0)
            if not isinstance(attempts, (int, float)) or isinstance(attempts, bool):
                raise CheckJobStoreError(
                    "The persistent page check job store contains invalid data."
                )
            job["review_queue_state"] = "publishing"
            job["review_queue_claim"] = claim_token
            job["review_queue_claimed_at"] = now
            job["review_queue_attempts"] = int(attempts) + 1
            return job

        return self._update_existing(job_id, update)

    def finish_review_handoff(
        self,
        job_id: str,
        claim_token: str,
        state: str,
        event_id: str,
        error: Optional[str],
    ) -> bool:
        """Atomically finish a leased review handoff for its current owner."""
        if state not in {"queued", "failed", "invalid"}:
            raise ValueError("Review handoff state must be queued, failed, or invalid.")
        now = time.time()

        def update(job: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            if (
                job.get("review_queue_state") != "publishing"
                or job.get("review_queue_claim") != claim_token
            ):
                return None
            job["review_queue_state"] = state
            job["review_event_id"] = event_id
            job["review_queue_error"] = error
            job.pop("review_queue_claim", None)
            job.pop("review_queue_claimed_at", None)
            if state == "failed":
                attempts = job.get("review_queue_attempts", 1)
                if not isinstance(attempts, (int, float)) or isinstance(attempts, bool):
                    raise CheckJobStoreError(
                        "The persistent page check job store contains invalid data."
                    )
                exponent = min(max(int(attempts) - 1, 0), 6)
                job["review_queue_next_attempt_at"] = now + 5 * (2**exponent)
            else:
                job.pop("review_queue_next_attempt_at", None)
            return job

        return self._update_existing(job_id, update) is not None

    def touch_execution(
        self, job_id: str, execution_token: str, touched_at: float
    ) -> bool:
        """Refresh an active job only while its execution token owns it."""
        def update(job: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            if (
                job.get("status") not in {"pending", "running"}
                or job.get("execution_token") != execution_token
            ):
                return None
            job["last_updated_at"] = touched_at
            return job

        return self._update_existing(job_id, update) is not None

    def all(self) -> List[Dict[str, Any]]:
        """Return every job record from Redis."""
        try:
            raw_jobs = self._redis_client.hgetall(self._key)
        except redis.RedisError as exc:
            raise CheckJobStoreError(
                "The persistent page check job store could not be read."
            ) from exc
        return [
            self._deserialise_job(self._decode_redis_value(raw_job_id), raw_job)
            for raw_job_id, raw_job in raw_jobs.items()
        ]

    def remove(self, job_id: str) -> None:
        """Remove a job record from Redis."""
        try:
            self._redis_client.hdel(self._key, job_id)
        except redis.RedisError as exc:
            raise CheckJobStoreError(
                "The persistent page check job store could not be updated."
            ) from exc

    def remove_terminal(self, job_id: str) -> bool:
        """Atomically remove a terminal job without an unfinished review handoff."""
        try:
            result = int(
                self._redis_client.eval(
                    self._REMOVE_TERMINAL_SCRIPT,
                    1,
                    self._key,
                    job_id,
                )
            )
        except redis.RedisError as exc:
            raise CheckJobStoreError(
                "The persistent page check job store could not be updated."
            ) from exc
        if result == -1:
            raise CheckJobStoreError(
                "The persistent page check job store contains invalid data."
            )
        return result == 1

    @staticmethod
    def _serialise_job(job: Dict[str, Any]) -> str:
        """Return a strict JSON representation of a page-check job."""
        try:
            job_id = job["job_id"]
            if not isinstance(job_id, str) or not job_id:
                raise ValueError("job_id must be a non-empty string")
            return json.dumps(job, allow_nan=False)
        except (KeyError, TypeError, ValueError) as exc:
            raise CheckJobStoreError("The page check job record is invalid.") from exc

    @classmethod
    def _deserialise_job(cls, job_id: str, raw_job: Any) -> Dict[str, Any]:
        """Decode and validate a page-check job read from Redis."""
        try:
            job = json.loads(cls._decode_redis_value(raw_job))
        except (json.JSONDecodeError, TypeError, UnicodeDecodeError) as exc:
            raise CheckJobStoreError(
                "The persistent page check job store contains invalid data."
            ) from exc
        if not isinstance(job, dict):
            raise CheckJobStoreError(
                "The persistent page check job store contains invalid data."
            )
        job["job_id"] = job_id
        return _normalise_check_job(job)

    @staticmethod
    def _decode_redis_value(value: Any) -> str:
        """Convert a Redis response value to text."""
        return value.decode() if isinstance(value, bytes) else str(value)


class EntryTranslatorService:
    """Service layer for Wiktionary entry translation operations."""

    _DEGRADED_JOB_DURATION_SECONDS = 300.0
    _EMA_ALPHA = 0.2

    _MAX_UNFINISHED_CHECK_JOBS = 100

    _STALE_CHECK_JOB_TIMEOUT_SECONDS = 900.0
    _CHECK_JOB_MAX_ATTEMPTS = 3

    _STALE_RECOVERY_INTERVAL_SECONDS = 30.0
    _REVIEW_HANDOFF_RECOVERY_BATCH_SIZE = 20
    _REVIEW_HANDOFF_LEASE_SECONDS = 120.0
    _TRANSLATION_JOB_MESSAGES = {
        "queued": "Translation job queued.",
        "loading_source": "Loading the source page.",
        "translating": "Translating the source page.",
        "queueing_publication": "Queueing translated entries for publication.",
        "prefiltering_publication": "Checking the translated page before publication.",
        "publication_queued": "Translated entries were queued for publication.",
        "publication_filtered": "The translated page did not pass the publication prefilter.",
        "completed": "Translation job completed.",
        "failed": "Translation job failed.",
    }
    _MAX_PREVIEW_DESCENDANT_BYTES = 1_000_000
    _MAX_PREVIEW_DESCENDANT_DEPTH = 32
    _MAX_PREVIEW_DESCENDANT_NODES = 2_000
    _MAX_PAGE_SNAPSHOT_BYTES = 1_000_000
    _SNAPSHOT_LANGUAGES = frozenset({"en", "mg"})

    def __init__(
        self,
        translation: Translation,
        publisher: Optional[WiktionaryRabbitMqPublisher] = None,
        queue_counter: Optional[JobCounter] = None,
        job_error_store: Optional[JobErrorStore] = None,
        get_page_func: Optional[Callable[[str, str], Optional[Page]]] = None,
        processor_factory: Optional[Callable[[str], Any]] = None,
        page_check_service: Optional["PageCheckService"] = None,
        page_check_publisher: Optional[WiktionaryRabbitMqPublisher] = None,
        task_runner: Optional[Callable[[Callable[[], None]], Any]] = None,
        check_job_store: Optional[RedisCheckJobStore] = None,
        page_checker_settings_store: Optional[PageCheckerSettingsStore] = None,
        definition_translation_settings_store: Optional[
            DefinitionTranslationSettingsStore
        ] = None,
        stale_job_timeout_seconds: float = _DEGRADED_JOB_DURATION_SECONDS,
        max_async_workers: int = 4,
        max_pending_jobs: int = 21,
        max_check_workers: int = 2,
        max_check_jobs_kept: int = 100_000,
        translation_job_store: Optional[RedisTranslationJobStore] = None,
        page_check_review_queue: Optional[RabbitMqPageCheckReviewQueue] = None,
    ) -> None:
        if max_async_workers < 1:
            raise ValueError("max_async_workers must be at least 1")
        if max_pending_jobs < 0:
            raise ValueError("max_pending_jobs must not be negative")
        if max_check_workers < 1:
            raise ValueError("max_check_workers must be at least 1")
        if max_check_jobs_kept < 1:
            raise ValueError("max_check_jobs_kept must be at least 1")
        if not math.isfinite(stale_job_timeout_seconds) or stale_job_timeout_seconds <= 0:
            raise ValueError("stale_job_timeout_seconds must be a positive finite number")

        self._translation = translation
        self._publisher = publisher
        self._queue_counter = queue_counter or RedisQueueCounter()
        self._job_error_store = job_error_store or JobErrorStore()
        self._translation_job_store = (
            translation_job_store
            if translation_job_store is not None
            else RedisTranslationJobStore()
        )
        self._get_page = get_page_func or self._default_get_page
        self._processor_factory = (
            processor_factory or entryprocessor.WiktionaryProcessorFactory.create
        )
        self._page_check_service = page_check_service
        self._page_check_publisher = page_check_publisher
        self._page_check_review_queue = page_check_review_queue
        self._task_runner = task_runner
        self._check_job_store = check_job_store or RedisCheckJobStore()
        self._max_check_jobs_kept = max_check_jobs_kept
        self._page_checker_settings_store = (
            page_checker_settings_store
            if page_checker_settings_store is not None
            else PageCheckerSettingsStore()
        )
        self._definition_translation_settings_store = (
            definition_translation_settings_store
            if definition_translation_settings_store is not None
            else DefinitionTranslationSettingsStore()
        )
        self._executor = (
            None
            if task_runner is not None
            else ThreadPoolExecutor(
                max_workers=max_async_workers,
                thread_name_prefix="entry-translator",
            )
        )
        self._max_async_workers = max_async_workers
        self._job_capacity = max_async_workers + max_pending_jobs
        self._job_slots = threading.BoundedSemaphore(self._job_capacity)
        self._executor_state_lock = threading.Lock()
        self._accepting_async_jobs = True
        self._process_admitted_jobs = 0
        self._process_running_jobs = 0
        self._rejected_job_count = 0
        self._completed_job_count = 0
        self._failed_job_count = 0
        self._local_job_ids: set[str] = set()
        self._stale_job_timeout_seconds = stale_job_timeout_seconds
        self._publish_lock = threading.Lock()
        self._avg_duration_lock = threading.Lock()
        self._average_job_duration_seconds: Optional[float] = None
        self._last_stale_recovery = 0.0
        self._last_check_recovery = 0.0
        self._stale_recovery_lock = threading.Lock()
        self._check_recovery_running = False
        self._check_jobs_lock = threading.Lock()
        self._check_executor = (
            None
            if task_runner is not None
            else ThreadPoolExecutor(
                max_workers=max_check_workers,
                thread_name_prefix="page-check",
            )
        )

    @contextmanager
    def _time_operation(self, operation: str, **context: Any) -> Iterator[None]:
        """Log the elapsed time for an operation.

        Args:
            operation: Name of the operation being timed.
            **context: Additional context values to include in the log entry.
        """
        start = time.monotonic()
        try:
            yield
        finally:
            elapsed_ms = (time.monotonic() - start) * 1000
            log.info(
                "Operation '%s' took %.2f ms. Context: %s",
                operation,
                elapsed_ms,
                context,
            )

    def health_status(self) -> Dict[str, Any]:
        """Return service health data."""
        self._maybe_recover_stale_jobs()
        self._schedule_stale_check_recovery()
        jobs = self._queue_counter.get()
        average_duration = self._get_average_job_duration()
        recent_errors = self.recent_job_errors()
        executor_status = self._executor_status()
        base_status = {
            "jobs": jobs,
            "counter_source": self._queue_counter.source,
            "average_job_duration_seconds": average_duration,
            "recent_job_error_count": len(recent_errors),
            "recent_job_errors": recent_errors[:5],
            **executor_status,
        }
        if not executor_status["accepting_async_jobs"]:
            return base_status | {
                "status": "degraded",
                "message": "The service is not accepting asynchronous jobs.",
            }
        if executor_status["available_job_slots"] == 0:
            return base_status | {
                "status": "degraded",
                "message": "Asynchronous translation capacity is full.",
            }
        if jobs >= 25:
            return base_status | {
                "status": "degraded",
                "message": "High job queue length (over 25) indicates potential overload.",
            }
        if (
            average_duration is not None
            and average_duration > self._DEGRADED_JOB_DURATION_SECONDS
        ):
            return base_status | {
                "status": "degraded",
                "message": "Average job duration exceeds 5 minutes.",
            }
        if recent_errors:
            return base_status | {
                "status": "degraded",
                "message": "Recent translation job errors were recorded.",
            }
        return base_status | {
            "status": "healthy",
            "message": "Service is operating normally.",
        }

    def job_count(self) -> int:
        """Return the current job count."""
        self._maybe_recover_stale_jobs()
        return self._queue_counter.get()

    def recent_job_errors(self) -> List[Dict[str, str]]:
        """Return recent background job errors."""
        return self._job_error_store.recent_errors()

    def enqueue_translation_job(
        self,
        language: str,
        title: str,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Queue a background translation job and return its pending record."""
        if not self._publisher:
            raise ServiceError(
                "Translation queue is unavailable because the publisher is not configured.",
                status_code=503,
            )

        job_id = self._normalise_translation_request_id(request_id)
        if job_id is not None:
            existing_job = self._get_existing_translation_request(
                job_id,
                language,
                title,
            )
            if existing_job is not None:
                return existing_job
        else:
            job_id = str(uuid.uuid4())
        owner_token = str(uuid.uuid4())

        self._reserve_job_slot()
        cleanup_lock = threading.Lock()
        cleanup_complete = False
        task_started = False
        owns_active_job = False
        heartbeat_stop = threading.Event()
        heartbeat_thread: Optional[threading.Thread] = None

        def stop_heartbeat() -> None:
            """Stop this job's liveness heartbeat before removing its record."""
            heartbeat_stop.set()
            if (
                heartbeat_thread is not None
                and heartbeat_thread.is_alive()
                and heartbeat_thread is not threading.current_thread()
            ):
                heartbeat_thread.join(timeout=1)

        def cleanup(failed: bool = False) -> None:
            """Release this job's process-local capacity exactly once."""
            nonlocal cleanup_complete
            stop_heartbeat()
            with cleanup_lock:
                if cleanup_complete:
                    return
                cleanup_complete = True
            if owns_active_job:
                with self._executor_state_lock:
                    self._local_job_ids.discard(job_id)
            self._finish_process_job(task_started, failed)

        def assert_publication_lease() -> None:
            """Fence the external publication side effect at its final boundary."""
            if not self._queue_counter.touch_job(
                job_id,
                time.time(),
                owner_token,
            ):
                raise TranslationJobLeaseLost(
                    "The translation job is no longer authorized to publish."
                )

        def filter_publication(page_title: str, content: str) -> bool:
            """Allow only candidates marked good when the prefilter is enabled."""
            try:
                enabled = (
                    self._page_checker_settings_store.get().translation_prefilter_enabled
                )
            except PageCheckerSettingsStoreError as exc:
                raise self._page_checker_settings_unavailable(exc) from exc
            if not enabled:
                return True
            self._update_translation_job(
                job,
                "running",
                "prefiltering_publication",
                owner_token,
            )
            page_checker = self._get_page_check_service()
            result = page_checker.check_page(
                "mg",
                page_title,
                candidate_content=content,
                repair=False,
            )
            return result.status == "good"

        try:
            publish_unlocked = self._publisher.publish_to_wiktionary(
                self._translation,
                publication_guard=assert_publication_lease,
                publication_filter=filter_publication,
            )
        except Exception:
            cleanup(failed=True)
            raise

        created_at = time.time()
        try:
            claimed = self._queue_counter.claim_job(
                title,
                language,
                created_at,
                job_id,
                owner_token,
            )
        except TranslationJobStoreError as exc:
            cleanup(failed=True)
            raise self._translation_job_store_unavailable(exc) from exc
        except Exception:
            cleanup(failed=True)
            raise
        if not claimed:
            try:
                existing_job = self._get_existing_translation_request(
                    job_id,
                    language,
                    title,
                )
            finally:
                cleanup()
            if existing_job is not None:
                return existing_job
            raise ServiceError(
                "The translation request is already being accepted.",
                status_code=503,
                headers={"Retry-After": "1"},
            )

        owns_active_job = True
        with self._executor_state_lock:
            self._local_job_ids.add(job_id)
        job: Dict[str, Any] = {
            "job_id": job_id,
            "language": language,
            "title": title,
            "status": "pending",
            "stage": "queued",
            "publication_state": "not_queued",
            "created_at": created_at,
            "last_updated_at": created_at,
            "result": None,
            "error": None,
            "message": self._TRANSLATION_JOB_MESSAGES["queued"],
            "_owner_token": owner_token,
        }
        initial_job = self._public_translation_job(job)
        try:
            created = self._translation_job_store.create(job)
        except TranslationJobStoreError as exc:
            try:
                self._queue_counter.finish_job(job_id, owner_token)
            finally:
                cleanup(failed=True)
            raise self._translation_job_store_unavailable(exc) from exc
        if not created:
            try:
                existing_job = self._get_existing_translation_request(
                    job_id,
                    language,
                    title,
                )
            finally:
                self._queue_counter.finish_job(job_id, owner_token)
                cleanup()
            if existing_job is None:
                raise ServiceError(
                    "Translation job history is temporarily unavailable.",
                    status_code=503,
                )
            return existing_job

        try:
            heartbeat_thread = threading.Thread(
                target=self._heartbeat_translation_job,
                args=(job_id, owner_token, heartbeat_stop),
                name=f"translation-job-heartbeat-{job_id}",
                daemon=True,
            )
            heartbeat_thread.start()
        except Exception:
            job["error"] = "The translation job could not be registered as active."
            try:
                self._update_translation_job(
                    job,
                    "error",
                    "failed",
                    owner_token,
                    require_active=False,
                )
            except TranslationJobStoreError:
                log.exception(
                    "Unable to persist activation failure for translation job %s.",
                    job_id,
                )
            try:
                self._queue_counter.finish_job(job_id, owner_token)
            finally:
                cleanup(failed=True)
            raise

        def publish_locked(page_title: str, entries: List[Entry]) -> None:
            """Queue publication under the existing serialization lock."""
            with self._publish_lock:
                self._update_translation_job(
                    job,
                    "running",
                    "queueing_publication",
                    owner_token,
                )
                queued = publish_unlocked(page_title, entries)
            if queued is False:
                job["publication_state"] = "filtered_out"
                self._update_translation_job(
                    job,
                    "running",
                    "publication_filtered",
                    owner_token,
                )
                return
            job["publication_state"] = "queued"
            self._update_translation_job(
                job,
                "running",
                "publication_queued",
                owner_token,
            )

        def task() -> None:
            """Run the translation job and publish results."""
            nonlocal task_started
            task_started = True
            self._mark_job_running()
            start_time = time.monotonic()
            failed = False
            terminal_state_persisted = False
            try:
                self._update_translation_job(
                    job,
                    "running",
                    "loading_source",
                    owner_token,
                )
                page, _content = self._fetch_page(title, language)
                self._update_translation_job(
                    job,
                    "running",
                    "translating",
                    owner_token,
                )
                result = self._translation.process_wiktionary_wiki_page(
                    page, custom_publish_function=publish_locked
                )
                serialised_result = self._serialise_translation_result(
                    result, title, language
                )
                if self._is_error_result(result):
                    failed = True
                    self._record_job_error(
                        "Translation job finished with an error result.",
                        result,
                        job_id=job_id,
                        title=title,
                        language=language,
                    )
                    job["result"] = serialised_result
                    job["error"] = str(
                        serialised_result.get("message")
                        or "Translation job finished with an error result."
                    )
                    self._update_translation_job(
                        job,
                        "error",
                        "failed",
                        owner_token,
                    )
                    terminal_state_persisted = True
                else:
                    if job["publication_state"] == "queued":
                        serialised_result = self._normalise_queued_translation_result(
                            serialised_result
                        )
                    elif job["publication_state"] == "filtered_out":
                        serialised_result = self._normalise_filtered_translation_result(
                            serialised_result
                        )
                    job["result"] = serialised_result
                    job["error"] = None
                    self._update_translation_job(
                        job,
                        "done",
                        "completed",
                        owner_token,
                    )
                    terminal_state_persisted = True
            except Exception as exc:
                failed = True
                self._record_job_error(
                    "Translation job failed during processing.",
                    exc,
                    job_id=job_id,
                    title=title,
                    language=language,
                )
                job["result"] = None
                job["error"] = str(exc)
                try:
                    self._update_translation_job(
                        job,
                        "error",
                        "failed",
                        owner_token,
                    )
                    terminal_state_persisted = True
                except TranslationJobStoreError:
                    log.exception(
                        "Unable to persist failure for translation job %s.", job_id
                    )
            finally:
                duration_seconds = time.monotonic() - start_time
                self._record_job_duration(duration_seconds)
                stop_heartbeat()
                try:
                    if terminal_state_persisted:
                        self._queue_counter.finish_job(job_id, owner_token)
                    else:
                        log.error(
                            "Keeping active record for translation job %s until stale recovery.",
                            job_id,
                        )
                finally:
                    cleanup(failed=failed)

        try:
            submitted_task = self._run_task(task)
            if isinstance(submitted_task, Future):
                def cleanup_cancelled(future: Future[Any]) -> None:
                    """Clean up a queued job canceled before its task starts."""
                    if not future.cancelled():
                        return
                    cancellation_message = (
                        "Translation job was cancelled before it started."
                    )
                    job["result"] = None
                    job["error"] = cancellation_message
                    terminal_state_persisted = False
                    try:
                        self._update_translation_job(
                            job,
                            "error",
                            "failed",
                            owner_token,
                        )
                        terminal_state_persisted = True
                    except TranslationJobStoreError:
                        log.exception(
                            "Unable to persist cancellation for translation job %s.",
                            job_id,
                        )
                    self._record_job_error(
                        "Translation job was cancelled before execution.",
                        RuntimeError(cancellation_message),
                        job_id=job_id,
                        title=title,
                        language=language,
                    )
                    stop_heartbeat()
                    try:
                        if terminal_state_persisted:
                            self._queue_counter.finish_job(job_id, owner_token)
                    finally:
                        cleanup(failed=True)

                submitted_task.add_done_callback(cleanup_cancelled)
        except Exception as exc:
            log.exception("Unable to start translation job for %s (%s).", title, language)
            submission_message = "The translation job could not be started."
            job["result"] = None
            job["error"] = submission_message
            terminal_state_persisted = False
            try:
                self._update_translation_job(
                    job,
                    "error",
                    "failed",
                    owner_token,
                )
                terminal_state_persisted = True
            except TranslationJobStoreError:
                log.exception(
                    "Unable to persist submission failure for translation job %s.",
                    job_id,
                )
            self._record_job_error(
                submission_message,
                exc,
                job_id=job_id,
                title=title,
                language=language,
            )
            stop_heartbeat()
            try:
                if terminal_state_persisted:
                    self._queue_counter.finish_job(job_id, owner_token)
            finally:
                cleanup(failed=True)
            raise
        return initial_job

    def get_translation_job(self, language: str, job_id: str) -> Dict[str, Any]:
        """Return a durable translation job scoped to its source language."""
        try:
            job = self._translation_job_store.get(job_id)
        except TranslationJobStoreError as exc:
            raise self._translation_job_store_unavailable(exc) from exc
        if job is None or job.get("language") != language:
            raise ServiceError("Unknown translation job.", status_code=404)
        job = self._recover_unleased_translation_job(job)
        return self._public_translation_job(job)

    def translate_page_sync(self, language: str, title: str) -> Dict[str, Any]:
        """Translate a page synchronously."""
        with self._time_operation("translate_page_sync", language=language, title=title):
            page, content = self._fetch_page(title, language)
            try:
                result = self._translation.process_wiktionary_wiki_page(page)
            except Exception as exc:
                raise ServiceError(
                    "Failed to translate the requested page.",
                    status_code=500,
                    details={"error": str(exc), "type": type(exc).__name__},
                ) from exc

            serialised_result = self._serialise_translation_result(result, title, language)
            if self._is_error_result(result):
                self._record_job_error(
                    "Synchronous translation failed.",
                    result,
                )
                raise ServiceError(
                    "Failed to translate the requested page.",
                    status_code=500,
                    details=serialised_result,
                )

            return serialised_result

    def get_translations(self, language: str, pagename: str) -> List[Dict[str, Any]]:
        """Fetch translation data for a Wiktionary page."""
        page, content = self._fetch_page(pagename, language)
        processor = self._build_processor(language, page, content)
        try:
            translations = self._translation.translate_wiktionary_page(processor)
        except Exception as exc:
            raise ServiceError(
                "Failed to retrieve translations for the requested page.",
                status_code=500,
                details={"error": str(exc), "type": type(exc).__name__},
            ) from exc
        return [translation.serialise() for translation in translations]

    def get_processed_page(self, language: str, pagename: str) -> List[Dict[str, Any]]:
        """Return processed Wiktionary data including entries and translations."""
        with self._time_operation("get_processed_page", language=language, pagename=pagename):
            page, content = self._fetch_page(pagename, language)
            processor = self._build_processor(language, page, content)
            processor.process(page)

            with self._time_operation("get_all_entries", language=language, pagename=pagename):
                entries = processor.get_all_entries(
                    get_additional_data=True, cleanup_definitions=True, advanced=True
                )
            sections: List[Dict[str, Any]] = []
            remaining_descendant_bytes = self._MAX_PREVIEW_DESCENDANT_BYTES
            remaining_descendant_nodes = self._MAX_PREVIEW_DESCENDANT_NODES
            for entry in entries:
                section = self._build_entry_section(
                    entry,
                    processor,
                    language,
                    max_descendant_bytes=remaining_descendant_bytes,
                    max_descendant_nodes=remaining_descendant_nodes,
                )
                sections.append(section)
                remaining_descendant_nodes = max(
                    0,
                    remaining_descendant_nodes
                    - self._descendant_node_count(section.get("descendants", [])),
                )
                remaining_descendant_bytes = max(
                    0,
                    remaining_descendant_bytes
                    - self._descendant_payload_size(section.get("descendants", [])),
                )
            return sections

    def get_page_snapshot(self, language: str, pagename: str) -> Dict[str, Any]:
        """Return one live page snapshot and entries parsed from that exact content."""
        if language not in self._SNAPSHOT_LANGUAGES:
            raise ServiceError(
                "Page snapshots are limited to English and Malagasy Wiktionary.",
                status_code=400,
            )
        page, content = self._fetch_page(pagename, language, force_refresh=True)
        content_bytes = content.encode("utf-8")
        if len(content_bytes) > self._MAX_PAGE_SNAPSHOT_BYTES:
            raise ServiceError(
                "The requested Wiktionary page is too large for review.",
                status_code=413,
            )
        serialised_entries: List[Dict[str, Any]] = []
        parse_error: Optional[str] = None
        try:
            processor = self._build_processor(language, page, content)
            processor.process(page)
            entries = processor.get_all_entries(
                get_additional_data=True,
                cleanup_definitions=True,
                advanced=True,
            )
            serialised_entries = [entry.serialise() for entry in entries]
        except Exception:
            log.warning(
                "Could not parse %s Wiktionary snapshot %r; returning raw review evidence.",
                language,
                pagename,
                exc_info=True,
            )
            parse_error = "The live page content could not be parsed."
        try:
            namespace = page.namespace()
            namespace_id = getattr(namespace, "id", None)
        except Exception:
            log.warning(
                "Could not resolve the namespace for %s Wiktionary snapshot %r.",
                language,
                pagename,
                exc_info=True,
            )
            namespace_id = None
        return {
            "language": language,
            "title": page.title(),
            "namespace": namespace_id if isinstance(namespace_id, int) else None,
            "content": content,
            "content_sha256": hashlib.sha256(content_bytes).hexdigest(),
            "entries": serialised_entries,
            "parsed": parse_error is None,
            "parse_error": parse_error,
            "content_trust": "untrusted_wiktionary_content",
        }

    def get_page_checker_settings(self) -> Dict[str, Any]:
        """Return the authoritative page-checker automation settings."""
        try:
            return self._page_checker_settings_store.get().serialise()
        except PageCheckerSettingsStoreError as exc:
            raise self._page_checker_settings_unavailable(exc) from exc

    def update_page_checker_settings(self, payload: Any) -> Dict[str, Any]:
        """Validate and replace the page-checker monitoring settings."""
        try:
            settings = PageCheckerSettings.from_monitoring_payload(payload)
        except PageCheckerSettingsValidationError as exc:
            raise ServiceError(
                "Invalid page checker settings.",
                status_code=400,
            ) from exc

        try:
            self._page_checker_settings_store.set_monitoring(settings)
        except PageCheckerSettingsStoreError as exc:
            raise self._page_checker_settings_unavailable(exc) from exc
        return settings.serialise_monitoring()

    def update_page_checker_autonomous_agent(self, payload: Any) -> Dict[str, bool]:
        """Validate and replace only automatic GitHub agent assignment."""
        if (
            not isinstance(payload, dict)
            or set(payload) != {"enabled"}
            or not isinstance(payload["enabled"], bool)
        ):
            raise ServiceError(
                "Invalid autonomous agent setting.",
                status_code=400,
            )
        try:
            self._page_checker_settings_store.set_autonomous_agent_enabled(
                payload["enabled"]
            )
        except PageCheckerSettingsStoreError as exc:
            raise self._page_checker_settings_unavailable(exc) from exc
        return {"autonomous_agent_enabled": payload["enabled"]}

    def update_translation_prefilter(self, payload: Any) -> Dict[str, bool]:
        """Validate and replace the translated-page publication prefilter."""
        if (
            not isinstance(payload, dict)
            or set(payload) != {"enabled"}
            or not isinstance(payload["enabled"], bool)
        ):
            raise ServiceError(
                "Invalid translation prefilter setting.",
                status_code=400,
            )
        try:
            self._page_checker_settings_store.set_translation_prefilter_enabled(
                payload["enabled"]
            )
        except PageCheckerSettingsStoreError as exc:
            raise self._page_checker_settings_unavailable(exc) from exc
        return {"translation_prefilter_enabled": payload["enabled"]}

    def update_page_check_job_history_limit(self, payload: Any) -> Dict[str, int]:
        """Validate and replace the visible page-check job history limit."""
        if not isinstance(payload, dict) or set(payload) != {"limit"}:
            raise ServiceError("Invalid job history limit.", status_code=400)
        try:
            settings = PageCheckerSettings(job_history_limit=payload["limit"])
            self._page_checker_settings_store.set_job_history_limit(
                settings.job_history_limit
            )
        except PageCheckerSettingsValidationError as exc:
            raise ServiceError("Invalid job history limit.", status_code=400) from exc
        except PageCheckerSettingsStoreError as exc:
            raise self._page_checker_settings_unavailable(exc) from exc
        return {"job_history_limit": settings.job_history_limit}

    def get_definition_translation_settings(self) -> Dict[str, bool]:
        """Return authoritative definition-translation settings."""
        try:
            return self._definition_translation_settings_store.get().serialise()
        except DefinitionTranslationSettingsStoreError as exc:
            raise self._definition_translation_settings_unavailable(exc) from exc

    def update_definition_translation_settings(self, payload: Any) -> Dict[str, bool]:
        """Validate and replace definition-translation settings."""
        try:
            settings = DefinitionTranslationSettings.from_payload(payload)
        except DefinitionTranslationSettingsValidationError as exc:
            raise ServiceError(
                "Invalid definition translation settings.",
                status_code=400,
            ) from exc
        if "nllb_roundtrip_validation_enabled" not in payload:
            try:
                current_settings = self._definition_translation_settings_store.get()
            except DefinitionTranslationSettingsStoreError as exc:
                raise self._definition_translation_settings_unavailable(exc) from exc
            settings = DefinitionTranslationSettings.from_payload(
                payload,
                current=current_settings,
            )
        try:
            self._definition_translation_settings_store.set(settings)
        except DefinitionTranslationSettingsStoreError as exc:
            raise self._definition_translation_settings_unavailable(exc) from exc
        return settings.serialise()

    def check_pages(
        self,
        language: str,
        titles: List[str],
        on_progress: Optional[Callable[[float], None]] = None,
        publication_guard: Optional[Callable[[], None]] = None,
    ) -> List[Dict[str, Any]]:
        """Check Malagasy Wiktionary pages against their source wiktionaries.

        Args:
            language: Language of the wiktionary the pages live on (usually "mg").
            titles: Page titles to check and fix.
            on_progress: Optional callback receiving a 0.0-1.0 completion ratio.

        Returns:
            A list of serialized PageCheckResult objects, one per title.
        """
        page_check_service = self._get_page_check_service()
        if publication_guard is None:
            return page_check_service.check_pages(
                language, titles, on_progress=on_progress
            )
        return page_check_service.check_pages(
            language,
            titles,
            on_progress=on_progress,
            publication_guard=publication_guard,
        )

    def enqueue_page_check(self, language: str, titles: List[str]) -> Dict[str, Any]:
        """Queue one asynchronous page check job per title.

        Args:
            language: Language of the wiktionary the pages live on (usually "mg").
            titles: Page titles to check and fix, one job per title.

        Returns:
            A dict with the "jobs" list of pending job states.

        Raises:
            ServiceError: When the job store is full of unfinished work.
        """
        jobs: List[Dict[str, Any]] = []
        now = time.time()
        with self._check_jobs_lock:
            for title in titles:
                job: Dict[str, Any] = {
                    "job_id": uuid.uuid4().hex,
                    "execution_token": uuid.uuid4().hex,
                    "language": language,
                    "titles": [title],
                    "status": "pending",
                    "created_at": now,
                    "last_updated_at": now,
                    "attempts": 0,
                    "progress": 0,
                    "results": None,
                    "error": None,
                    "stage": "queued",
                    "message": "Waiting for a page-check worker.",
                    "timeline": [
                        {
                            "timestamp": now,
                            "stage": "queued",
                            "message": "Waiting for a page-check worker.",
                        }
                    ],
                    "review_queue_state": "not_needed",
                    "review_event_id": None,
                    "review_queue_error": None,
                }
                jobs.append(job)
            try:
                accepted = self._check_job_store.put_many_bounded(
                    jobs,
                    self._max_check_jobs_kept,
                    self._MAX_UNFINISHED_CHECK_JOBS,
                )
            except CheckJobStoreError as exc:
                raise self._page_check_store_unavailable(exc) from exc
            if not accepted:
                raise ServiceError(
                    "Page check capacity is currently full.",
                    status_code=503,
                )

        for job in jobs:
            try:
                self._run_check_task(self._build_check_task(job))
            except Exception:
                log.exception("Unable to start page check job %s.", job["job_id"])
                with self._check_jobs_lock:
                    job["status"] = "error"
                    job["last_updated_at"] = time.time()
                    job["error"] = "The page check job could not be started."
                    self._set_check_job_state(
                        job,
                        "failed",
                        "The page check job could not be started.",
                    )
                    self._prepare_page_check_review(job)
                self._check_job_store.put(job)
                self._publish_page_check_review(job)

        self._schedule_stale_check_recovery()
        return {"jobs": [dict(job) for job in jobs]}

    def _build_check_task(self, job: Dict[str, Any]) -> Callable[[], None]:
        """Build the task that runs one page check job and records progress."""

        def on_progress(ratio: float) -> None:
            with self._check_jobs_lock:
                progress = max(0, min(100, int(ratio * 100)))
                job["progress"] = max(job["progress"], progress)
                job["last_updated_at"] = time.time()
                stage, message = self._check_progress_state(job["progress"])
                self._set_check_job_state(job, stage, message)
            if not self._check_job_store.put(job):
                raise CheckJobExecutionSuperseded(
                    "A newer worker owns this page-check job."
                )

        def publication_guard() -> None:
            if not self._check_job_store.touch_execution(
                job["job_id"], job["execution_token"], time.time()
            ):
                raise CheckJobExecutionSuperseded(
                    "A newer worker owns this page-check job."
                )

        def task() -> None:
            """Run the page check job and record its outcome."""
            try:
                with self._check_jobs_lock:
                    job["status"] = "running"
                    job["last_updated_at"] = time.time()
                    self._set_check_job_state(
                        job,
                        "loading_target",
                        "Loading the current Wiktionary page.",
                    )
                if not self._check_job_store.put(job):
                    raise CheckJobExecutionSuperseded(
                        "A newer worker owns this page-check job."
                    )
                results = self.check_pages(
                    job["language"],
                    job["titles"],
                    on_progress=on_progress,
                    publication_guard=publication_guard,
                )
                with self._check_jobs_lock:
                    job["status"] = "done"
                    job["progress"] = 100
                    job["last_updated_at"] = time.time()
                    job["results"] = results
                    job["error"] = None
                    self._set_check_job_state(
                        job,
                        "completed",
                        "Page check completed; the full result is available.",
                    )
                    self._prepare_page_check_review(job)
                if self._check_job_store.put(job):
                    self._publish_page_check_review(job)
            except CheckJobExecutionSuperseded:
                log.info(
                    "Page check job %s stopped after stale recovery reassigned it.",
                    job["job_id"],
                )
            except Exception as exc:
                log.exception("Page check job %s failed.", job["job_id"])
                with self._check_jobs_lock:
                    job["status"] = "error"
                    job["last_updated_at"] = time.time()
                    job["error"] = str(exc)
                    self._set_check_job_state(job, "failed", str(exc))
                    self._prepare_page_check_review(job)
                if self._check_job_store.put(job):
                    self._publish_page_check_review(job)
            finally:
                self._trim_check_jobs()

        return task

    def get_page_check_job(self, job_id: str) -> Dict[str, Any]:
        """Return the current state of an asynchronous page check job.

        Args:
            job_id: Id of the page check job.

        Returns:
            The serialized job state: "pending", "running", "done" or "error".

        Raises:
            ServiceError: When the job id is unknown.
        """
        try:
            job = self._check_job_store.get(job_id)
        except CheckJobStoreError as exc:
            raise self._page_check_store_unavailable(exc) from exc
        if job is None:
            raise ServiceError(
                "Unknown page check job.",
                status_code=404,
            )
        self._schedule_stale_check_recovery()
        return job

    def list_page_check_jobs(
        self,
        language: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Return summaries of recent page check jobs, newest first.

        Args:
            language: Optional language to filter the jobs by.
            limit: Maximum number of jobs to return, capped at the store bound.

        Returns:
            A list of job summaries without their full results.
        """
        try:
            jobs = self._check_job_store.all()
        except CheckJobStoreError as exc:
            raise self._page_check_store_unavailable(exc) from exc
        if language is not None:
            jobs = [job for job in jobs if job["language"] == language]
        jobs.sort(key=lambda job: job["created_at"], reverse=True)
        pending_jobs = sorted(
            (job for job in jobs if job["status"] == "pending"),
            key=lambda job: (job["created_at"], job["job_id"]),
        )
        queue_positions = {
            job["job_id"]: index for index, job in enumerate(pending_jobs, start=1)
        }
        summaries: List[Dict[str, Any]] = []
        history_limit = self._page_check_job_history_limit()
        for job in jobs[: max(0, min(limit, history_limit))]:
            summaries.append(
                {
                    "job_id": job["job_id"],
                    "language": job["language"],
                    "titles": list(job["titles"]),
                    "status": job["status"],
                    "created_at": job["created_at"],
                    "last_updated_at": job["last_updated_at"],
                    "attempts": job["attempts"],
                    "progress": job["progress"],
                    "error": job["error"],
                    "stage": job.get("stage", "queued"),
                    "message": job.get("message", "Waiting for a page-check worker."),
                    "review_queue_state": job.get(
                        "review_queue_state", "not_needed"
                    ),
                    "review_event_id": job.get("review_event_id"),
                    "review_queue_error": job.get("review_queue_error"),
                    "queue_position": queue_positions.get(job["job_id"]),
                    "result_counts": _count_check_results(job.get("results")),
                }
            )
        self._schedule_stale_check_recovery()
        return summaries

    def get_page_check_statistics(self, language: str) -> Dict[str, Any]:
        """Aggregate retained page-check jobs into canonical UTC periods.

        Args:
            language: Wiktionary language whose retained jobs should be counted.

        Returns:
            Retention metadata and one statistics record for each supported period.
        """
        as_of = time.time()
        try:
            stored_jobs = self._check_job_store.all()
        except CheckJobStoreError as exc:
            raise self._page_check_store_unavailable(exc) from exc
        stored_jobs.sort(
            key=lambda job: (
                job.get("created_at")
                if isinstance(job.get("created_at"), (int, float))
                else float("-inf"),
                str(job.get("job_id", "")),
            ),
            reverse=True,
        )
        history_limit = self._page_check_job_history_limit()
        retained_jobs = stored_jobs[:history_limit]
        jobs = [job for job in retained_jobs if job.get("language") == language]
        statistics = [
            _aggregate_page_check_period(jobs, period, period_start, period_end)
            for period, period_start, period_end in _page_check_period_bounds(as_of)
        ]
        self._schedule_stale_check_recovery()
        return {
            "language": language,
            "generated_at": as_of,
            "timezone": "UTC",
            "retention_limit": history_limit,
            "retained_job_count": len(jobs),
            "statistics": statistics,
        }

    @staticmethod
    def _set_check_job_state(
        job: Dict[str, Any], stage: str, message: str
    ) -> None:
        """Update a job's current stage and append a bounded timeline event."""
        job["stage"] = stage
        job["message"] = message
        timeline = job.setdefault("timeline", [])
        if not isinstance(timeline, list):
            timeline = []
            job["timeline"] = timeline
        last_event = timeline[-1] if timeline and isinstance(timeline[-1], dict) else None
        if last_event is not None and last_event.get("stage") == stage:
            last_event["message"] = message
            last_event["timestamp"] = job["last_updated_at"]
            return
        timeline.append(
            {
                "timestamp": job["last_updated_at"],
                "stage": stage,
                "message": message,
            }
        )
        del timeline[:-_CHECK_JOB_TIMELINE_LIMIT]

    def _prepare_page_check_review(self, job: Dict[str, Any]) -> None:
        """Persist the exact first review event for a terminal Malagasy job."""
        if isinstance(job.get("review_message"), dict):
            return
        outcome = _page_check_job_outcome(job)
        if job.get("language") != "mg" or outcome not in REVIEWABLE_PAGE_CHECK_OUTCOMES:
            job["review_queue_state"] = "not_needed"
            job["review_event_id"] = None
            job["review_queue_error"] = None
            return
        if self._page_check_review_queue is None:
            job["review_queue_state"] = "disabled"
            job["review_event_id"] = None
            job["review_queue_error"] = None
            return
        try:
            message = build_page_check_review_message(job)
        except PageCheckReviewQueueError as exc:
            job["review_queue_state"] = "invalid"
            job["review_event_id"] = None
            job["review_queue_error"] = str(exc)[:1_000]
            return
        job["review_queue_state"] = "pending"
        job["review_event_id"] = message["event_id"]
        job["review_queue_error"] = None
        job["review_message"] = message
        job["review_queue_attempts"] = 0
        job["review_queue_next_attempt_at"] = 0.0

    def _publish_page_check_review(self, job: Dict[str, Any]) -> None:
        """Publish one prepared review event without changing the check outcome."""
        if (
            job.get("review_queue_state")
            not in {"pending", "failed", "publishing"}
            or self._page_check_review_queue is None
        ):
            return
        if not isinstance(job.get("review_message"), dict):
            self._prepare_page_check_review(job)
            try:
                self._check_job_store.put(job)
            except CheckJobStoreError as exc:
                log.error(
                    "Could not persist page-check review event for job %s: %s",
                    job.get("job_id"),
                    exc,
                )
                return
            if job.get("review_queue_state") != "pending":
                return
        claim_token = uuid.uuid4().hex
        try:
            claimed_job = self._check_job_store.claim_review_handoff(
                job["job_id"],
                claim_token,
                time.time(),
                self._REVIEW_HANDOFF_LEASE_SECONDS,
            )
        except CheckJobStoreError as exc:
            log.error(
                "Could not claim page-check job %s for review publication: %s",
                job["job_id"],
                exc,
            )
            return
        if claimed_job is None:
            return
        event_id = str(claimed_job.get("review_event_id") or "")
        try:
            review_message = validate_page_check_review_message(
                claimed_job.get("review_message")
            )
        except PageCheckReviewQueueError as exc:
            state = "invalid"
            error = str(exc)[:1_000]
        else:
            try:
                event_id = self._page_check_review_queue.publish_message(review_message)
            except PageCheckReviewQueueError as exc:
                log.error(
                    "Could not queue page-check job %s for manual review: %s",
                    job["job_id"],
                    exc,
                )
                state = "failed"
                error = str(exc)[:1_000]
            except Exception as exc:  # pylint: disable=broad-exception-caught
                log.exception(
                    "Unexpected page-check review failure for job %s.",
                    job.get("job_id"),
                )
                state = "failed"
                error = f"Unexpected review transport failure: {type(exc).__name__}"
            else:
                state = "queued"
                error = None
        try:
            finished = self._check_job_store.finish_review_handoff(
                job["job_id"],
                claim_token,
                state,
                event_id,
                error,
            )
        except CheckJobStoreError as exc:
            log.error(
                "Could not store page-check review handoff state for job %s: %s",
                job["job_id"],
                exc,
            )
            return
        if finished:
            with self._check_jobs_lock:
                job["review_queue_state"] = state
                job["review_event_id"] = event_id
                job["review_queue_error"] = error

    @staticmethod
    def _check_progress_state(progress: int) -> Tuple[str, str]:
        """Return the current detailed stage for a page-check percentage."""
        if progress < 15:
            return "loading_target", "Loading the current Wiktionary page."
        if progress < 30:
            return "resolving_source", "Resolving the linked source entry."
        if progress < 50:
            return "loading_source", "Loading and parsing the source Wiktionary page."
        if progress < 55:
            return "loading_reference", "Loading the tenymalagasy.org reference."
        if progress < 75:
            return "verifying", "Comparing the current definitions with their sources."
        if progress < 95:
            return "generating_fix", "Generating and validating a proposed correction."
        if progress < 100:
            return "queueing_publication", "Revalidating the pages and queueing the correction."
        return "finalising", "Finalising the page-check result."

    def _schedule_stale_check_recovery(self) -> None:
        """Schedule stale-job recovery without delaying an HTTP status response."""
        if self._check_executor is None:
            return
        with self._stale_recovery_lock:
            now = time.time()
            if (
                self._check_recovery_running
                or now - self._last_check_recovery
                < self._STALE_RECOVERY_INTERVAL_SECONDS
            ):
                return
            self._last_check_recovery = now
            self._check_recovery_running = True
        try:
            self._check_executor.submit(self._run_scheduled_check_recovery)
        except RuntimeError:
            with self._stale_recovery_lock:
                self._check_recovery_running = False
            log.warning("Page check recovery could not be scheduled during shutdown.")

    def _run_scheduled_check_recovery(self) -> None:
        """Run one scheduled recovery and release its single-flight marker."""
        try:
            self._recover_stale_check_jobs()
        finally:
            with self._stale_recovery_lock:
                self._check_recovery_running = False

    def _maybe_recover_stale_check_jobs(self) -> None:
        """Run stale page check job recovery at most once per interval."""
        with self._stale_recovery_lock:
            now = time.time()
            if (
                self._check_recovery_running
                or now - self._last_check_recovery
                < self._STALE_RECOVERY_INTERVAL_SECONDS
            ):
                return
            self._last_check_recovery = now
            self._check_recovery_running = True
        try:
            self._recover_stale_check_jobs()
        finally:
            with self._stale_recovery_lock:
                self._check_recovery_running = False

    def _recover_stale_check_jobs(self) -> None:
        """Retry failed review handoffs and relaunch stale page-check jobs."""
        now = time.time()
        jobs = self._check_job_store.all()
        review_handoffs = [
            job
            for job in jobs
            if _review_handoff_is_claimable(
                job,
                now,
                self._REVIEW_HANDOFF_LEASE_SECONDS,
            )
        ]
        for job in review_handoffs[: self._REVIEW_HANDOFF_RECOVERY_BATCH_SIZE]:
            self._publish_page_check_review(job)
        stale = [
            job
            for job in jobs
            if job["status"] in ("pending", "running")
            and now - job["last_updated_at"] > self._STALE_CHECK_JOB_TIMEOUT_SECONDS
        ]
        for observed_job in stale:
            job = self._check_job_store.claim_stale_job(
                observed_job["job_id"],
                observed_job["last_updated_at"],
                now,
                self._STALE_CHECK_JOB_TIMEOUT_SECONDS,
                uuid.uuid4().hex,
            )
            if job is None:
                continue
            exceeded_retry_limit = job["attempts"] > self._CHECK_JOB_MAX_ATTEMPTS
            with self._check_jobs_lock:
                if exceeded_retry_limit:
                    job["status"] = "error"
                    job["last_updated_at"] = time.time()
                    job["error"] = "The page check job stalled and exceeded its retry limit."
                    self._set_check_job_state(job, "failed", job["error"])
                    self._prepare_page_check_review(job)
                else:
                    self._set_check_job_state(
                        job,
                        "retrying",
                        f"Retrying a stalled page check (attempt {job['attempts']}).",
                    )
            if not self._check_job_store.put(job):
                continue
            if exceeded_retry_limit:
                self._publish_page_check_review(job)
                continue
            log.warning(
                "Relaunching stale page check job %s (attempt %d).",
                job["job_id"],
                job["attempts"],
            )
            try:
                self._run_check_task(self._build_check_task(job))
            except Exception:
                log.exception(
                    "Unable to relaunch stale page check job %s.", job["job_id"]
                )
                with self._check_jobs_lock:
                    job["status"] = "error"
                    job["last_updated_at"] = time.time()
                    job["error"] = "The page check job could not be relaunched."
                    self._set_check_job_state(job, "failed", job["error"])
                    self._prepare_page_check_review(job)
                self._check_job_store.put(job)
                self._publish_page_check_review(job)

    def _trim_check_jobs(self) -> None:
        """Drop the oldest completed check jobs to bound the job store."""
        jobs = self._check_job_store.all()
        self._trim_completed_check_jobs(jobs, self._max_check_jobs_kept)

    def _page_check_job_history_limit(self) -> int:
        """Return the authoritative number of jobs exposed to Atlas."""
        try:
            return self._page_checker_settings_store.get().job_history_limit
        except PageCheckerSettingsStoreError as exc:
            log.warning(
                "Using the default page-check job history limit: %s",
                exc,
            )
            return DEFAULT_JOB_HISTORY_LIMIT

    def _trim_completed_check_jobs(
        self,
        jobs: List[Dict[str, Any]],
        maximum_jobs: int,
    ) -> None:
        """Drop oldest terminal jobs from a known snapshot to reach a bound."""
        if len(jobs) <= maximum_jobs:
            return
        completed = sorted(
            (
                job
                for job in jobs
                if job["status"] in ("done", "error")
                and job.get("review_queue_state")
                not in {"pending", "failed", "publishing"}
            ),
            key=lambda job: job["created_at"],
        )
        for job in completed[: len(jobs) - maximum_jobs]:
            self._check_job_store.remove_terminal(job["job_id"])

    def _run_task(self, task: Callable[[], None]) -> Any:
        """Run a task in the configured runner or bounded executor."""
        if self._task_runner:
            return self._task_runner(task)
        if self._executor is None:
            raise RuntimeError("Translation executor is not configured.")
        return self._executor.submit(task)

    def _run_check_task(self, task: Callable[[], None]) -> Any:
        """Run a page-check task in its dedicated executor."""
        if self._task_runner:
            return self._task_runner(task)
        if self._check_executor is None:
            raise RuntimeError("Page check executor is not configured.")
        return self._check_executor.submit(task)

    @staticmethod
    def _normalise_translation_request_id(request_id: Optional[str]) -> Optional[str]:
        """Validate an optional client UUID used to make job creation idempotent."""
        if request_id is None:
            return None
        if not isinstance(request_id, str):
            raise ServiceError("Field 'request_id' must be a UUID.", status_code=400)
        try:
            return str(uuid.UUID(request_id))
        except (ValueError, AttributeError) as exc:
            raise ServiceError(
                "Field 'request_id' must be a UUID.",
                status_code=400,
            ) from exc

    def _get_existing_translation_request(
        self,
        job_id: str,
        language: str,
        title: str,
    ) -> Optional[Dict[str, Any]]:
        """Return a matching idempotent job or reject reuse for other inputs."""
        try:
            existing_job = self._translation_job_store.get(job_id)
        except TranslationJobStoreError as exc:
            raise self._translation_job_store_unavailable(exc) from exc
        if existing_job is None:
            return None
        existing_job = self._recover_unleased_translation_job(existing_job)
        if (
            existing_job.get("language") != language
            or existing_job.get("title") != title
        ):
            raise ServiceError(
                "The request ID is already associated with another translation job.",
                status_code=409,
            )
        return self._public_translation_job(existing_job)

    def _recover_unleased_translation_job(
        self,
        job: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Fence a durable active state whose process lease has disappeared."""
        if job.get("status") not in ("pending", "running"):
            return job
        job_id = job.get("job_id")
        owner_token = job.get("_owner_token")
        if not isinstance(job_id, str) or not isinstance(owner_token, str):
            return job
        try:
            if self._queue_counter.owns_job(job_id, owner_token):
                return job
            last_updated_at = float(job["last_updated_at"])
        except TranslationJobStoreError as exc:
            raise self._translation_job_store_unavailable(exc) from exc
        except (KeyError, TypeError, ValueError) as exc:
            raise self._translation_job_store_unavailable(
                TranslationJobStoreError(
                    "The persistent translation job store contains invalid data."
                )
            ) from exc
        if time.time() - last_updated_at < self._stale_job_timeout_seconds:
            return job

        error_message = (
            f"Job lease was absent for {self._stale_job_timeout_seconds:g} seconds."
        )
        recovered_job = dict(job)
        recovered_job["result"] = None
        recovered_job["error"] = error_message
        try:
            self._update_translation_job(
                recovered_job,
                "error",
                "failed",
                owner_token,
                require_active=False,
            )
        except TranslationJobLeaseLost:
            latest_job = self._translation_job_store.get(job_id)
            if latest_job is None:
                raise ServiceError("Unknown translation job.", status_code=404)
            return latest_job
        self._record_job_error(
            "Translation job lost its active process lease.",
            {
                "message": error_message,
                "error_type": "MissingJobLease",
                "title": job.get("title", ""),
                "language": job.get("language", ""),
            },
            job_id=job_id,
        )
        return recovered_job

    @staticmethod
    def _public_translation_job(job: Dict[str, Any]) -> Dict[str, Any]:
        """Return a job record without its internal owner fencing token."""
        public_job = dict(job)
        public_job.pop("_owner_token", None)
        return public_job

    def _heartbeat_translation_job(
        self,
        job_id: str,
        owner_token: str,
        stop_event: threading.Event,
    ) -> None:
        """Keep a live job distinguishable from work abandoned by a dead process."""
        interval_seconds = max(
            0.1,
            min(30.0, self._stale_job_timeout_seconds / 3),
        )
        while not stop_event.wait(interval_seconds):
            try:
                if not self._queue_counter.touch_job(
                    job_id,
                    time.time(),
                    owner_token,
                ):
                    return
            except Exception:  # pylint: disable=broad-exception-caught
                log.exception(
                    "Unable to refresh heartbeat for translation job %s.",
                    job_id,
                )

    def _update_translation_job(
        self,
        job: Dict[str, Any],
        status: str,
        stage: str,
        owner_token: str,
        *,
        require_active: bool = True,
    ) -> None:
        """Persist one translation job lifecycle transition."""
        if require_active and not self._queue_counter.touch_job(
            str(job["job_id"]),
            time.time(),
            owner_token,
        ):
            raise TranslationJobLeaseLost("The translation job is no longer active.")
        job["status"] = status
        job["stage"] = stage
        job["message"] = self._TRANSLATION_JOB_MESSAGES[stage]
        job["last_updated_at"] = time.time()
        if not self._translation_job_store.put_owned(job, owner_token):
            raise TranslationJobLeaseLost(
                "The translation job owner is no longer authoritative."
            )

    @staticmethod
    def _normalise_queued_translation_result(
        result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Describe RabbitMQ acceptance without claiming direct wiki publication."""
        queued_result = dict(result)
        queued_result["status"] = "publication_queued"
        queued_result["message"] = "Translated entries were queued for publication."
        queued_result["published"] = False
        return queued_result

    @staticmethod
    def _normalise_filtered_translation_result(
        result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Describe a translated candidate discarded by the page checker."""
        filtered_result = dict(result)
        filtered_result["status"] = "publication_filtered"
        filtered_result["message"] = (
            "The translated page did not pass the publication prefilter."
        )
        filtered_result["published"] = False
        return filtered_result

    def _get_page_check_service(self) -> "PageCheckService":
        """Return the shared page checker used by checks and publication filtering."""
        if self._page_check_service is None:
            settings_store = self._definition_translation_settings_store
            self._page_check_service = PageCheckService(
                get_page=self._get_page,
                publisher=self._page_check_publisher,
                nllb_roundtrip_validation_enabled=lambda: (
                    settings_store.get().nllb_roundtrip_validation_enabled
                ),
            )
        return self._page_check_service

    @staticmethod
    def _translation_job_store_unavailable(
        error: TranslationJobStoreError,
    ) -> ServiceError:
        """Convert an authoritative translation job-store failure to HTTP 503."""
        log.error("Persistent translation job storage failed: %s", error)
        return ServiceError(
            "Translation job history is temporarily unavailable.",
            status_code=503,
        )

    @staticmethod
    def _page_check_store_unavailable(error: CheckJobStoreError) -> ServiceError:
        """Convert a persistent job-store failure into the public API error."""
        log.error("Persistent page check job storage failed: %s", error)
        return ServiceError(
            "Page check history is temporarily unavailable.",
            status_code=503,
        )

    @staticmethod
    def _page_checker_settings_unavailable(
        error: PageCheckerSettingsStoreError,
    ) -> ServiceError:
        """Convert an authoritative settings-store failure to a public error."""
        log.error("Persistent page checker settings storage failed: %s", error)
        return ServiceError(
            "Page checker settings are temporarily unavailable.",
            status_code=503,
        )

    @staticmethod
    def _definition_translation_settings_unavailable(
        error: DefinitionTranslationSettingsStoreError,
    ) -> ServiceError:
        """Convert a definition settings-store failure to a public error."""
        log.error("Persistent definition translation settings storage failed: %s", error)
        return ServiceError(
            "Definition translation settings are temporarily unavailable.",
            status_code=503,
        )

    def _reserve_job_slot(self) -> None:
        """Reserve process-local asynchronous capacity without blocking."""
        with self._executor_state_lock:
            accepting = self._accepting_async_jobs
            if not accepting:
                self._rejected_job_count += 1
                status = self._executor_status_unlocked()
        if not accepting:
            raise ServiceError(
                "Translation service is shutting down.",
                status_code=503,
                details=status,
            )
        if not self._job_slots.acquire(blocking=False):
            with self._executor_state_lock:
                self._rejected_job_count += 1
                status = self._executor_status_unlocked()
            raise ServiceError(
                "Translation capacity is currently full.",
                status_code=503,
                details=status,
            )
        with self._executor_state_lock:
            if not self._accepting_async_jobs:
                self._job_slots.release()
                self._rejected_job_count += 1
                status = self._executor_status_unlocked()
                raise ServiceError(
                    "Translation service is shutting down.",
                    status_code=503,
                    details=status,
                )
            self._process_admitted_jobs += 1

    def _mark_job_running(self) -> None:
        """Record that an admitted job started execution."""
        with self._executor_state_lock:
            self._process_running_jobs += 1

    def _finish_process_job(self, started: bool, failed: bool) -> None:
        """Release capacity and update process-local completion metrics."""
        with self._executor_state_lock:
            self._process_admitted_jobs -= 1
            if started:
                self._process_running_jobs -= 1
            self._completed_job_count += 1
            if failed:
                self._failed_job_count += 1
        self._job_slots.release()

    def _executor_status(self) -> Dict[str, Any]:
        """Return process-local executor capacity and lifecycle information."""
        with self._executor_state_lock:
            return self._executor_status_unlocked()

    def _executor_status_unlocked(self) -> Dict[str, Any]:
        """Return executor status while the state lock is held."""
        queued_jobs = self._process_admitted_jobs - self._process_running_jobs
        return {
            "process_admitted_jobs": self._process_admitted_jobs,
            "process_running_jobs": self._process_running_jobs,
            "process_queued_jobs": queued_jobs,
            "process_job_capacity": self._job_capacity,
            "available_job_slots": self._job_capacity - self._process_admitted_jobs,
            "max_async_workers": self._max_async_workers,
            "accepting_async_jobs": self._accepting_async_jobs,
            "rejected_job_count": self._rejected_job_count,
            "completed_job_count": self._completed_job_count,
            "failed_job_count": self._failed_job_count,
        }

    def shutdown(self, wait: bool = False, cancel_futures: bool = True) -> None:
        """Stop accepting jobs and shut down the owned executor."""
        with self._executor_state_lock:
            if not self._accepting_async_jobs:
                return
            self._accepting_async_jobs = False
        if self._executor is not None:
            self._executor.shutdown(wait=wait, cancel_futures=cancel_futures)
        if self._check_executor is not None:
            self._check_executor.shutdown(wait=wait, cancel_futures=cancel_futures)

    def _record_job_duration(self, duration_seconds: float) -> None:
        """Update the exponential moving average for job durations."""
        if duration_seconds < 0:
            return
        with self._avg_duration_lock:
            if self._average_job_duration_seconds is None:
                self._average_job_duration_seconds = duration_seconds
            else:
                current = self._average_job_duration_seconds
                self._average_job_duration_seconds = (
                    self._EMA_ALPHA * duration_seconds + (1 - self._EMA_ALPHA) * current
                )

    def _maybe_recover_stale_jobs(self) -> None:
        """Run stale job recovery at most once per interval."""
        with self._stale_recovery_lock:
            now = time.time()
            if now - self._last_stale_recovery < self._STALE_RECOVERY_INTERVAL_SECONDS:
                return
            self._last_stale_recovery = now
        self._recover_stale_jobs()

    def _recover_stale_jobs(self) -> List[Dict[str, Any]]:
        """Remove timed-out jobs and make their diagnostics available."""
        with self._executor_state_lock:
            protected_job_ids = set(self._local_job_ids)
        stale_jobs = self._queue_counter.recover_stale_jobs(
            self._stale_job_timeout_seconds,
            time.time(),
            protected_job_ids,
        )
        timeout_seconds_text = f"{self._stale_job_timeout_seconds:g}"
        for active_job in stale_jobs:
            job_id = str(active_job.get("job_id", ""))
            owner_token = str(active_job.get("_owner_token", ""))
            error_message = f"Job exceeded {timeout_seconds_text} seconds."
            recovered = False
            if job_id:
                try:
                    job = self._translation_job_store.get(job_id)
                    if job is None:
                        recovered = True
                    elif (
                        owner_token
                        and job.get("status") in ("pending", "running")
                    ):
                        job["result"] = None
                        job["error"] = error_message
                        self._update_translation_job(
                            job,
                            "error",
                            "failed",
                            owner_token,
                            require_active=False,
                        )
                        recovered = True
                except TranslationJobLeaseLost:
                    continue
                except TranslationJobStoreError:
                    log.exception(
                        "Unable to persist stale recovery for translation job %s.",
                        job_id,
                    )
                    continue
            if not recovered:
                continue
            self._record_job_error(
                "Translation job exceeded the configured timeout and was removed.",
                {
                    "message": error_message,
                    "error_type": "StaleJobTimeout",
                    "title": active_job.get("title", ""),
                    "language": active_job.get("language", ""),
                },
                job_id=job_id or None,
            )
        return stale_jobs

    def _get_average_job_duration(self) -> Optional[float]:
        """Return the current exponential moving average of job durations."""
        with self._avg_duration_lock:
            return self._average_job_duration_seconds

    @staticmethod
    def _serialise_translation_result(
        result: Any, title: str, language: str
    ) -> Dict[str, Any]:
        """Convert a translation result into API response data."""
        if isinstance(result, TranslationPageResult):
            return result.serialise()
        if isinstance(result, dict):
            return result
        if isinstance(result, int):
            return {
                "title": title,
                "language": language,
                "status": "published" if result > 0 else "no_entries",
                "message": "Translation finished.",
                "entries_count": result,
                "published": result > 0,
                "error_type": None,
            }
        return {
            "title": title,
            "language": language,
            "status": "unknown",
            "message": "Translation finished without structured result data.",
            "entries_count": 0,
            "published": False,
            "error_type": None,
        }

    @staticmethod
    def _is_error_result(result: Any) -> bool:
        """Return True when the translation result represents failure."""
        if isinstance(result, TranslationPageResult):
            return result.status == "error"
        if isinstance(result, dict):
            return result.get("status") == "error"
        return False

    def _record_job_error(
        self,
        message: str,
        error: Any,
        *,
        job_id: Optional[str] = None,
        title: str = "",
        language: str = "",
    ) -> None:
        """Record a job error in the configured error store."""
        if isinstance(error, TranslationPageResult):
            error_data = {
                "message": message,
                "error": error.message,
                "type": error.error_type or "TranslationPageResult",
                "title": title or error.title,
                "language": language or error.language,
            }
        elif isinstance(error, dict):
            error_data = {
                "message": message,
                "error": str(error.get("message", "")),
                "type": str(error.get("error_type", "dict")),
                "title": title or str(error.get("title", "")),
                "language": language or str(error.get("language", "")),
            }
        else:
            error_data = {
                "message": message,
                "error": str(error),
                "type": type(error).__name__,
                "title": title,
                "language": language,
            }
        if job_id is not None:
            error_data["job_id"] = job_id
        self._job_error_store.record_error(error_data)

    def _fetch_page(
        self,
        title: str,
        language: str,
        *,
        force_refresh: bool = False,
    ) -> Tuple[Page, str]:
        """Fetch a wiki page and its content, or raise a ServiceError."""
        try:
            page = self._get_page(title, language)
        except Exception as exc:
            raise ServiceError(
                "Unable to retrieve the requested page.",
                status_code=502,
                details={"error": str(exc), "type": type(exc).__name__},
            ) from exc

        if page is None:
            raise ServiceError(
                f"Page '{title}' was not found for language '{language}'.",
                status_code=404,
            )

        with self._time_operation("fetch_page", title=title, language=language):
            try:
                content = (
                    page.get(force_refresh=True)
                    if force_refresh
                    else page.get()
                )
            except NoPage as exc:
                if not force_refresh:
                    raise ServiceError(
                        "Unable to retrieve the requested page.",
                        status_code=502,
                        details={"error": str(exc), "type": type(exc).__name__},
                    ) from exc
                raise ServiceError(
                    f"Page '{title}' was not found for language '{language}'.",
                    status_code=404,
                ) from exc
            except WikimediaRateLimitError as exc:
                headers = None
                details: Dict[str, Any] = {"type": type(exc).__name__}
                if exc.retry_after is not None:
                    retry_after = max(1, math.ceil(exc.retry_after))
                    headers = {"Retry-After": str(retry_after)}
                    details["retry_after_seconds"] = retry_after
                raise ServiceError(
                    str(exc),
                    status_code=exc.status_code,
                    details=details,
                    headers=headers,
                ) from exc
            except Exception as exc:
                raise ServiceError(
                    "Unable to retrieve the requested page.",
                    status_code=502,
                    details={"error": str(exc), "type": type(exc).__name__},
                ) from exc

        return page, content

    def _build_processor(self, language: str, page: Page, content: str) -> Any:
        """Create a processor for the requested language and page."""
        with self._time_operation("build_processor", language=language, title=page.title()):
            processor_class = self._processor_factory(language)
            processor = processor_class()
            processor.set_text(content)
            processor.set_title(page.title())
            return processor

    def _build_entry_section(
        self,
        entry: Entry,
        processor: Any,
        language: str,
        max_descendant_bytes: int | None = None,
        max_descendant_nodes: int | None = None,
    ) -> Dict[str, Any]:
        """Serialize an entry and attach translations for the requested language."""
        with self._time_operation(
            "build_entry_section",
            language=entry.language,
            part_of_speech=entry.part_of_speech,
        ):
            entry.definitions = [
                processor.advanced_extract_definition(entry.part_of_speech, definition)
                for definition in entry.definitions
            ]
            section = entry.serialise()
            get_descendant_tree = getattr(processor, "get_descendant_tree", None)
            if (
                callable(get_descendant_tree)
                and max_descendant_bytes != 0
                and max_descendant_nodes != 0
            ):
                descendants = get_descendant_tree(
                    entry.language,
                    entry.part_of_speech,
                    max_nodes=max_descendant_nodes,
                )
                descendants = self._bounded_descendant_nodes(
                    descendants,
                    self._MAX_PREVIEW_DESCENDANT_NODES
                    if max_descendant_nodes is None
                    else max_descendant_nodes,
                    self._MAX_PREVIEW_DESCENDANT_BYTES
                    if max_descendant_bytes is None
                    else max_descendant_bytes,
                )
                if descendants:
                    section["descendants"] = descendants
            if entry.language == language:
                section["translations"] = [
                    translation.serialise()
                    for translation in processor.retrieve_translations()
                    if translation.part_of_speech == entry.part_of_speech
                ]
            return section

    @staticmethod
    def _bounded_descendant_nodes(
        nodes: Any, max_nodes: int, max_bytes: int
    ) -> List[Dict[str, Any]]:
        """Copy recursive nodes within depth, count, and serialized-size bounds."""

        if not isinstance(nodes, list) or max_nodes <= 0 or max_bytes <= 0:
            return []
        result: List[Dict[str, Any]] = []
        stack: List[tuple[Any, List[Dict[str, Any]], int]] = [
            (iter(nodes), result, 1)
        ]
        copied_nodes = 0
        copied_bytes = 2
        while stack and copied_nodes < max_nodes:
            iterator, target, depth = stack[-1]
            try:
                node = next(iterator)
            except StopIteration:
                stack.pop()
                continue
            if not isinstance(node, dict):
                continue
            copied_node = {
                key: value for key, value in node.items() if key != "descendants"
            }
            try:
                node_bytes = len(
                    json.dumps(copied_node, separators=(",", ":")).encode("utf-8")
                ) + 32
            except (TypeError, ValueError):
                continue
            if copied_bytes + node_bytes > max_bytes:
                break
            target.append(copied_node)
            copied_nodes += 1
            copied_bytes += node_bytes
            children = node.get("descendants")
            if (
                isinstance(children, list)
                and children
                and copied_nodes < max_nodes
                and depth < EntryTranslatorService._MAX_PREVIEW_DESCENDANT_DEPTH
            ):
                copied_children: List[Dict[str, Any]] = []
                copied_node["descendants"] = copied_children
                stack.append((iter(children), copied_children, depth + 1))
        return result

    @staticmethod
    def _descendant_payload_size(nodes: Any) -> int:
        """Return the serialized size used by the response-wide byte budget."""

        try:
            return len(json.dumps(nodes, separators=(",", ":")).encode("utf-8"))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _descendant_node_count(nodes: Any) -> int:
        """Count descendant nodes without recursively traversing untrusted data."""

        count = 0
        pending = list(nodes) if isinstance(nodes, list) else []
        while pending:
            node = pending.pop()
            if not isinstance(node, dict):
                continue
            count += 1
            children = node.get("descendants")
            if isinstance(children, list):
                pending.extend(children)
        return count

    @staticmethod
    def _default_get_page(title: str, language: str) -> Optional[Page]:
        """Retrieve a page from the Redis-backed Wiktionary cache."""
        return Page(Site(language, "wiktionary"), title)


__all__ = [
    "CheckJobStoreError",
    "EntryTranslatorService",
    "JobCounter",
    "JobErrorStore",
    "QueueCounter",
    "RedisCheckJobStore",
    "RedisQueueCounter",
    "RedisTranslationJobStore",
    "ServiceError",
    "TranslationJobStoreError",
]
