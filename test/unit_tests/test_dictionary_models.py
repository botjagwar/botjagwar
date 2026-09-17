from unittest.mock import MagicMock, patch

from sqlalchemy.sql.elements import TextClause

from api.dictionary.model import Definition
from api.dictionary.model import Word


def test_definition_does_not_map_optional_vector_column() -> None:
    """Dictionary queries must work without the optional pgvector migration."""
    assert "definition_vector" not in Definition.__table__.columns


def test_additional_data_uses_parameterized_sql() -> None:
    """Additional word data remains compatible with SQLAlchemy 2."""
    manager = MagicMock()
    manager.session.execute.return_value.fetchall.return_value = [
        (42, "synonym", "home"),
    ]
    word = Word("house", "en", "ana", [])
    word.id = 42

    with patch("api.databasemanager.DictionaryDatabaseManager", return_value=manager):
        assert word.additional_data == {"synonym": ["home"]}

    query, parameters = manager.session.execute.call_args.args
    assert isinstance(query, TextClause)
    assert parameters == {"word_id": 42}
