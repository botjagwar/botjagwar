#!/usr/bin/env python3
"""Refresh the Atlas dashboard statistics snapshot Nginx serves as a static file."""

import fcntl
import json
import logging
import os
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import TextIO

import psycopg2
from psycopg2 import sql

try:
    from scripts.refresh_materialized_views import configure_logging, load_database_uri
except ModuleNotFoundError:  # Direct execution adds scripts/, not the repository root, to sys.path.
    from refresh_materialized_views import configure_logging, load_database_uri

LOGGER = logging.getLogger(__name__)
DEFAULT_ATLAS_STATE_DIR = Path("/var/lib/botjagwar/atlas")
STATISTICS_FILENAME = "logs/dashboard-statistics.json"
LOCK_FILENAME = ".dashboard-statistics-refresh.lock"
MATERIALIZED_VIEW_SCHEMA = "public"
MATERIALIZED_VIEW_NAME = "atlas_dashboard_statistics_mv"
PERIOD_ORDER = (
    "last_day",
    "last_7_days",
    "last_week",
    "last_month",
    "year_to_date",
    "last_year",
)
REQUIRED_STATISTICS_FIELDS = frozenset(
    {
        "period",
        "period_start",
        "period_end",
        "entry_count",
        "translated_languages",
        "generated_at",
        "missing_timestamp_count",
    }
)


def json_default(value: object) -> str:
    """Serialize database timestamps the way PostgREST does."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def render_statistics(rows: list[dict]) -> str:
    """Serialize the statistics rows as the JSON array expected by the dashboard."""
    return json.dumps(rows, default=json_default, ensure_ascii=False, separators=(",", ":"))


def validate_statistics_snapshot(snapshot: object) -> None:
    """Validate the non-empty array shape consumed by the Atlas dashboard."""
    if not isinstance(snapshot, list) or not snapshot:
        raise RuntimeError("Dashboard statistics snapshot must be a non-empty JSON array.")
    for index, row in enumerate(snapshot):
        if not isinstance(row, dict):
            raise RuntimeError(f"Dashboard statistics row {index} is not a JSON object.")
        missing_fields = REQUIRED_STATISTICS_FIELDS - row.keys()
        if missing_fields:
            missing = ", ".join(sorted(missing_fields))
            raise RuntimeError(f"Dashboard statistics row {index} is missing fields: {missing}.")


def validate_statistics_file(snapshot_path: Path) -> None:
    """Load and validate a dashboard statistics snapshot file."""
    with snapshot_path.open(encoding="utf-8") as snapshot_file:
        validate_statistics_snapshot(json.load(snapshot_file))


def acquire_statistics_lock(lock_path: Path) -> TextIO | None:
    """Acquire the exclusive snapshot refresh lock, or None when already held."""
    lock_file = lock_path.open("a", encoding="utf-8")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock_file.close()
        return None
    return lock_file


def fetch_dashboard_statistics(database_uri: str) -> list[dict]:
    """Read the dashboard statistics rows from the materialized view."""
    period_order = sql.SQL(" ").join(
        sql.SQL("WHEN {} THEN {}").format(sql.Literal(period), sql.Literal(index + 1))
        for index, period in enumerate(PERIOD_ORDER)
    )
    query = sql.SQL(
        "SELECT period, period_start, period_end, entry_count, translated_languages, "
        "generated_at, missing_timestamp_count "
        "FROM {}.{} "
        "ORDER BY CASE period {} ELSE {} END"
    ).format(
        sql.Identifier(MATERIALIZED_VIEW_SCHEMA),
        sql.Identifier(MATERIALIZED_VIEW_NAME),
        period_order,
        sql.Literal(len(PERIOD_ORDER) + 1),
    )
    connection = psycopg2.connect(database_uri)
    try:
        with connection.cursor() as cursor:
            cursor.execute(query)
            rows = [
                {
                    "period": period,
                    "period_start": period_start,
                    "period_end": period_end,
                    "entry_count": entry_count,
                    "translated_languages": translated_languages,
                    "generated_at": generated_at,
                    "missing_timestamp_count": missing_timestamp_count,
                }
                for (
                    period,
                    period_start,
                    period_end,
                    entry_count,
                    translated_languages,
                    generated_at,
                    missing_timestamp_count,
                ) in cursor.fetchall()
            ]
    finally:
        connection.close()
    if not rows:
        raise RuntimeError("The atlas_dashboard_statistics materialized view returned no rows.")
    return rows


def write_dashboard_statistics(database_uri: str, output_path: Path) -> int:
    """Fetch dashboard statistics from the materialized view and atomically replace the snapshot."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lock_file = acquire_statistics_lock(output_path.parent / LOCK_FILENAME)
    if lock_file is None:
        try:
            validate_statistics_file(output_path)
        except (OSError, ValueError, RuntimeError) as exc:
            raise RuntimeError("Another dashboard statistics refresh is running and no valid snapshot exists.") from exc
        LOGGER.info("Another dashboard statistics refresh is already running; keeping the valid snapshot.")
        return 0
    try:
        rows = fetch_dashboard_statistics(database_uri)
        if not rows:
            raise RuntimeError("The atlas_dashboard_statistics materialized view returned no rows.")
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{output_path.name}.", dir=output_path.parent, text=True)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as temporary_file:
                temporary_file.write(render_statistics(rows))
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            validate_statistics_file(Path(temporary_name))
            os.chmod(temporary_name, 0o644)
            os.replace(temporary_name, output_path)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)
    finally:
        lock_file.close()
    LOGGER.info("Wrote %d dashboard statistics periods to %s.", len(rows), output_path)
    return len(rows)


def main() -> int:
    """Run the configured dashboard statistics snapshot job."""
    configure_logging()
    config_path = Path(os.environ.get("BOTJAGWAR_CONFIG", "/etc/botjagwar/config.ini"))
    state_dir = Path(os.environ.get("BOTJAGWAR_ATLAS_STATE_DIR", DEFAULT_ATLAS_STATE_DIR))
    try:
        write_dashboard_statistics(load_database_uri(config_path), state_dir / STATISTICS_FILENAME)
    except (FileNotFoundError, ValueError, RuntimeError, OSError, psycopg2.Error):
        LOGGER.exception("Dashboard statistics refresh did not complete successfully.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
