#!/usr/bin/env python3
"""Refresh the Atlas dashboard statistics materialized view."""

import logging
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2 import sql

try:
    from scripts.refresh_materialized_views import configure_logging, load_database_uri
except ModuleNotFoundError:  # Direct execution adds scripts/, not the repository root, to sys.path.
    from refresh_materialized_views import configure_logging, load_database_uri

LOGGER = logging.getLogger(__name__)
LOCK_NAME = "botjagwar_refresh_materialized_views"
MATERIALIZED_VIEW_SCHEMA = "public"
MATERIALIZED_VIEW_NAME = "atlas_dashboard_statistics_mv"


def refresh_atlas_dashboard_statistics_mv(database_uri: str) -> int:
    """Concurrently refresh the dashboard statistics materialized view."""
    connection = psycopg2.connect(database_uri)
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_lock(hashtext(%s))", (LOCK_NAME,))
            if not cursor.fetchone()[0]:
                LOGGER.info("Another materialized-view refresh is already running; exiting.")
                return 0

            cursor.execute(
                "SELECT to_regclass(%s) IS NOT NULL",
                (f"{MATERIALIZED_VIEW_SCHEMA}.{MATERIALIZED_VIEW_NAME}",),
            )
            if not cursor.fetchone()[0]:
                raise RuntimeError(
                    f"Materialized view {MATERIALIZED_VIEW_SCHEMA}.{MATERIALIZED_VIEW_NAME} is not installed"
                )

            LOGGER.info("Refreshing %s.%s", MATERIALIZED_VIEW_SCHEMA, MATERIALIZED_VIEW_NAME)
            cursor.execute(
                sql.SQL("REFRESH MATERIALIZED VIEW CONCURRENTLY {}.{}").format(
                    sql.Identifier(MATERIALIZED_VIEW_SCHEMA),
                    sql.Identifier(MATERIALIZED_VIEW_NAME),
                )
            )
            cursor.execute("SELECT to_regclass('public.materialized_view_refresh_status') IS NOT NULL")
            if cursor.fetchone()[0]:
                cursor.execute(
                    """
                    INSERT INTO public.materialized_view_refresh_status
                        (schema_name, view_name, refreshed_at)
                    VALUES (%s, %s, now())
                    ON CONFLICT (schema_name, view_name)
                    DO UPDATE SET refreshed_at = EXCLUDED.refreshed_at
                    """,
                    (MATERIALIZED_VIEW_SCHEMA, MATERIALIZED_VIEW_NAME),
                )
            LOGGER.info("Successfully refreshed %s.%s", MATERIALIZED_VIEW_SCHEMA, MATERIALIZED_VIEW_NAME)
            return 1
    finally:
        connection.close()


def main() -> int:
    """Run the configured dashboard materialized-view refresh job."""
    configure_logging()
    config_path = Path(os.environ.get("BOTJAGWAR_CONFIG", "/etc/botjagwar/config.ini"))
    try:
        return_code = refresh_atlas_dashboard_statistics_mv(load_database_uri(config_path))
    except (FileNotFoundError, ValueError, RuntimeError, psycopg2.Error):
        LOGGER.exception("Dashboard materialized-view refresh did not complete successfully.")
        return 1
    return 0 if return_code >= 0 else 1


if __name__ == "__main__":
    sys.exit(main())
