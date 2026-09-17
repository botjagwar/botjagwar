"""Offline tests for the SQLite-backed tenymalagasy HTTP mirror."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import requests
from aiohttp.test_utils import TestClient, TestServer

from tenymalagasy_mirror import (
    CachedResponse,
    TenymalagasyMirror,
    TenymalagasyMirrorStore,
    create_app,
)


class FakeSession:
    """Return one fixed upstream response and record requests."""

    def __init__(self, status: int = 200) -> None:
        self.status = status
        self.calls: list[str] = []

    def get(self, url: str, **_kwargs: Any) -> Any:
        """Return a response containing the requested URL."""
        self.calls.append(url)
        return SimpleNamespace(
            status_code=self.status,
            headers={"Content-Type": "text/html; charset=utf-8"},
            content=f"upstream: {url}".encode(),
        )


def test_store_round_trips_binary_response(tmp_path: Path) -> None:
    store = TenymalagasyMirrorStore(tmp_path / "mirror.sqlite3")
    response = CachedResponse(200, "text/html", b"cached body")

    store.put("/bins/teny2/alika", response)

    assert store.get("/bins/teny2/alika") == response


def test_mirror_reuses_sqlite_response(tmp_path: Path) -> None:
    session = FakeSession()
    mirror = TenymalagasyMirror(
        TenymalagasyMirrorStore(tmp_path / "mirror.sqlite3"),
        upstream_url="https://upstream.example",
        session=session,
    )

    first = mirror.get("/bins/teny2/alika")
    second = mirror.get("/bins/teny2/alika")

    assert first == second
    assert first.status == 200
    assert session.calls == ["https://upstream.example/bins/teny2/alika"]


def test_mirror_caches_not_found_responses(tmp_path: Path) -> None:
    session = FakeSession(status=404)
    mirror = TenymalagasyMirror(
        TenymalagasyMirrorStore(tmp_path / "mirror.sqlite3"), session=session
    )

    assert mirror.get("/bins/teny2/tsisy").status == 404
    assert mirror.get("/bins/teny2/tsisy").status == 404
    assert len(session.calls) == 1


def test_mirror_does_not_cache_server_errors(tmp_path: Path) -> None:
    session = FakeSession(status=503)
    mirror = TenymalagasyMirror(
        TenymalagasyMirrorStore(tmp_path / "mirror.sqlite3"), session=session
    )

    mirror.get("/bins/teny2/alika")
    mirror.get("/bins/teny2/alika")

    assert len(session.calls) == 2


def test_http_service_preserves_path_status_and_content_type(tmp_path: Path) -> None:
    async def run() -> None:
        mirror = TenymalagasyMirror(
            TenymalagasyMirrorStore(tmp_path / "mirror.sqlite3"),
            upstream_url="https://upstream.example",
            session=FakeSession(status=404),
        )
        client = TestClient(TestServer(create_app(mirror)))
        await client.start_server()
        try:
            response = await client.get("/bins/teny2/tsisy?language=mg")
            assert response.status == 404
            assert response.content_type == "text/html"
            assert "upstream.example/bins/teny2/tsisy?language=mg" in await response.text()
        finally:
            await client.close()

    asyncio.run(run())


def test_http_service_returns_bad_gateway_for_upstream_failure(tmp_path: Path) -> None:
    class FailingSession:
        def get(self, _url: str, **_kwargs: Any) -> Any:
            raise requests.ConnectionError("offline")

    async def run() -> None:
        mirror = TenymalagasyMirror(
            TenymalagasyMirrorStore(tmp_path / "mirror.sqlite3"),
            session=FailingSession(),
        )
        client = TestClient(TestServer(create_app(mirror)))
        await client.start_server()
        try:
            response = await client.get("/bins/teny2/alika")
            assert response.status == 502
        finally:
            await client.close()

    asyncio.run(run())
