from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest
import psycopg2
import requests

from scripts.snapshot_page_check_statistics import (
    PERIODS,
    fetch_page_check_statistics,
    load_snapshot_configuration,
    main,
    snapshot_page_check_statistics,
    validate_page_check_statistics,
    validate_snapshot_storage,
    write_page_check_snapshots,
)


GENERATED_AT = datetime(2026, 8, 19, 12, 17, 45, tzinfo=timezone.utc).timestamp()
PERIOD_STARTS = {
    "today": datetime(2026, 8, 19, tzinfo=timezone.utc).timestamp(),
    "last_7_days": datetime(2026, 8, 12, 12, 17, 45, tzinfo=timezone.utc).timestamp(),
    "current_week": datetime(2026, 8, 17, tzinfo=timezone.utc).timestamp(),
    "current_month": datetime(2026, 8, 1, tzinfo=timezone.utc).timestamp(),
    "last_3_months": datetime(2026, 5, 19, 12, 17, 45, tzinfo=timezone.utc).timestamp(),
    "last_6_months": datetime(2026, 2, 19, 12, 17, 45, tzinfo=timezone.utc).timestamp(),
}


def statistics_payload(language: str = "mg") -> dict[str, object]:
    """Return a complete live statistics response."""
    return {
        "language": language,
        "generated_at": GENERATED_AT,
        "timezone": "UTC",
        "retention_limit": 200,
        "retained_job_count": 12,
        "statistics": [
            {
                "period": period,
                "period_start": PERIOD_STARTS[period],
                "period_end": GENERATED_AT,
                "job_count": 12,
                "checked_count": 10,
                "assessable_count": 8,
                "result_counts": {"good": 6, "fixed": 2, "unverifiable": 1, "error": 1},
                "good_percentage": 50.0,
                "grade": "E",
            }
            for period in PERIODS
        ],
    }


def test_load_snapshot_configuration_uses_application_database_and_defaults(tmp_path: Path) -> None:
    """The sampler defaults to the local Malagasy page checker."""
    config = tmp_path / "config.ini"
    config.write_text(
        "[global]\ndatabase_uri=postgresql+psycopg2://user:password@database/botjagwar\n",
        encoding="utf-8",
    )

    assert load_snapshot_configuration(config) == (
        "postgresql://user:password@database/botjagwar",
        "http://127.0.0.1:8000",
        ("mg",),
    )


def test_load_snapshot_configuration_accepts_multiple_unique_languages(tmp_path: Path) -> None:
    """Configured language lists are trimmed and deduplicated in order."""
    config = tmp_path / "config.ini"
    config.write_text(
        """[global]
database_uri=postgresql://database
page_check_statistics_url=https://checker.example.test/base/
page_check_statistics_languages=mg, en,mg
""",
        encoding="utf-8",
    )

    assert load_snapshot_configuration(config) == (
        "postgresql://database",
        "https://checker.example.test/base",
        ("mg", "en"),
    )


@pytest.mark.parametrize(
    ("configuration", "message"),
    [
        ("[global]\ndatabase_uri=sqlite:///test.db\n", "PostgreSQL"),
        (
            "[global]\ndatabase_uri=postgresql://database\npage_check_statistics_url=http://user:pass@host\n",
            "base URL",
        ),
        (
            "[global]\ndatabase_uri=postgresql://database\npage_check_statistics_languages=mg,../en\n",
            "language codes",
        ),
    ],
)
def test_load_snapshot_configuration_rejects_unsafe_values(
    tmp_path: Path, configuration: str, message: str
) -> None:
    """Invalid database, URL, and path-segment language values fail closed."""
    config = tmp_path / "config.ini"
    config.write_text(configuration, encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_snapshot_configuration(config)


def test_validate_page_check_statistics_accepts_complete_and_empty_periods() -> None:
    """Canonical scores and explicitly ungraded empty periods are accepted."""
    payload = statistics_payload()
    empty_period = payload["statistics"][0]
    empty_period.update(
        {
            "job_count": 0,
            "checked_count": 0,
            "assessable_count": 0,
            "result_counts": {"good": 0, "fixed": 0, "unverifiable": 0, "error": 0},
            "good_percentage": None,
            "grade": None,
        }
    )

    assert validate_page_check_statistics(payload, "mg") is payload


def test_validate_page_check_statistics_scores_non_good_jobs() -> None:
    """A completed error remains in the total-job score denominator."""
    payload = statistics_payload()
    error_period = payload["statistics"][0]
    error_period.update(
        {
            "job_count": 1,
            "checked_count": 1,
            "assessable_count": 0,
            "result_counts": {"good": 0, "fixed": 0, "unverifiable": 0, "error": 1},
            "good_percentage": 0.0,
            "grade": "E",
        }
    )

    assert validate_page_check_statistics(payload, "mg") is payload


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload.update(language="en"),
        lambda payload: payload.update(retained_job_count=201),
        lambda payload: payload["statistics"].pop(),
        lambda payload: payload["statistics"][1].update(period="today"),
        lambda payload: payload["statistics"][0].update(checked_count=9),
        lambda payload: payload["statistics"][0].update(assessable_count=7),
        lambda payload: payload["statistics"][0].update(good_percentage=80.0),
        lambda payload: payload["statistics"][0].update(grade="A"),
        lambda payload: payload["statistics"][0].update(period_start=GENERATED_AT - 3600),
        lambda payload: payload["statistics"][0].update(period_start=PERIOD_STARTS["today"] + 1),
        lambda payload: payload["statistics"][0].update(period_end=1e300),
    ],
)
def test_validate_page_check_statistics_rejects_inconsistent_payloads(mutation) -> None:
    """Malformed metadata, periods, counts, percentages, and grades are rejected."""
    payload = deepcopy(statistics_payload())
    mutation(payload)

    with pytest.raises(RuntimeError):
        validate_page_check_statistics(payload, "mg")


def test_fetch_page_check_statistics_encodes_language_and_validates_json(mocker) -> None:
    """The sampler performs one bounded read against the language statistics route."""
    response = mocker.Mock()
    response.json.return_value = statistics_payload("mg-test")
    get = mocker.patch(
        "scripts.snapshot_page_check_statistics.requests.get", return_value=response
    )

    assert fetch_page_check_statistics("https://checker.test/root", "mg-test")["language"] == "mg-test"
    get.assert_called_once_with(
        "https://checker.test/root/wiktionary-pages/mg-test/check-jobs/statistics",
        headers={
            "Accept": "application/json",
            "User-Agent": "Botjagwar page-check statistics sampler",
        },
        timeout=(3.05, 15),
    )
    response.raise_for_status.assert_called_once_with()


def test_fetch_page_check_statistics_rejects_invalid_json(mocker) -> None:
    """A successful non-JSON response cannot be persisted."""
    response = mocker.Mock()
    response.json.side_effect = requests.exceptions.JSONDecodeError("invalid", "", 0)
    mocker.patch("scripts.snapshot_page_check_statistics.requests.get", return_value=response)

    with pytest.raises(RuntimeError, match="invalid JSON"):
        fetch_page_check_statistics("https://checker.test", "mg")


def test_write_page_check_snapshots_stores_six_rows_in_the_half_hour_bucket(mocker) -> None:
    """Every period is atomically written under the floored generated timestamp."""
    connection = mocker.patch(
        "scripts.snapshot_page_check_statistics.psycopg2.connect"
    ).return_value
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = [(True,), (True,)]
    cursor.rowcount = 6

    assert write_page_check_snapshots("postgresql://database", [statistics_payload()]) == 6

    rows = cursor.executemany.call_args.args[1]
    assert len(rows) == 6
    assert [row[2] for row in rows] == list(PERIODS)
    assert rows[0][1] == datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
    assert rows[0][3] == datetime(2026, 8, 19, 12, 17, 45, tzinfo=timezone.utc)
    assert rows[0][-2:] == (50.0, "E")
    assert "DO NOTHING" in cursor.executemany.call_args.args[0]
    connection.close.assert_called_once_with()


def test_write_page_check_snapshots_skips_an_overlapping_sampler(mocker) -> None:
    """The PostgreSQL advisory lock prevents concurrent writes."""
    connection = mocker.patch(
        "scripts.snapshot_page_check_statistics.psycopg2.connect"
    ).return_value
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (False,)

    assert write_page_check_snapshots("postgresql://database", [statistics_payload()]) == 0
    cursor.executemany.assert_not_called()


def test_write_page_check_snapshots_requires_migration_010(mocker) -> None:
    """A missing snapshot table is reported rather than silently discarding history."""
    connection = mocker.patch(
        "scripts.snapshot_page_check_statistics.psycopg2.connect"
    ).return_value
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = [(True,), (False,)]

    with pytest.raises(RuntimeError, match="is not installed"):
        write_page_check_snapshots("postgresql://database", [statistics_payload()])


def test_validate_snapshot_storage_checks_relation_function_and_role_permissions(mocker) -> None:
    """Installer validation rolls back a real write and reads it through the RPC."""
    connection = mocker.patch(
        "scripts.snapshot_page_check_statistics.psycopg2.connect"
    ).return_value
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = [(True, True, True), (1,)]

    validate_snapshot_storage("postgresql://database")

    statements = [call.args[0] for call in cursor.execute.call_args_list]
    assert any("page_check_statistics_snapshots" in statement for statement in statements)
    assert any("page_check_score_history" in statement for statement in statements)
    connection.rollback.assert_called_once_with()
    connection.close.assert_called_once_with()


@pytest.mark.parametrize(
    "responses",
    [[(False, False, False)], [(True, True, True), (0,)]],
)
def test_validate_snapshot_storage_rejects_missing_or_unreadable_storage(mocker, responses) -> None:
    """A release cannot activate without migrations 010/011 and readable history."""
    connection = mocker.patch(
        "scripts.snapshot_page_check_statistics.psycopg2.connect"
    ).return_value
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = responses

    with pytest.raises(RuntimeError):
        validate_snapshot_storage("postgresql://database")


def test_validate_snapshot_storage_propagates_a_read_only_database(mocker) -> None:
    """ACLs cannot hide a database-level read-only transaction setting."""
    connection = mocker.patch(
        "scripts.snapshot_page_check_statistics.psycopg2.connect"
    ).return_value
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (True, True, True)
    cursor.execute.side_effect = [None, psycopg2.OperationalError("read only")]

    with pytest.raises(psycopg2.OperationalError, match="read only"):
        validate_snapshot_storage("postgresql://database")


def test_snapshot_page_check_statistics_fetches_and_writes_every_language(mocker) -> None:
    """One cron execution stores each configured language independently."""
    fetch = mocker.patch(
        "scripts.snapshot_page_check_statistics.fetch_page_check_statistics",
        side_effect=lambda _url, language: statistics_payload(language),
    )
    write = mocker.patch(
        "scripts.snapshot_page_check_statistics.write_page_check_snapshots", return_value=6
    )

    assert snapshot_page_check_statistics(
        "postgresql://database", "https://checker.test", ("mg", "en")
    ) == 12
    assert [call.args[1] for call in fetch.call_args_list] == ["mg", "en"]
    assert [call.args[1][0]["language"] for call in write.call_args_list] == ["mg", "en"]


def test_snapshot_page_check_statistics_keeps_successful_languages_when_one_fails(mocker) -> None:
    """A failed language is retried later without discarding successful snapshots."""
    fetch = mocker.patch(
        "scripts.snapshot_page_check_statistics.fetch_page_check_statistics",
        side_effect=[statistics_payload("mg"), requests.ConnectionError("offline")],
    )
    write = mocker.patch(
        "scripts.snapshot_page_check_statistics.write_page_check_snapshots", return_value=6
    )

    with pytest.raises(RuntimeError, match="en"):
        snapshot_page_check_statistics(
            "postgresql://database", "https://checker.test", ("mg", "en")
        )

    assert fetch.call_count == 2
    assert write.call_count == 1
    assert write.call_args.args[1][0]["language"] == "mg"


def test_main_loads_the_protected_config_and_reports_failures(mocker, monkeypatch, tmp_path: Path) -> None:
    """Cron configuration is honored and operational errors produce a failing exit status."""
    config = tmp_path / "config.ini"
    config.write_text("[global]\ndatabase_uri=postgresql://database\n", encoding="utf-8")
    monkeypatch.setenv("BOTJAGWAR_CONFIG", str(config))
    snapshot = mocker.patch(
        "scripts.snapshot_page_check_statistics.snapshot_page_check_statistics", return_value=6
    )

    assert main() == 0
    snapshot.assert_called_once_with(
        "postgresql://database", "http://127.0.0.1:8000", ("mg",)
    )

    snapshot.side_effect = RuntimeError("offline")
    assert main() == 1


def test_main_can_validate_storage_without_fetching_statistics(mocker, monkeypatch, tmp_path: Path) -> None:
    """The installer check touches only PostgreSQL and never requires a running translator."""
    config = tmp_path / "config.ini"
    config.write_text("[global]\ndatabase_uri=postgresql://database\n", encoding="utf-8")
    monkeypatch.setenv("BOTJAGWAR_CONFIG", str(config))
    validate = mocker.patch("scripts.snapshot_page_check_statistics.validate_snapshot_storage")
    snapshot = mocker.patch("scripts.snapshot_page_check_statistics.snapshot_page_check_statistics")

    assert main(check_storage=True) == 0
    validate.assert_called_once_with("postgresql://database")
    snapshot.assert_not_called()
