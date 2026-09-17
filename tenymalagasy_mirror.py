#!/usr/bin/env python3
"""Mirror tenymalagasy.org responses through a persistent SQLite cache."""

from __future__ import annotations

import argparse
import asyncio
import configparser
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests
from aiohttp import web

from api.config import BotjagwarConfig

LOGGER = logging.getLogger(__name__)
DEFAULT_UPSTREAM_URL = "https://tenymalagasy.org"
DEFAULT_DATABASE_PATH = Path(__file__).resolve().parent / "user_data" / "tenymalagasy_mirror.sqlite3"
USER_AGENT = "Botjagwar tenymalagasy mirror"


@dataclass(frozen=True)
class CachedResponse:
    """Represent one cached upstream HTTP response."""

    status: int
    content_type: str
    body: bytes


class TenymalagasyMirrorStore:
    """Persist tenymalagasy.org responses in SQLite."""

    def __init__(self, path: Path) -> None:
        """Create the response cache if it does not already exist."""
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS responses (
                    cache_key TEXT PRIMARY KEY,
                    status_code INTEGER NOT NULL,
                    content_type TEXT NOT NULL,
                    body BLOB NOT NULL,
                    fetched_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
                )
            """)

    def _connect(self) -> sqlite3.Connection:
        """Open a short-lived connection safe for worker-thread use."""
        return sqlite3.connect(self.path, timeout=5)

    def get(self, cache_key: str) -> Optional[CachedResponse]:
        """Return a cached response, if one exists."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT status_code, content_type, body FROM responses WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()
        if row is None:
            return None
        return CachedResponse(status=int(row[0]), content_type=str(row[1]), body=bytes(row[2]))

    def put(self, cache_key: str, response: CachedResponse) -> None:
        """Store an upstream response unless another worker stored it first."""
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO responses (cache_key, status_code, content_type, body)
                VALUES (?, ?, ?, ?)
                """,
                (cache_key, response.status, response.content_type, response.body),
            )


class TenymalagasyMirror:
    """Fetch uncached requests from tenymalagasy.org."""

    def __init__(
        self,
        store: TenymalagasyMirrorStore,
        upstream_url: str = DEFAULT_UPSTREAM_URL,
        session: Optional[requests.Session] = None,
    ) -> None:
        """Initialize the mirror with injectable storage and HTTP dependencies."""
        self._store = store
        self._upstream_url = upstream_url.rstrip("/")
        self._session = session if session is not None else requests.Session()

    def get(self, cache_key: str) -> CachedResponse:
        """Return a cached response or fetch and persist it from upstream."""
        cached = self._store.get(cache_key)
        if cached is not None:
            return cached

        response = self._session.get(
            f"{self._upstream_url}{cache_key}",
            headers={"User-Agent": USER_AGENT},
            verify=False,
            timeout=30,
        )
        mirrored = CachedResponse(
            status=response.status_code,
            content_type=response.headers.get("Content-Type", "application/octet-stream"),
            body=response.content,
        )
        if response.status_code < 500:
            self._store.put(cache_key, mirrored)
        return mirrored


MIRROR_KEY: web.AppKey[TenymalagasyMirror] = web.AppKey("mirror", TenymalagasyMirror)


def create_app(mirror: TenymalagasyMirror) -> web.Application:
    """Create the tenymalagasy HTTP mirror application."""
    app = web.Application()
    app[MIRROR_KEY] = mirror

    async def health(_request: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    async def proxy(request: web.Request) -> web.Response:
        cache_key = request.path_qs
        try:
            response = await asyncio.to_thread(request.app[MIRROR_KEY].get, cache_key)
        except requests.RequestException as exc:
            LOGGER.warning("tenymalagasy.org request failed for %s: %s", cache_key, exc)
            raise web.HTTPBadGateway(text="tenymalagasy.org is unavailable.") from exc
        return web.Response(
            body=response.body,
            status=response.status,
            headers={"Content-Type": response.content_type},
        )

    app.router.add_get("/health", health)
    app.router.add_get("/{path:.*}", proxy)
    return app


def _config_value(key: str, default: str) -> str:
    """Read one optional mirror setting from Botjagwar configuration."""
    try:
        return BotjagwarConfig().get(key, section="tenymalagasy")
    except (KeyError, configparser.Error) as exc:
        LOGGER.debug("Using default tenymalagasy setting for %s: %s", key, exc)
        return default


def parse_args() -> argparse.Namespace:
    """Parse service command-line arguments using configured defaults."""
    parser = argparse.ArgumentParser(description="SQLite-backed tenymalagasy.org HTTP mirror")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8004)
    parser.add_argument(
        "--database",
        type=Path,
        default=Path(_config_value("database_path", str(DEFAULT_DATABASE_PATH))),
    )
    parser.add_argument("--upstream", default=_config_value("upstream_url", DEFAULT_UPSTREAM_URL))
    return parser.parse_args()


def main() -> None:
    """Run the mirror on a loopback address."""
    args = parse_args()
    logging.basicConfig(level=logging.INFO)
    mirror = TenymalagasyMirror(TenymalagasyMirrorStore(args.database), args.upstream)
    web.run_app(create_app(mirror), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
