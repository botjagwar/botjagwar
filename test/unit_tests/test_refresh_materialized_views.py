from pathlib import Path

import pytest

from scripts.refresh_materialized_views import load_database_uri, order_views, refresh_materialized_views


def test_order_views_places_dependencies_first() -> None:
    """A materialized view is refreshed after all views it reads."""
    source = ("public", "source")
    middle = ("public", "middle")
    final = ("public", "final")

    assert order_views([final, source, middle], [(source, middle), (middle, final)]) == [
        source,
        middle,
        final,
    ]


def test_order_views_rejects_cycles() -> None:
    """Dependency cycles fail before any refresh is attempted."""
    first = ("public", "first")
    second = ("public", "second")

    with pytest.raises(ValueError, match="dependency cycle"):
        order_views([first, second], [(first, second), (second, first)])


def test_load_database_uri_supports_sqlalchemy_driver(tmp_path: Path) -> None:
    """The scheduler converts SQLAlchemy's explicit psycopg2 URI."""
    config = tmp_path / "config.ini"
    config.write_text(
        "[global]\ndatabase_uri = postgresql+psycopg2://user:password@db/botjagwar\n",
        encoding="utf-8",
    )

    assert load_database_uri(config) == "postgresql://user:password@db/botjagwar"


def test_load_database_uri_prefers_dedicated_refresh_role(tmp_path: Path) -> None:
    """Maintenance can use a materialized-view owner without elevating the API role."""
    config = tmp_path / "config.ini"
    config.write_text(
        "[global]\n"
        "database_uri = postgresql://application@db/botjagwar\n"
        "materialized_view_database_uri = postgresql://refresh-owner@db/botjagwar\n",
        encoding="utf-8",
    )

    assert load_database_uri(config) == "postgresql://refresh-owner@db/botjagwar"


def test_load_database_uri_rejects_non_postgresql_database(tmp_path: Path) -> None:
    """Materialized views are not available on the SQLite fallback."""
    config = tmp_path / "config.ini"
    config.write_text("[global]\ndatabase_uri = sqlite:///botjagwar.db\n", encoding="utf-8")

    with pytest.raises(ValueError, match="PostgreSQL"):
        load_database_uri(config)


def test_refresh_records_success_when_tracking_table_exists(mocker) -> None:
    """Successful refreshes update the optional materialized-view status table."""
    connection = mocker.patch("scripts.refresh_materialized_views.psycopg2.connect").return_value
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = [(True,), (True,)]
    mocker.patch("scripts.refresh_materialized_views.discover_views", return_value=[("public", "json_dictionary")])

    assert refresh_materialized_views("postgresql://database") == 1

    statements = [call.args[0] for call in cursor.execute.call_args_list]
    assert any("materialized_view_refresh_status" in str(statement) and "INSERT INTO" in str(statement) for statement in statements)
