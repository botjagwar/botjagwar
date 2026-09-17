"""Tests for the Gemma definition reformulation client."""
from __future__ import annotations

from typing import Any

import pytest
import requests

from api.servicemanager.gemma import GemmaDefinitionReformulator


class FakeResponse:
    """Small successful chat-completion response."""

    def __init__(self, content: str = "a simpler definition") -> None:
        self.content = content

    def raise_for_status(self) -> None:
        """Represent an HTTP success."""

    def json(self) -> dict[str, Any]:
        """Return one reformulated definition."""
        return {"choices": [{"message": {"content": self.content}}]}


class FakeSession:
    """Capture the outgoing Gemma request."""

    def __init__(self, content: str = "a simpler definition") -> None:
        self.request: dict[str, Any] = {}
        self.content = content

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        """Capture and answer one request."""
        self.request = {"url": url, **kwargs}
        return FakeResponse(self.content)


def test_reformulator_sends_deterministic_simple_english_prompt() -> None:
    """Gemma receives the definition and returns stripped text."""
    session = FakeSession()
    reformulator = GemmaDefinitionReformulator(
        api_url="http://gemma/chat",
        model="gemma-4",
        session=session,  # type: ignore[arg-type]
    )

    assert reformulator.reformulate("a complicated definition") == "a simpler definition"
    assert session.request["url"] == "http://gemma/chat"
    assert session.request["json"]["model"] == "gemma-4"
    assert session.request["json"]["temperature"] == 0
    assert session.request["json"]["messages"][-1]["content"] == "a complicated definition"


def test_reformulator_maps_http_errors_to_runtime_error() -> None:
    """Transport failures use the pipeline's stable reformulation error."""
    class FailingSession(FakeSession):
        def post(self, url: str, **kwargs: Any) -> FakeResponse:
            raise requests.RequestException("offline")

    reformulator = GemmaDefinitionReformulator(
        api_url="http://gemma/chat",
        session=FailingSession(),  # type: ignore[arg-type]
    )

    with pytest.raises(RuntimeError, match="Gemma definition reformulation failed"):
        reformulator.reformulate("a complicated definition")


def test_complete_json_generates_structured_definitions() -> None:
    """The page checker can request deterministic JSON from the dedicated Gemma client."""
    session = FakeSession(
        '```json\n{"entry": "dog", "part_of_speech": "ana", '
        '"definitions": ["an animal that lives with people"]}\n```'
    )
    client = GemmaDefinitionReformulator(
        api_url="http://gemma/chat",
        model="gemma-4",
        session=session,  # type: ignore[arg-type]
    )

    assert client.complete_json("source entries", system_prompt="generate definitions") == {
        "entry": "dog",
        "part_of_speech": "ana",
        "definitions": ["an animal that lives with people"],
    }
    assert session.request["json"]["response_format"] == {"type": "json_object"}
    assert session.request["json"]["messages"] == [
        {"role": "system", "content": "generate definitions"},
        {"role": "user", "content": "source entries"},
    ]
