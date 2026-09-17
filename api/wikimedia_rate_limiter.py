"""Cross-process Wikimedia request pacing backed by Redis."""

import configparser
import math
import time
from email.utils import parsedate_to_datetime
from http import HTTPStatus
from typing import Any, Callable, Iterator

from api.config import BotjagwarConfig

DEFAULT_REQUESTS_PER_MINUTE = 60.0
DEFAULT_MAX_WAIT_SECONDS = 30.0
DEFAULT_KEY_PREFIX = "botjagwar:wikimedia-rate-limit:{global}"

_RESERVE_SCRIPT = """
redis.replicate_commands()
local redis_time = redis.call("TIME")
local now_us = (tonumber(redis_time[1]) * 1000000) + tonumber(redis_time[2])
local interval_us = tonumber(ARGV[1])
local max_wait_us = tonumber(ARGV[2])

local next_start_us = tonumber(redis.call("GET", KEYS[1])) or now_us
local embargo_until_us = tonumber(redis.call("GET", KEYS[2])) or now_us
local start_us = math.max(now_us, next_start_us, embargo_until_us)
local wait_us = start_us - now_us

if wait_us > max_wait_us then
    return {0, wait_us}
end

local following_start_us = start_us + interval_us
local ttl_ms = math.max(1000, math.ceil((following_start_us - now_us) / 1000) + 1000)
redis.call("SET", KEYS[1], following_start_us, "PX", ttl_ms)
return {1, wait_us}
"""

_EXTEND_EMBARGO_SCRIPT = """
redis.replicate_commands()
local redis_time = redis.call("TIME")
local now_us = (tonumber(redis_time[1]) * 1000000) + tonumber(redis_time[2])
local retry_after_us = tonumber(ARGV[1])
local candidate_us = now_us + retry_after_us
local current_us = tonumber(redis.call("GET", KEYS[1])) or now_us

if candidate_us > current_us then
    local ttl_ms = math.max(1, math.ceil(retry_after_us / 1000) + 1000)
    redis.call("SET", KEYS[1], candidate_us, "PX", ttl_ms)
    current_us = candidate_us
end

return math.max(0, current_us - now_us)
"""


class WikimediaRateLimitError(RuntimeError):
    """Report that a Wikimedia request cannot safely start."""

    def __init__(
        self,
        message: str,
        *,
        retry_after: float | None = None,
        status: int = HTTPStatus.SERVICE_UNAVAILABLE,
    ) -> None:
        super().__init__(message)
        self.retry_after = retry_after
        self.status = int(status)
        self.status_code = self.status


class WikimediaRateLimiter:
    """Reserve globally spaced Wikimedia request starts through Redis."""

    def __init__(
        self,
        redis_client: Any,
        requests_per_minute: float = DEFAULT_REQUESTS_PER_MINUTE,
        max_wait_seconds: float = DEFAULT_MAX_WAIT_SECONDS,
        *,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.time,
        key_prefix: str = DEFAULT_KEY_PREFIX,
    ) -> None:
        if not math.isfinite(requests_per_minute) or requests_per_minute <= 0:
            raise ValueError("requests_per_minute must be a positive finite number")
        if not math.isfinite(max_wait_seconds) or max_wait_seconds < 0:
            raise ValueError("max_wait_seconds must be a non-negative finite number")
        if not key_prefix:
            raise ValueError("key_prefix must not be empty")

        self._redis_client = redis_client
        self._interval_us = math.ceil(60_000_000 / requests_per_minute)
        self._max_wait_seconds = max_wait_seconds
        self._max_wait_us = math.floor(max_wait_seconds * 1_000_000)
        self._sleeper = sleeper
        self._clock = clock
        self._schedule_key = f"{key_prefix}:next-start-us"
        self._embargo_key = f"{key_prefix}:embargo-until-us"

    @classmethod
    def from_config(
        cls,
        redis_client: Any,
        config: BotjagwarConfig | None = None,
        *,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.time,
        key_prefix: str = DEFAULT_KEY_PREFIX,
    ) -> "WikimediaRateLimiter":
        """Build a limiter from Botjagwar's optional Wikimedia settings."""
        settings = config or BotjagwarConfig()
        requests_per_minute = _configured_float(
            settings,
            "requests_per_minute",
            DEFAULT_REQUESTS_PER_MINUTE,
        )
        max_wait_seconds = _configured_float(
            settings,
            "max_wait_seconds",
            DEFAULT_MAX_WAIT_SECONDS,
        )
        return cls(
            redis_client,
            requests_per_minute=requests_per_minute,
            max_wait_seconds=max_wait_seconds,
            sleeper=sleeper,
            clock=clock,
            key_prefix=key_prefix,
        )

    def acquire(self) -> float:
        """Reserve one request start, sleep until it, or reject it safely."""
        try:
            result = self._redis_client.eval(
                _RESERVE_SCRIPT,
                2,
                self._schedule_key,
                self._embargo_key,
                self._interval_us,
                self._max_wait_us,
            )
            accepted = bool(int(result[0]))
            wait_us = max(0, int(result[1]))
        except Exception as exc:
            raise WikimediaRateLimitError(
                "Redis could not coordinate a Wikimedia request.",
                status=HTTPStatus.SERVICE_UNAVAILABLE,
            ) from exc

        wait_seconds = wait_us / 1_000_000
        if not accepted or wait_seconds > self._max_wait_seconds:
            raise WikimediaRateLimitError(
                "The Wikimedia request wait exceeds the configured budget.",
                retry_after=wait_seconds,
                status=HTTPStatus.TOO_MANY_REQUESTS,
            )
        if wait_seconds:
            self._sleeper(wait_seconds)
        return wait_seconds

    def extend_embargo(self, retry_after_seconds: float) -> float:
        """Extend the shared embargo from Redis time without shortening it."""
        if not math.isfinite(retry_after_seconds) or retry_after_seconds < 0:
            raise ValueError("retry_after_seconds must be a non-negative finite number")

        retry_after_us = math.ceil(retry_after_seconds * 1_000_000)
        try:
            remaining_us = int(
                self._redis_client.eval(
                    _EXTEND_EMBARGO_SCRIPT,
                    1,
                    self._embargo_key,
                    retry_after_us,
                )
            )
        except Exception as exc:
            raise WikimediaRateLimitError(
                "Redis could not update the Wikimedia request embargo.",
                status=HTTPStatus.SERVICE_UNAVAILABLE,
            ) from exc
        return max(0, remaining_us) / 1_000_000

    def observe_exception(self, error: Exception) -> bool:
        """Extend the embargo when a failed response provides retry timing."""
        status = _status_from_exception(error)
        if status == HTTPStatus.FORBIDDEN:
            return False

        code = str(getattr(error, "code", "")).lower()
        name = type(error).__name__.lower()
        is_maxlag = code == "maxlag" or "maxlag" in name
        is_rate_limited = code == "ratelimited"
        if status not in (HTTPStatus.TOO_MANY_REQUESTS, HTTPStatus.SERVICE_UNAVAILABLE) and not (
            is_maxlag or is_rate_limited
        ):
            return False

        retry_after = _retry_after_from_exception(error, self._clock)
        if retry_after is None and is_maxlag:
            retry_after = _maxlag_seconds(error)
        if retry_after is None:
            return False

        self.extend_embargo(retry_after)
        return True


def _configured_float(
    config: BotjagwarConfig,
    key: str,
    default: float,
) -> float:
    try:
        value = config.get(key, "wikimedia")
    except (configparser.Error, KeyError):
        return default
    return float(value)


def _exception_sources(error: Exception) -> Iterator[Any]:
    seen: set[int] = set()
    pending: list[Any] = [error]
    while pending:
        source = pending.pop(0)
        if source is None or id(source) in seen:
            continue
        seen.add(id(source))
        yield source
        pending.extend(
            (
                getattr(source, "response", None),
                getattr(source, "__cause__", None),
                getattr(source, "__context__", None),
            )
        )


def _status_from_exception(error: Exception) -> int | None:
    for source in _exception_sources(error):
        for attribute in ("status_code", "status"):
            value = getattr(source, attribute, None)
            try:
                if value is not None:
                    return int(value)
            except (TypeError, ValueError):
                continue
    return None


def _retry_after_from_exception(
    error: Exception,
    clock: Callable[[], float],
) -> float | None:
    for source in _exception_sources(error):
        direct_value = getattr(source, "retry_after", None)
        parsed = _parse_retry_after(direct_value, clock)
        if parsed is not None:
            return parsed

        headers = getattr(source, "headers", None)
        if headers is not None and hasattr(headers, "get"):
            value = headers.get("Retry-After")
            if value is None:
                value = headers.get("retry-after")
            parsed = _parse_retry_after(value, clock)
            if parsed is not None:
                return parsed

        other = getattr(source, "other", None)
        if isinstance(other, dict):
            for key in ("retry-after", "retry_after"):
                parsed = _parse_retry_after(other.get(key), clock)
                if parsed is not None:
                    return parsed
    return None


def _parse_retry_after(
    value: Any,
    clock: Callable[[], float],
) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        try:
            retry_at = parsedate_to_datetime(str(value)).timestamp()
        except (TypeError, ValueError, OverflowError):
            return None
        seconds = retry_at - clock()
    if not math.isfinite(seconds):
        return None
    return max(0.0, seconds)


def _maxlag_seconds(error: Exception) -> float | None:
    for source in _exception_sources(error):
        other = getattr(source, "other", None)
        if not isinstance(other, dict):
            continue
        try:
            lag = float(other["lag"])
        except (KeyError, TypeError, ValueError):
            continue
        if math.isfinite(lag) and lag >= 0:
            return lag
    return None


__all__ = [
    "DEFAULT_MAX_WAIT_SECONDS",
    "DEFAULT_REQUESTS_PER_MINUTE",
    "WikimediaRateLimitError",
    "WikimediaRateLimiter",
]
