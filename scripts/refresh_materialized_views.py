#!/usr/bin/env python3
"""Refresh every materialized view in the configured PostgreSQL database."""

import configparser
import logging
import os
import sys
from pathlib import Path
from typing import Iterable

import psycopg2
from psycopg2 import sql

LOGGER = logging.getLogger(__name__)
LOCK_NAME = "botjagwar_refresh_materialized_views"
ViewName = tuple[str, str]


def configure_logging() -> None:
    """Configure timestamped logs suitable for cron output."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def load_database_uri(config_path: Path) -> str:
    """Read the PostgreSQL URI from the Botjagwar configuration file."""
    parser = configparser.ConfigParser(interpolation=None)
    if not parser.read(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    try:
        database_uri = parser.get(
            "global",
            "materialized_view_database_uri",
            fallback=parser.get("global", "database_uri"),
        )
    except (configparser.NoOptionError, configparser.NoSectionError) as exc:
        raise ValueError(f"database_uri is not configured in {config_path}") from exc

    database_uri = database_uri.replace("postgresql+psycopg2://", "postgresql://", 1)
    if not database_uri.startswith(("postgresql://", "postgres://")):
        raise ValueError("Materialized-view refresh requires a PostgreSQL database URI")
    return database_uri


def order_views(
    views: Iterable[ViewName], dependencies: Iterable[tuple[ViewName, ViewName]]
) -> list[ViewName]:
    """Return materialized views in dependency-first order."""
    remaining = set(views)
    prerequisites = {view: set() for view in remaining}
    for source, dependent in dependencies:
        if source in remaining and dependent in remaining:
            prerequisites[dependent].add(source)

    ordered: list[ViewName] = []
    while remaining:
        ready = sorted(view for view in remaining if not prerequisites[view] & remaining)
        if not ready:
            cycle = ", ".join(f"{schema}.{name}" for schema, name in sorted(remaining))
            raise ValueError(f"Materialized-view dependency cycle detected: {cycle}")
        ordered.extend(ready)
        remaining.difference_update(ready)
    return ordered


def discover_views(cursor) -> list[ViewName]:
    """Discover visible materialized views in dependency-first order."""
    cursor.execute(
        """
        SELECT schemaname, matviewname
        FROM pg_catalog.pg_matviews
        WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
        """
    )
    views = list(cursor.fetchall())
    cursor.execute(
        """
        SELECT source_namespace.nspname,
               source.relname,
               dependent_namespace.nspname,
               dependent.relname
        FROM pg_catalog.pg_depend dependency
        JOIN pg_catalog.pg_rewrite rewrite ON rewrite.oid = dependency.objid
        JOIN pg_catalog.pg_class dependent ON dependent.oid = rewrite.ev_class
        JOIN pg_catalog.pg_namespace dependent_namespace
          ON dependent_namespace.oid = dependent.relnamespace
        JOIN pg_catalog.pg_class source ON source.oid = dependency.refobjid
        JOIN pg_catalog.pg_namespace source_namespace ON source_namespace.oid = source.relnamespace
        WHERE source.relkind = 'm'
          AND dependent.relkind = 'm'
          AND source.oid <> dependent.oid
        """
    )
    dependencies = [
        ((source_schema, source_name), (dependent_schema, dependent_name))
        for source_schema, source_name, dependent_schema, dependent_name in cursor.fetchall()
    ]
    return order_views(views, dependencies)


def refresh_materialized_views(database_uri: str) -> int:
    """Refresh all materialized views and return the number refreshed."""
    connection = psycopg2.connect(database_uri)
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_lock(hashtext(%s))", (LOCK_NAME,))
            if not cursor.fetchone()[0]:
                LOGGER.info("Another materialized-view refresh is already running; exiting.")
                return 0

            views = discover_views(cursor)
            LOGGER.info("Discovered %d materialized views.", len(views))
            cursor.execute(
                "SELECT to_regclass('public.materialized_view_refresh_status') IS NOT NULL"
            )
            tracking_enabled = cursor.fetchone()[0]
            failures: list[str] = []
            for schema, name in views:
                qualified_name = f"{schema}.{name}"
                try:
                    LOGGER.info("Refreshing %s", qualified_name)
                    cursor.execute(
                        sql.SQL("REFRESH MATERIALIZED VIEW {}.{}").format(
                            sql.Identifier(schema),
                            sql.Identifier(name),
                        )
                    )
                    if tracking_enabled:
                        cursor.execute(
                            """
                            INSERT INTO public.materialized_view_refresh_status
                                (schema_name, view_name, refreshed_at)
                            VALUES (%s, %s, now())
                            ON CONFLICT (schema_name, view_name)
                            DO UPDATE SET refreshed_at = EXCLUDED.refreshed_at
                            """,
                            (schema, name),
                        )
                except psycopg2.Error:
                    failures.append(qualified_name)
                    LOGGER.exception("Failed to refresh %s", qualified_name)

            if failures:
                raise RuntimeError(f"Failed materialized views: {', '.join(failures)}")
            LOGGER.info("Successfully refreshed %d materialized views.", len(views))
            return len(views)
    finally:
        connection.close()


def main() -> int:
    """Run the configured materialized-view refresh job."""
    configure_logging()
    config_path = Path(os.environ.get("BOTJAGWAR_CONFIG", "/etc/botjagwar/config.ini"))
    try:
        return_code = refresh_materialized_views(load_database_uri(config_path))
    except (FileNotFoundError, ValueError, RuntimeError, psycopg2.Error):
        LOGGER.exception("Materialized-view refresh did not complete successfully.")
        return 1
    return 0 if return_code >= 0 else 1


if __name__ == "__main__":
    sys.exit(main())
