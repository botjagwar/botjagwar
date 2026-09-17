"""Tests for installing protected database URIs into PostgREST configuration."""

from pathlib import Path

import pytest

from scripts.sync_postgrest_database_uri import sync_postgrest_database_uri


def test_sync_postgrest_database_uri(tmp_path: Path) -> None:
    """Update every PostgREST instance from the protected runtime config."""
    config = tmp_path / "config.ini"
    config.write_text("[global]\ndatabase_uri = postgresql://user:secret@database/botjagwar\n", encoding="utf-8")
    postgrest = tmp_path / "pgrest"
    postgrest.mkdir()
    for index in (1, 2):
        (postgrest / f"pgrest_{index}.ini").write_text(
            'db-uri = "postgresql://example"\nserver-host = "127.0.0.1"\n',
            encoding="utf-8",
        )

    assert sync_postgrest_database_uri(config, postgrest) == 2
    for postgrest_path in postgrest.glob("*.ini"):
        assert 'db-uri = "postgresql://user:secret@database/botjagwar"' in postgrest_path.read_text(
            encoding="utf-8"
        )


def test_sync_postgrest_database_uri_requires_runtime_database_uri(tmp_path: Path) -> None:
    """Fail clearly when the protected runtime configuration is incomplete."""
    config = tmp_path / "config.ini"
    config.write_text("[global]\ndebug = false\n", encoding="utf-8")

    with pytest.raises(ValueError, match="database_uri"):
        sync_postgrest_database_uri(config, tmp_path)
