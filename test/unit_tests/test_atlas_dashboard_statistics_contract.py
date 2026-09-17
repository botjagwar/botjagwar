"""Contract tests for the Atlas dashboard SQL migration."""

from pathlib import Path


MIGRATION_006 = Path(__file__).parents[2] / "data/migrations/006_add_atlas_dashboard_statistics.sql"
MIGRATION_007 = Path(__file__).parents[2] / "data/migrations/007_track_entry_and_translation_creation.sql"


def test_dashboard_statistics_define_expected_utc_periods() -> None:
    """Dashboard windows distinguish rolling periods from complete calendars."""
    sql = MIGRATION_006.read_text(encoding="utf-8")

    for period in ("last_day", "last_7_days", "last_week", "last_month", "year_to_date", "last_year"):
        assert f"'{period}'" in sql
    assert "AT TIME ZONE 'UTC'" in sql
    assert "words.date_changed >= bounds.period_start" in sql
    assert "words.date_changed < bounds.period_end" in sql


def test_dashboard_statistics_count_words_and_deduplicate_definitions() -> None:
    """Multiple Malagasy definitions do not inflate translated-entry counts."""
    sql = MIGRATION_006.read_text(encoding="utf-8")

    assert "count(words.id) AS entry_count" in sql
    assert "WHERE EXISTS" in sql
    assert "definitions.definition_language = 'mg'" in sql
    assert "words.language <> 'mg'" in sql
    assert "ALTER COLUMN date_changed SET DEFAULT now()" in sql
    assert "WHERE date_changed IS NULL" in sql


def test_entry_creation_timestamp_is_immutable_and_indexed() -> None:
    """Migration 007 separates immutable creation time from modification time."""
    sql = MIGRATION_007.read_text(encoding="utf-8")

    assert "ADD COLUMN IF NOT EXISTS created_at" in sql
    assert "NEW.created_at := statement_timestamp()" in sql
    assert "word.created_at is immutable" in sql
    assert "idx_word_created_at" in sql
    assert "WHERE created_at IS NOT NULL" in sql
    assert "words.created_at >= bounds.period_start" in sql
    assert "words.created_at IS NULL" in sql
    assert "words.date_changed >= bounds.period_start" in sql


def test_translation_activity_uses_append_only_event_time() -> None:
    """Translation rankings derive from trigger-managed association events."""
    sql = MIGRATION_007.read_text(encoding="utf-8")

    assert "events_malagasy_translation_created" in sql
    assert "capture_malagasy_translation_link" in sql
    assert "capture_reclassified_malagasy_definition" in sql
    assert "pg_trigger_depth() > 1" in sql
    assert "events.created_at >= bounds.period_start" in sql
    assert "count(DISTINCT events.word_id) AS translated_entries" in sql
