"""Security tests for database connection diagnostics."""

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

from sqlalchemy.engine import make_url

from api import databasemanager


def test_database_log_masks_connection_password(monkeypatch, caplog) -> None:
    """Database startup diagnostics must never disclose URI credentials."""
    password = "never-log-this-password"
    engine = MagicMock()
    engine.url = make_url(f"postgresql://bot:{password}@database.example/botjagwar")
    monkeypatch.setattr(databasemanager, "create_engine", lambda *_args, **_kwargs: engine)
    base = SimpleNamespace(metadata=MagicMock())
    manager = databasemanager.DatabaseManager.__new__(databasemanager.DatabaseManager)
    manager.db_header = str(engine.url)

    with caplog.at_level(logging.INFO):
        databasemanager.DatabaseManager.__init__(manager, base)

    assert password not in caplog.text
    assert "database.example/botjagwar" in caplog.text
