"""Contract tests for dictionary request handlers and transaction middleware."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp.web import Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.dictionary.model import Base, Definition
from api.dictionary.request_handlers.configuration import configure_service, do_commit
from api.dictionary.request_handlers.definition import edit_definition, search_definition
from api.dictionary.request_handlers.middlewares import auto_committer
from api.dictionary.request_handlers.routines import save_changes_on_disk


@pytest.fixture
def dictionary_session():
    """Create an isolated in-memory dictionary session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def test_search_definition_accepts_json_object(dictionary_session) -> None:
    """Accept the dictionary returned by aiohttp's request JSON decoder."""
    dictionary_session.add(Definition(definition="sample definition", language="en"))
    dictionary_session.commit()
    request = MagicMock()
    request.app = {"session_instance": dictionary_session}
    request.json = AsyncMock(return_value={"definition": "sample%"})

    response = asyncio.run(search_definition(request))

    assert response.status == 200
    assert "sample definition" in response.text


def test_edit_definition_returns_not_found(dictionary_session) -> None:
    """Return HTTP 404 instead of raising when a definition is absent."""
    request = MagicMock()
    request.app = {"session_instance": dictionary_session, "autocommit": True}
    request.match_info = {"definition_id": "999"}

    response = asyncio.run(edit_definition(request))

    assert response.status == 404


def test_configuration_accepts_only_boolean_autocommit() -> None:
    """Reject truthy strings while accepting JSON boolean values."""
    request = MagicMock()
    request.app = {"autocommit": True}
    request.json = AsyncMock(return_value={"autocommit": False})
    assert asyncio.run(configure_service(request)).status == 200
    assert request.app["autocommit"] is False

    request.json = AsyncMock(return_value={"autocommit": "false"})
    assert asyncio.run(configure_service(request)).status == 400


def test_failed_commit_returns_server_error() -> None:
    """Do not report success when committing the transaction fails."""
    request = MagicMock()
    request.app = {"session_instance": MagicMock()}
    request.app["session_instance"].commit.side_effect = RuntimeError("database unavailable")

    response = asyncio.run(do_commit(request))

    assert response.status == 500
    request.app["session_instance"].rollback.assert_called_once()


def test_save_changes_propagates_commit_failure() -> None:
    """Prevent handlers from returning success after a failed commit."""
    session = MagicMock()
    session.commit.side_effect = RuntimeError("database unavailable")

    with pytest.raises(RuntimeError, match="database unavailable"):
        asyncio.run(save_changes_on_disk({"autocommit": True}, session))

    session.rollback.assert_called_once()


def test_auto_committer_counts_deletes_and_commits_on_threshold() -> None:
    """Include deletes and commit on the configured mutation count."""
    request = MagicMock()
    request.method = "DELETE"
    request.app = {
        "autocommit": True,
        "commit_count": 0,
        "commit_every": 2,
        "session_instance": MagicMock(),
    }
    handler = AsyncMock(return_value=Response(status=204))

    asyncio.run(auto_committer(request, handler))
    request.app["session_instance"].commit.assert_not_called()
    asyncio.run(auto_committer(request, handler))

    request.app["session_instance"].commit.assert_called_once()
    assert request.app["commit_count"] == 0
