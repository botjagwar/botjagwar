import fcntl
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts.refresh_dashboard_statistics import (
    LOCK_FILENAME,
    acquire_statistics_lock,
    fetch_dashboard_statistics,
    json_default,
    main,
    render_statistics,
    validate_statistics_file,
    validate_statistics_snapshot,
    write_dashboard_statistics,
)


def statistics_row(entry_count: int = 12) -> dict[str, object]:
    """Return one complete row in the shape consumed by Atlas."""
    return {
        "period": "last_day",
        "period_start": "2026-08-13T18:00:00+00:00",
        "period_end": "2026-08-14T18:00:00+00:00",
        "entry_count": entry_count,
        "translated_languages": [{"language": "fr", "translated_entries": 3}],
        "generated_at": "2026-08-14T18:00:00+00:00",
        "missing_timestamp_count": 0,
    }


def statistics_response(*rows: dict[str, object]) -> bytes:
    """Serialize rows the way the materialized view snapshot would."""
    return render_statistics(list(rows)).encode("utf-8")


def hold_refresh_lock(directory: Path):
    """Acquire the refresh lock out-of-band and return its open file handle."""
    lock_file = (directory / LOCK_FILENAME).open("a", encoding="utf-8")
    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    return lock_file


def test_json_default_formats_timestamps_like_postgrest() -> None:
    """Timestamps are serialized as ISO 8601 strings the dashboard can parse."""
    moment = datetime(2026, 8, 14, 18, 0, 0, tzinfo=timezone.utc)

    assert json_default(moment) == "2026-08-14T18:00:00+00:00"


def test_json_default_rejects_unexpected_types() -> None:
    """Unknown values fail loudly instead of producing silent output."""
    with pytest.raises(TypeError, match="not JSON serializable"):
        json_default(object())


def test_render_statistics_produces_the_postgrest_array_shape() -> None:
    """The rendered payload is a JSON array keyed like the materialized view rows."""
    rows = [
        {
            "period": "last_day",
            "period_start": datetime(2026, 8, 13, 18, 0, 0, tzinfo=timezone.utc),
            "period_end": datetime(2026, 8, 14, 18, 0, 0, tzinfo=timezone.utc),
            "entry_count": 12,
            "translated_languages": [{"language": "fr", "translated_entries": 3}],
            "generated_at": datetime(2026, 8, 14, 18, 0, 0, tzinfo=timezone.utc),
            "missing_timestamp_count": 0,
        }
    ]

    payload = render_statistics(rows)

    assert payload == (
        '[{"period":"last_day","period_start":"2026-08-13T18:00:00+00:00",'
        '"period_end":"2026-08-14T18:00:00+00:00","entry_count":12,'
        '"translated_languages":[{"language":"fr","translated_entries":3}],'
        '"generated_at":"2026-08-14T18:00:00+00:00","missing_timestamp_count":0}]'
    )


@pytest.mark.parametrize(
    "snapshot",
    [[], {}, ["not-an-object"], [{"period": "last_day"}]],
)
def test_validate_statistics_snapshot_rejects_incomplete_shapes(snapshot: object) -> None:
    """Atlas is never served an empty, non-array, non-object, or incomplete snapshot."""
    with pytest.raises(RuntimeError):
        validate_statistics_snapshot(snapshot)


def test_validate_statistics_file_accepts_all_atlas_fields(tmp_path: Path) -> None:
    """A persisted non-empty array with all Atlas fields is valid."""
    snapshot = tmp_path / "dashboard-statistics.json"
    snapshot.write_text(render_statistics([statistics_row()]), encoding="utf-8")

    validate_statistics_file(snapshot)


def test_fetch_dashboard_statistics_reads_the_materialized_view(mocker) -> None:
    """The six periods are read from the configured database in canonical order."""
    connection = mocker.patch("scripts.refresh_dashboard_statistics.psycopg2.connect").return_value
    cursor = connection.cursor.return_value.__enter__.return_value
    moment = datetime(2026, 8, 14, 18, 0, 0, tzinfo=timezone.utc)
    cursor.fetchall.return_value = [
        (
            "last_day",
            datetime(2026, 8, 13, 18, 0, 0, tzinfo=timezone.utc),
            moment,
            12,
            [{"language": "fr", "translated_entries": 3}],
            moment,
            0,
        )
    ]

    rows = fetch_dashboard_statistics("postgresql://database")

    assert rows == [
        {
            "period": "last_day",
            "period_start": datetime(2026, 8, 13, 18, 0, 0, tzinfo=timezone.utc),
            "period_end": moment,
            "entry_count": 12,
            "translated_languages": [{"language": "fr", "translated_entries": 3}],
            "generated_at": moment,
            "missing_timestamp_count": 0,
        }
    ]
    statement = str(cursor.execute.call_args.args[0])
    assert "atlas_dashboard_statistics_mv" in statement
    assert "ORDER BY CASE period" in statement


def test_fetch_dashboard_statistics_returns_periods_in_canonical_order(mocker) -> None:
    """The snapshot preserves the RPC's period ordering."""
    import re

    connection = mocker.patch("scripts.refresh_dashboard_statistics.psycopg2.connect").return_value
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = [
        (
            "last_day",
            datetime(2026, 8, 13, 18, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 8, 14, 18, 0, 0, tzinfo=timezone.utc),
            12,
            [{"language": "fr", "translated_entries": 3}],
            datetime(2026, 8, 14, 18, 0, 0, tzinfo=timezone.utc),
            0,
        )
    ]

    fetch_dashboard_statistics("postgresql://database")

    statement = str(cursor.execute.call_args.args[0])
    periods = re.findall(r"Literal\('([^']+)'\)", statement)
    assert periods == [
        "last_day",
        "last_7_days",
        "last_week",
        "last_month",
        "year_to_date",
        "last_year",
    ]


def test_fetch_dashboard_statistics_requires_rows(mocker) -> None:
    """An empty materialized view is reported instead of blanking the snapshot."""
    connection = mocker.patch("scripts.refresh_dashboard_statistics.psycopg2.connect").return_value
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = []

    with pytest.raises(RuntimeError, match="returned no rows"):
        fetch_dashboard_statistics("postgresql://database")


def test_fetch_dashboard_statistics_raises_on_database_errors(mocker) -> None:
    """Unreachable databases surface as refresh failures."""
    import psycopg2

    mocker.patch(
        "scripts.refresh_dashboard_statistics.psycopg2.connect",
        side_effect=psycopg2.OperationalError("connection refused"),
    )

    with pytest.raises(psycopg2.OperationalError, match="connection refused"):
        fetch_dashboard_statistics("postgresql://database")


def test_write_dashboard_statistics_writes_and_replaces_atomically(mocker, tmp_path: Path) -> None:
    """A snapshot is written through a temporary file and atomically renamed."""
    output = tmp_path / "atlas" / "logs" / "dashboard-statistics.json"
    mocker.patch(
        "scripts.refresh_dashboard_statistics.fetch_dashboard_statistics",
        return_value=[statistics_row()],
    )

    assert write_dashboard_statistics("postgresql://database", output) == 1

    validate_statistics_file(output)
    assert list(output.parent.glob(".dashboard-statistics.json.*")) == []
    released_lock = acquire_statistics_lock(output.parent / LOCK_FILENAME)
    assert released_lock is not None
    released_lock.close()


def test_write_dashboard_statistics_skips_an_overlapping_refresh(mocker, tmp_path: Path) -> None:
    """A second cron process exits before fetching or replacing the snapshot."""
    output = tmp_path / "dashboard-statistics.json"
    previous_snapshot = render_statistics([statistics_row(entry_count=5)])
    output.write_text(previous_snapshot, encoding="utf-8")
    fetch = mocker.patch("scripts.refresh_dashboard_statistics.fetch_dashboard_statistics")
    holder = hold_refresh_lock(tmp_path)

    try:
        assert write_dashboard_statistics("postgresql://database", output) == 0
    finally:
        holder.close()

    fetch.assert_not_called()
    assert output.read_text(encoding="utf-8") == previous_snapshot


@pytest.mark.parametrize("existing_snapshot", [None, "not-json", "[]", '[{"period":"last_day"}]'])
def test_write_dashboard_statistics_fails_on_lock_contention_without_valid_snapshot(
    mocker, tmp_path: Path, existing_snapshot: str | None
) -> None:
    """Lock contention is unsuccessful unless Nginx already has a valid snapshot."""
    output = tmp_path / "dashboard-statistics.json"
    if existing_snapshot is not None:
        output.write_text(existing_snapshot, encoding="utf-8")
    fetch = mocker.patch("scripts.refresh_dashboard_statistics.fetch_dashboard_statistics")
    holder = hold_refresh_lock(tmp_path)

    try:
        with pytest.raises(RuntimeError, match="no valid snapshot"):
            write_dashboard_statistics("postgresql://database", output)
    finally:
        holder.close()

    fetch.assert_not_called()


def test_main_fails_on_lock_contention_without_valid_snapshot(mocker, monkeypatch, tmp_path: Path) -> None:
    """The cron entry reports failure when contention leaves no snapshot for Nginx."""
    config = tmp_path / "config.ini"
    config.write_text("[global]\ndatabase_uri = postgresql://database\n", encoding="utf-8")
    monkeypatch.setenv("BOTJAGWAR_CONFIG", str(config))
    monkeypatch.setenv("BOTJAGWAR_ATLAS_STATE_DIR", str(tmp_path / "atlas"))
    fetch = mocker.patch("scripts.refresh_dashboard_statistics.fetch_dashboard_statistics")
    lock_dir = tmp_path / "atlas" / "logs"
    lock_dir.mkdir(parents=True)
    holder = hold_refresh_lock(lock_dir)

    try:
        assert main() == 1
    finally:
        holder.close()

    fetch.assert_not_called()


def test_write_dashboard_statistics_keeps_the_previous_snapshot_when_empty(mocker, tmp_path: Path) -> None:
    """An empty result never blanks the file that Nginx serves."""
    output = tmp_path / "dashboard-statistics.json"
    previous_snapshot = render_statistics([statistics_row(entry_count=5)])
    output.write_text(previous_snapshot, encoding="utf-8")
    mocker.patch("scripts.refresh_dashboard_statistics.fetch_dashboard_statistics", return_value=[])

    with pytest.raises(RuntimeError, match="returned no rows"):
        write_dashboard_statistics("postgresql://database", output)

    assert output.read_text(encoding="utf-8") == previous_snapshot


def test_write_dashboard_statistics_keeps_previous_snapshot_when_rows_are_incomplete(mocker, tmp_path: Path) -> None:
    """Incomplete rows fail validation before the previous snapshot is replaced."""
    output = tmp_path / "dashboard-statistics.json"
    previous_snapshot = render_statistics([statistics_row(entry_count=5)])
    output.write_text(previous_snapshot, encoding="utf-8")
    mocker.patch(
        "scripts.refresh_dashboard_statistics.fetch_dashboard_statistics",
        return_value=[{"period": "last_day"}],
    )

    with pytest.raises(RuntimeError, match="missing fields"):
        write_dashboard_statistics("postgresql://database", output)

    assert output.read_text(encoding="utf-8") == previous_snapshot


def test_write_dashboard_statistics_keeps_previous_snapshot_when_fetch_fails(mocker, tmp_path: Path) -> None:
    """A failed fetch never blanks the file that Nginx serves."""
    output = tmp_path / "dashboard-statistics.json"
    previous_snapshot = render_statistics([statistics_row(entry_count=5)])
    output.write_text(previous_snapshot, encoding="utf-8")
    mocker.patch(
        "scripts.refresh_dashboard_statistics.fetch_dashboard_statistics",
        side_effect=RuntimeError("Could not read the atlas_dashboard_statistics materialized view"),
    )

    with pytest.raises(RuntimeError, match="materialized view"):
        write_dashboard_statistics("postgresql://database", output)

    assert output.read_text(encoding="utf-8") == previous_snapshot


def test_fetch_dashboard_statistics_response_shape_matches_serialized_snapshot(mocker) -> None:
    """The materialized view tuple shape renders into the JSON consumed by Atlas."""
    connection = mocker.patch("scripts.refresh_dashboard_statistics.psycopg2.connect").return_value
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = [
        (
            "last_day",
            datetime(2026, 8, 13, 18, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 8, 14, 18, 0, 0, tzinfo=timezone.utc),
            12,
            [{"language": "fr", "translated_entries": 3}],
            datetime(2026, 8, 14, 18, 0, 0, tzinfo=timezone.utc),
            0,
        )
    ]

    rows = fetch_dashboard_statistics("postgresql://database")

    validate_statistics_snapshot(rows)
    assert render_statistics(rows) == statistics_response(statistics_row()).decode("utf-8")
