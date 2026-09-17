#!/usr/bin/env python3
"""Persist half-hourly snapshots of the retained page-check statistics."""

import argparse
import calendar
import configparser
import logging
import math
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import quote, urlsplit

import psycopg2
import requests

try:
    from scripts.refresh_materialized_views import configure_logging
except ModuleNotFoundError:  # Direct execution adds scripts/, not the repository root, to sys.path.
    from refresh_materialized_views import configure_logging

LOGGER = logging.getLogger(__name__)
DEFAULT_PAGE_CHECKER_URL = "http://127.0.0.1:8000"
DEFAULT_LANGUAGES = ("mg",)
LOCK_NAME = "botjagwar_snapshot_page_check_statistics"
REQUEST_TIMEOUT_SECONDS = (3.05, 15)
PERIODS = (
    "today",
    "last_7_days",
    "current_week",
    "current_month",
    "last_3_months",
    "last_6_months",
)
RESULT_STATUSES = ("good", "fixed", "unverifiable", "error")
GRADES = frozenset({"A", "B", "C", "D", "E"})
LANGUAGE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,10}$")


def _database_uri(value: str) -> str:
    """Return a psycopg2-compatible PostgreSQL URI."""
    database_uri = value.strip().replace("postgresql+psycopg2://", "postgresql://", 1)
    if not database_uri.startswith(("postgresql://", "postgres://")):
        raise ValueError("Page-check statistics snapshots require a PostgreSQL database URI")
    return database_uri


def _page_checker_url(value: str) -> str:
    """Validate and normalize the configured page-checker base URL."""
    url = value.strip().rstrip("/")
    parsed = urlsplit(url)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("page_check_statistics_url must be an HTTP(S) base URL without credentials or a query")
    return url


def _languages(value: str) -> tuple[str, ...]:
    """Parse the configured comma-separated Wiktionary language codes."""
    languages = tuple(dict.fromkeys(language.strip() for language in value.split(",") if language.strip()))
    if not languages or any(not LANGUAGE_PATTERN.fullmatch(language) for language in languages):
        raise ValueError("page_check_statistics_languages must contain comma-separated language codes")
    return languages


def load_snapshot_configuration(config_path: Path) -> tuple[str, str, tuple[str, ...]]:
    """Load the database, page-checker URL, and sampled languages."""
    parser = configparser.ConfigParser(interpolation=None)
    if not parser.read(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    try:
        database_uri = parser.get("global", "database_uri")
        page_checker_url = parser.get(
            "global", "page_check_statistics_url", fallback=DEFAULT_PAGE_CHECKER_URL
        )
        languages = parser.get(
            "global",
            "page_check_statistics_languages",
            fallback=",".join(DEFAULT_LANGUAGES),
        )
    except (configparser.NoOptionError, configparser.NoSectionError) as exc:
        raise ValueError(f"database_uri is not configured in {config_path}") from exc
    return _database_uri(database_uri), _page_checker_url(page_checker_url), _languages(languages)


def _finite_number(value: Any, field: str) -> float:
    """Return a finite JSON number or reject the statistics payload."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuntimeError(f"Page-check statistics field {field} must be a number.")
    number = float(value)
    if not math.isfinite(number):
        raise RuntimeError(f"Page-check statistics field {field} must be finite.")
    return number


def _count(value: Any, field: str) -> int:
    """Return a non-negative JSON integer or reject the statistics payload."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RuntimeError(f"Page-check statistics field {field} must be a non-negative integer.")
    return value


def _grade(percentage: float) -> str:
    """Return the grade represented by a page-check percentage."""
    if percentage >= 90:
        return "A"
    if percentage >= 80:
        return "B"
    if percentage >= 70:
        return "C"
    if percentage >= 60:
        return "D"
    return "E"


def _subtract_calendar_months(value: datetime, months: int) -> datetime:
    """Subtract UTC calendar months while clamping invalid month-end days."""
    month_index = value.month - 1 - months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def _period_bounds(generated_at: float) -> dict[str, tuple[float, float]]:
    """Return the canonical UTC bounds represented by a live response."""
    current = datetime.fromtimestamp(generated_at, tz=timezone.utc)
    day_start = current.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = day_start - timedelta(days=current.weekday())
    month_start = day_start.replace(day=1)
    return {
        "today": (day_start.timestamp(), generated_at),
        "last_7_days": ((current - timedelta(days=7)).timestamp(), generated_at),
        "current_week": (week_start.timestamp(), generated_at),
        "current_month": (month_start.timestamp(), generated_at),
        "last_3_months": (_subtract_calendar_months(current, 3).timestamp(), generated_at),
        "last_6_months": (_subtract_calendar_months(current, 6).timestamp(), generated_at),
    }


def validate_page_check_statistics(payload: Any, language: str) -> dict[str, Any]:
    """Validate one live page-check statistics response before persistence."""
    if not isinstance(payload, dict):
        raise RuntimeError("Page-check statistics response must be a JSON object.")
    if payload.get("language") != language or payload.get("timezone") != "UTC":
        raise RuntimeError("Page-check statistics response has unexpected language or timezone metadata.")

    generated_at = _finite_number(payload.get("generated_at"), "generated_at")
    try:
        expected_bounds = _period_bounds(generated_at)
    except (OverflowError, OSError, ValueError) as exc:
        raise RuntimeError("Page-check statistics generated_at is outside the supported range.") from exc

    retention_limit = _count(payload.get("retention_limit"), "retention_limit")
    retained_job_count = _count(payload.get("retained_job_count"), "retained_job_count")
    if retention_limit < 1 or retained_job_count > retention_limit:
        raise RuntimeError("Page-check statistics retention metadata is inconsistent.")

    statistics = payload.get("statistics")
    if not isinstance(statistics, list) or len(statistics) != len(PERIODS):
        raise RuntimeError("Page-check statistics response must contain all six periods.")

    seen_periods: set[str] = set()
    for index, statistic in enumerate(statistics):
        if not isinstance(statistic, dict):
            raise RuntimeError(f"Page-check statistics period {index} must be a JSON object.")
        period = statistic.get("period")
        if period not in PERIODS or period in seen_periods:
            raise RuntimeError("Page-check statistics periods must be unique and canonical.")
        seen_periods.add(period)

        period_start = _finite_number(statistic.get("period_start"), f"{period}.period_start")
        period_end = _finite_number(statistic.get("period_end"), f"{period}.period_end")
        try:
            datetime.fromtimestamp(period_start, tz=timezone.utc)
            datetime.fromtimestamp(period_end, tz=timezone.utc)
        except (OverflowError, OSError, ValueError) as exc:
            raise RuntimeError(f"Page-check statistics period {period} has unsupported bounds.") from exc
        expected_start, expected_end = expected_bounds[period]
        if not math.isclose(period_start, expected_start, rel_tol=0.0, abs_tol=0.001) or not math.isclose(
            period_end, expected_end, rel_tol=0.0, abs_tol=0.001
        ):
            raise RuntimeError(f"Page-check statistics period {period} has noncanonical UTC bounds.")

        job_count = _count(statistic.get("job_count"), f"{period}.job_count")
        checked_count = _count(statistic.get("checked_count"), f"{period}.checked_count")
        assessable_count = _count(statistic.get("assessable_count"), f"{period}.assessable_count")
        result_counts = statistic.get("result_counts")
        if not isinstance(result_counts, dict):
            raise RuntimeError(f"Page-check statistics period {period} has invalid result counts.")
        counts = {
            status: _count(result_counts.get(status), f"{period}.result_counts.{status}")
            for status in RESULT_STATUSES
        }
        if checked_count != sum(counts.values()) or checked_count > job_count:
            raise RuntimeError(f"Page-check statistics period {period} has inconsistent checked counts.")
        if assessable_count != counts["good"] + counts["fixed"]:
            raise RuntimeError(f"Page-check statistics period {period} has an inconsistent assessable count.")

        percentage = statistic.get("good_percentage")
        grade = statistic.get("grade")
        if job_count == 0:
            if percentage is not None or grade is not None:
                raise RuntimeError(f"Page-check statistics period {period} must not grade empty data.")
            continue
        percentage_number = _finite_number(percentage, f"{period}.good_percentage")
        expected_percentage = round(counts["good"] * 100 / job_count, 1)
        if percentage_number != expected_percentage or grade not in GRADES or grade != _grade(percentage_number):
            raise RuntimeError(f"Page-check statistics period {period} has an inconsistent score or grade.")

    if seen_periods != set(PERIODS):
        raise RuntimeError("Page-check statistics response is missing a canonical period.")
    return payload


def fetch_page_check_statistics(page_checker_url: str, language: str) -> dict[str, Any]:
    """Fetch and validate one language's live retained-job statistics."""
    url = (
        f"{page_checker_url}/wiktionary-pages/{quote(language, safe='')}"
        "/check-jobs/statistics"
    )
    response = requests.get(
        url,
        headers={"Accept": "application/json", "User-Agent": "Botjagwar page-check statistics sampler"},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError("Page-check statistics endpoint returned invalid JSON.") from exc
    return validate_page_check_statistics(payload, language)


def _snapshot_rows(payload: dict[str, Any]) -> list[tuple[Any, ...]]:
    """Flatten one validated response into the rows stored by migrations 010/011."""
    generated_at = datetime.fromtimestamp(float(payload["generated_at"]), tz=timezone.utc)
    snapshot_at = generated_at.replace(
        minute=0 if generated_at.minute < 30 else 30,
        second=0,
        microsecond=0,
    )
    rows = []
    for statistic in payload["statistics"]:
        result_counts = statistic["result_counts"]
        rows.append(
            (
                payload["language"],
                snapshot_at,
                statistic["period"],
                generated_at,
                datetime.fromtimestamp(float(statistic["period_start"]), tz=timezone.utc),
                datetime.fromtimestamp(float(statistic["period_end"]), tz=timezone.utc),
                payload["retention_limit"],
                payload["retained_job_count"],
                statistic["job_count"],
                statistic["checked_count"],
                statistic["assessable_count"],
                result_counts["good"],
                result_counts["fixed"],
                result_counts["unverifiable"],
                result_counts["error"],
                statistic["good_percentage"],
                statistic["grade"],
            )
        )
    return rows


def write_page_check_snapshots(database_uri: str, payloads: Sequence[dict[str, Any]]) -> int:
    """Store the first validated statistics in each generated half-hour bucket."""
    rows = [row for payload in payloads for row in _snapshot_rows(payload)]
    stored_rows = 0
    connection = psycopg2.connect(database_uri)
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_try_advisory_xact_lock(hashtext(%s))", (LOCK_NAME,))
                if not cursor.fetchone()[0]:
                    LOGGER.info("Another page-check statistics snapshot is running; exiting.")
                    return 0
                cursor.execute(
                    "SELECT to_regclass('public.page_check_statistics_snapshots') IS NOT NULL"
                )
                if not cursor.fetchone()[0]:
                    raise RuntimeError(
                        "Table public.page_check_statistics_snapshots is not installed"
                    )
                cursor.executemany(
                    """
                    INSERT INTO public.page_check_statistics_snapshots (
                        language, snapshot_at, period, generated_at, period_start, period_end,
                        retention_limit, retained_job_count, job_count, checked_count,
                        assessable_count, good_count, fixed_count, unverifiable_count,
                        error_count, good_percentage, grade
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (language, snapshot_at, period) DO NOTHING
                    """,
                    rows,
                )
                stored_rows = cursor.rowcount
    finally:
        connection.close()
    LOGGER.info(
        "Stored %d of %d page-check statistics period snapshots.",
        stored_rows,
        len(rows),
    )
    return stored_rows


def validate_snapshot_storage(database_uri: str) -> None:
    """Verify migrations 010/011 with a probe write that is always rolled back."""
    generated_at = datetime.now(tz=timezone.utc)
    snapshot_at = generated_at.replace(
        minute=0 if generated_at.minute < 30 else 30,
        second=0,
        microsecond=0,
    )
    connection = psycopg2.connect(database_uri)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    to_regclass('public.page_check_statistics_snapshots') IS NOT NULL,
                    to_regprocedure('public.page_check_score_history(text,text,integer)') IS NOT NULL,
                    EXISTS (
                        SELECT 1
                        FROM pg_constraint
                        WHERE conname = 'page_check_statistics_snapshots_job_score_check'
                          AND conrelid = to_regclass('public.page_check_statistics_snapshots')
                    )
                """
            )
            table_exists, function_exists, score_contract_exists = cursor.fetchone()
            if not table_exists or not function_exists or not score_contract_exists:
                raise RuntimeError("Page-check statistics migrations 010 and 011 are not installed")
            cursor.execute(
                """
                INSERT INTO public.page_check_statistics_snapshots (
                    language, snapshot_at, period, generated_at, period_start, period_end,
                    retention_limit, retained_job_count, job_count, checked_count,
                    assessable_count, good_count, fixed_count, unverifiable_count,
                    error_count, good_percentage, grade
                ) VALUES (
                    '_check_', %s, 'today', %s, %s, %s,
                    1, 1, 1, 1, 0, 0, 0, 0, 1, 0.0, 'E'
                )
                ON CONFLICT (language, snapshot_at, period) DO NOTHING
                """,
                (snapshot_at, generated_at, snapshot_at, generated_at),
            )
            cursor.execute(
                "SELECT count(*) FROM public.page_check_score_history('_check_', 'today', 2)"
            )
            if cursor.fetchone()[0] < 1:
                raise RuntimeError("The configured database role cannot read page-check statistics")
    finally:
        connection.rollback()
        connection.close()


def snapshot_page_check_statistics(
    database_uri: str,
    page_checker_url: str,
    languages: Sequence[str],
) -> int:
    """Fetch and persist each configured language without blocking the others."""
    stored_rows = 0
    failed_languages: list[str] = []
    for language in languages:
        try:
            payload = fetch_page_check_statistics(page_checker_url, language)
            stored_rows += write_page_check_snapshots(database_uri, [payload])
        except (
            ValueError,
            RuntimeError,
            ArithmeticError,
            OSError,
            psycopg2.Error,
            requests.RequestException,
        ):
            failed_languages.append(language)
            LOGGER.exception("Could not snapshot page-check statistics for %s.", language)
    if failed_languages:
        raise RuntimeError(
            f"Page-check statistics failed for languages: {', '.join(failed_languages)}"
        )
    return stored_rows


def main(check_storage: bool = False) -> int:
    """Run the configured page-check statistics snapshot job."""
    configure_logging()
    config_path = Path(os.environ.get("BOTJAGWAR_CONFIG", "/etc/botjagwar/config.ini"))
    try:
        database_uri, page_checker_url, languages = load_snapshot_configuration(config_path)
        if check_storage:
            validate_snapshot_storage(database_uri)
        else:
            snapshot_page_check_statistics(database_uri, page_checker_url, languages)
    except (
        FileNotFoundError,
        ValueError,
        RuntimeError,
        OSError,
        psycopg2.Error,
        requests.RequestException,
    ):
        LOGGER.exception("Page-check statistics snapshot did not complete successfully.")
        return 1
    return 0


if __name__ == "__main__":
    argument_parser = argparse.ArgumentParser(description=__doc__)
    argument_parser.add_argument(
        "--check-storage",
        action="store_true",
        help="validate migrations 010/011 and exit without fetching statistics",
    )
    sys.exit(main(check_storage=argument_parser.parse_args().check_storage))
