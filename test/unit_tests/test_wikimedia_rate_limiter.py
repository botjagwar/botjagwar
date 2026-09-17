from datetime import datetime, timezone
from email.utils import format_datetime
from http import HTTPStatus
from types import SimpleNamespace
from typing import Any

import pytest
import redis

import api.wikimedia_rate_limiter as limiter_module
from api.wikimedia_rate_limiter import (
    WikimediaRateLimitError,
    WikimediaRateLimiter,
)


class CoordinatingRedis:
    """Model the two Lua operations with one shared Redis clock and keyspace."""

    def __init__(self, now_seconds: float = 1_000.0) -> None:
        self.now_us = round(now_seconds * 1_000_000)
        self.values: dict[str, int] = {}
        self.calls: list[tuple[str, int, tuple[Any, ...]]] = []

    def advance(self, seconds: float) -> None:
        """Advance the fake authoritative Redis clock."""
        self.now_us += round(seconds * 1_000_000)

    def eval(self, script: str, numkeys: int, *arguments: Any) -> Any:
        """Execute the behavior represented by the limiter's Lua scripts."""
        self.calls.append((script, numkeys, arguments))
        if script == limiter_module._RESERVE_SCRIPT:
            schedule_key, embargo_key, interval_us, max_wait_us = arguments
            next_start_us = self.values.get(schedule_key, self.now_us)
            embargo_until_us = self.values.get(embargo_key, self.now_us)
            start_us = max(self.now_us, next_start_us, embargo_until_us)
            wait_us = start_us - self.now_us
            if wait_us > max_wait_us:
                return [0, wait_us]
            self.values[schedule_key] = start_us + interval_us
            return [1, wait_us]

        if script == limiter_module._EXTEND_EMBARGO_SCRIPT:
            embargo_key, retry_after_us = arguments
            candidate_us = self.now_us + retry_after_us
            current_us = self.values.get(embargo_key, self.now_us)
            if candidate_us > current_us:
                current_us = candidate_us
                self.values[embargo_key] = current_us
            return max(0, current_us - self.now_us)

        raise AssertionError("Unexpected Lua script")


def test_reservations_use_redis_time_and_space_two_limiter_objects() -> None:
    redis_client = CoordinatingRedis()
    sleeps: list[float] = []
    first = WikimediaRateLimiter(redis_client, sleeper=sleeps.append)
    second = WikimediaRateLimiter(redis_client, sleeper=sleeps.append)

    assert first.acquire() == 0
    assert second.acquire() == 1

    assert sleeps == [1]
    assert "redis.replicate_commands()" in limiter_module._RESERVE_SCRIPT
    assert 'redis.call("TIME")' in limiter_module._RESERVE_SCRIPT


def test_wait_over_budget_is_rejected_without_sleep_or_reservation() -> None:
    redis_client = CoordinatingRedis()
    WikimediaRateLimiter(redis_client).acquire()
    schedule_before_rejection = dict(redis_client.values)
    sleeps: list[float] = []
    limiter = WikimediaRateLimiter(
        redis_client,
        max_wait_seconds=0.25,
        sleeper=sleeps.append,
    )

    with pytest.raises(WikimediaRateLimitError) as raised:
        limiter.acquire()

    assert raised.value.status == HTTPStatus.TOO_MANY_REQUESTS
    assert raised.value.status_code == HTTPStatus.TOO_MANY_REQUESTS
    assert raised.value.retry_after == 1
    assert sleeps == []
    assert redis_client.values == schedule_before_rejection


def test_redis_failure_fails_closed_without_sleeping() -> None:
    sleeps: list[float] = []

    class BrokenRedis:
        def eval(self, *_args: Any) -> Any:
            raise redis.ConnectionError("unavailable")

    limiter = WikimediaRateLimiter(BrokenRedis(), sleeper=sleeps.append)

    with pytest.raises(WikimediaRateLimitError) as raised:
        limiter.acquire()

    assert raised.value.status == HTTPStatus.SERVICE_UNAVAILABLE
    assert raised.value.retry_after is None
    assert sleeps == []


def test_embargo_extension_never_shortens_existing_deadline() -> None:
    redis_client = CoordinatingRedis()
    limiter = WikimediaRateLimiter(redis_client)

    assert limiter.extend_embargo(10) == 10
    redis_client.advance(2)
    assert limiter.extend_embargo(3) == 8
    assert limiter.extend_embargo(12) == 12

    embargo_key = f"{limiter_module.DEFAULT_KEY_PREFIX}:embargo-until-us"
    assert redis_client.values[embargo_key] == redis_client.now_us + 12_000_000
    assert "redis.replicate_commands()" in limiter_module._EXTEND_EMBARGO_SCRIPT
    assert 'redis.call("TIME")' in limiter_module._EXTEND_EMBARGO_SCRIPT


def test_429_response_retry_after_extends_shared_embargo() -> None:
    redis_client = CoordinatingRedis()
    limiter = WikimediaRateLimiter(redis_client)
    error = RuntimeError("rate limited")
    error.response = SimpleNamespace(
        status_code=HTTPStatus.TOO_MANY_REQUESTS,
        headers={"Retry-After": "7"},
    )

    assert limiter.observe_exception(error) is True

    embargo_key = f"{limiter_module.DEFAULT_KEY_PREFIX}:embargo-until-us"
    assert redis_client.values[embargo_key] == redis_client.now_us + 7_000_000


def test_retry_after_http_date_uses_injected_clock() -> None:
    redis_client = CoordinatingRedis()
    retry_at = format_datetime(
        datetime.fromtimestamp(1_010, timezone.utc),
        usegmt=True,
    )
    limiter = WikimediaRateLimiter(redis_client, clock=lambda: 1_000)
    error = RuntimeError("maintenance")
    error.response = SimpleNamespace(
        status_code=HTTPStatus.SERVICE_UNAVAILABLE,
        headers={"retry-after": retry_at},
    )

    assert limiter.observe_exception(error) is True

    embargo_key = f"{limiter_module.DEFAULT_KEY_PREFIX}:embargo-until-us"
    assert redis_client.values[embargo_key] == redis_client.now_us + 10_000_000


def test_maxlag_metadata_extends_embargo() -> None:
    redis_client = CoordinatingRedis()
    limiter = WikimediaRateLimiter(redis_client)
    error = RuntimeError("lagged")
    error.code = "maxlag"
    error.other = {"lag": "4.5"}

    assert limiter.observe_exception(error) is True

    embargo_key = f"{limiter_module.DEFAULT_KEY_PREFIX}:embargo-until-us"
    assert redis_client.values[embargo_key] == redis_client.now_us + 4_500_000


def test_403_does_not_extend_embargo_or_retry() -> None:
    redis_client = CoordinatingRedis()
    limiter = WikimediaRateLimiter(redis_client)
    error = RuntimeError("forbidden")
    error.response = SimpleNamespace(
        status_code=HTTPStatus.FORBIDDEN,
        headers={"Retry-After": "20"},
    )

    assert limiter.observe_exception(error) is False
    assert redis_client.calls == []
