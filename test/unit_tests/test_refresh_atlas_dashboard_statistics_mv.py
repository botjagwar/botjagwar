import pytest

from scripts.refresh_atlas_dashboard_statistics_mv import refresh_atlas_dashboard_statistics_mv


def test_refresh_records_success_when_tracking_table_exists(mocker) -> None:
    """Successful concurrent refreshes update the optional status table."""
    connection = mocker.patch("scripts.refresh_atlas_dashboard_statistics_mv.psycopg2.connect").return_value
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = [(True,), (True,), (True,)]

    assert refresh_atlas_dashboard_statistics_mv("postgresql://database") == 1

    statements = [call.args[0] for call in cursor.execute.call_args_list]
    assert any("REFRESH MATERIALIZED VIEW CONCURRENTLY" in str(statement) for statement in statements)
    assert any(
        "materialized_view_refresh_status" in str(statement) and "INSERT INTO" in str(statement)
        for statement in statements
    )


def test_refresh_skips_tracking_when_status_table_missing(mocker) -> None:
    """The refresh still succeeds when migration 004 was never applied."""
    connection = mocker.patch("scripts.refresh_atlas_dashboard_statistics_mv.psycopg2.connect").return_value
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = [(True,), (True,), (False,)]

    assert refresh_atlas_dashboard_statistics_mv("postgresql://database") == 1

    statements = [call.args[0] for call in cursor.execute.call_args_list]
    assert not any("INSERT INTO public.materialized_view_refresh_status" in str(statement) for statement in statements)


def test_refresh_exits_when_another_refresh_is_running(mocker) -> None:
    """A held advisory lock skips the refresh without failing the job."""
    connection = mocker.patch("scripts.refresh_atlas_dashboard_statistics_mv.psycopg2.connect").return_value
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = [(False,)]

    assert refresh_atlas_dashboard_statistics_mv("postgresql://database") == 0

    statements = [call.args[0] for call in cursor.execute.call_args_list]
    assert not any("REFRESH MATERIALIZED VIEW" in str(statement) for statement in statements)


def test_refresh_raises_when_materialized_view_missing(mocker) -> None:
    """A database without migration 008 fails loudly instead of silently succeeding."""
    connection = mocker.patch("scripts.refresh_atlas_dashboard_statistics_mv.psycopg2.connect").return_value
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = [(True,), (False,)]

    with pytest.raises(RuntimeError, match="is not installed"):
        refresh_atlas_dashboard_statistics_mv("postgresql://database")
