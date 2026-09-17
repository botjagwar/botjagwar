import bz2
import configparser
import os
import sys
from typing import Any, Callable

import pywikibot
import redis
import requests

from api.config import BotjagwarConfig
from api.decorator import separate_process, retry_on_fail, run_once
from api.wikimedia_rate_limiter import WikimediaRateLimiter
from import_wiktionary import EnWiktionaryDumpImporter

config = BotjagwarConfig()

DEFAULT_USER_AGENT_DESCRIPTION = (
    "mgwiktionary-automation/1.0 "
    "(https://mg.wiktionary.org/wiki/User:Bot-Jagwar)"
)


def _wikimedia_setting(key: str, default: str) -> str:
    """Return one optional Wikimedia setting with a deploy-safe default."""
    try:
        return config.get(key, "wikimedia")
    except (configparser.Error, KeyError):
        return default


class RedisWikipageError(Exception):
    pass


class NoPage(Exception):
    pass


class UnsafeWikiWriteError(RuntimeError):
    """Reject a live write outside Botjagwar's Malagasy Wiktionary target."""


class RedisSite(object):
    def __init__(
        self,
        language: str,
        wiki: str,
        host: str = "default",
        port: int = 6379,
        password: str = "default",
        offline: bool = False,
        download_dump_if_not_exists: bool = True,
        *,
        redis_client: Any | None = None,
        rate_limiter: WikimediaRateLimiter | None = None,
    ) -> None:
        self.offline = offline
        self.language = language
        self.wiki = wiki
        self.host = config.get("host", "redis") if host == "default" else host
        if password == "default":
            self.password = config.get("password", "redis") or None
        else:
            self.password = None

        self.port = port
        self.download_dump_if_not_exists = download_dump_if_not_exists
        self._redis_client = redis_client
        self._rate_limiter = rate_limiter
        self._wikimedia_site = None

    def all_pages(self):
        for key in self.instance.scan_iter(
            match=f"{self.wiki}.{self.language}/*", count=1000
        ):
            page_name = str(key, encoding="utf8").replace(
                f"{self.wiki}.{self.language}/", ""
            )
            yield RedisPage(RedisSite(self.language, "wiktionary"), page_name)

    @property
    def lang(self):
        return self.language

    @property
    @run_once
    def instance(self):
        if self._redis_client is not None:
            return self._redis_client
        return redis.Redis(
            self.host, self.port, password=self.password, socket_timeout=3
        )

    @property
    @run_once
    def rate_limiter(self) -> WikimediaRateLimiter:
        """Return the limiter sharing this site's Redis connection."""
        if self._rate_limiter is not None:
            return self._rate_limiter
        return WikimediaRateLimiter.from_config(self.instance, config=config)

    @property
    def wikimedia_site(self) -> Any:
        """Create the configured Pywikibot site lazily.

        The site is cached per RedisSite instance, not globally, so that
        different language sites never share a cached Pywikibot site.
        """
        if self._wikimedia_site is None:
            pywikibot.config.max_retries = int(
                _wikimedia_setting("max_retries", "2")
            )
            pywikibot.config.retry_wait = float(
                _wikimedia_setting("retry_wait_seconds", "1")
            )
            pywikibot.config.retry_max = float(
                _wikimedia_setting("retry_max_seconds", "5")
            )
            pywikibot.config.maxlag = int(_wikimedia_setting("maxlag_seconds", "5"))
            pywikibot.config.socket_timeout = (
                float(_wikimedia_setting("socket_connect_timeout_seconds", "5")),
                float(_wikimedia_setting("socket_read_timeout_seconds", "30")),
            )
            description = _wikimedia_setting(
                "user_agent_description",
                DEFAULT_USER_AGENT_DESCRIPTION,
            ).strip()
            pywikibot.config.user_agent_description = (
                description or DEFAULT_USER_AGENT_DESCRIPTION
            )
            self._wikimedia_site = pywikibot.Site(self.language, self.wiki)
        return self._wikimedia_site

    def random_page(self):
        rkey = self.instance.randomkey()
        while not rkey.startswith(bytes(f"{self.wiki}.{self.language}/", "utf8")):
            rkey = self.instance.randomkey()

        page_name = str(rkey, encoding="utf8").replace(
            f"{self.wiki}.{self.language}/", ""
        )
        return RedisPage(self, page_name)

    def download_dump(self):
        return

    def download_dump_(self):
        url = (
            f"https://dumps.wikimedia.org/{self.language}wiktionary/latest"
            f"/{self.language}wiktionary-latest-pages-articles.xml.bz2"
        )
        dump_dir = "user_data/dumps"
        dump_path = f"{dump_dir}/{self.language}wikt.xml"

        if not os.path.isdir(dump_dir):
            os.mkdir(dump_dir)
        if not os.path.isfile(f"{dump_path}.bz2"):
            print(
                "File is absent. Downloading from dumps.wikimedia.org. This may take a while..."
            )
            with requests.get(url, stream=True) as request:
                request.raise_for_status()
                with open(f"{dump_path}.bz2", "wb") as f:
                    for chunk in request.iter_content(chunk_size=8192):
                        f.write(chunk)
            print("Download complete.")

        print("Extracting dump file...")
        with (open(dump_path, "wb") as xml_file, bz2.BZ2File(f"{dump_path}.bz2", "rb") as file):
            for data in iter(lambda: file.read(100 * 1024), b""):
                xml_file.write(data)

    @separate_process
    def load_xml_dump(self, download=False, dump_path="user_data/dumps/enwikt.xml"):
        if self.download_dump_if_not_exists or download:
            self.download_dump()

        importer = EnWiktionaryDumpImporter(dump_path)
        for xml_page in importer.load():
            try:
                title, content = importer.get_page_from_xml(xml_page)
                self.push_page(title, content)
            except redis.ConnectionError as error:
                print(error)
            except Exception as error:
                print("Unknown error ", error)

    def push_page(self, title: str, content: str):
        if title is not None and content is not None:
            try:
                self.instance.set(f"{self.wiki}.{self.language}/{title}", content)
            except redis.RedisError as error:
                print(error)

    def __str__(self):
        return f"{self.wiki}.{self.language}"


class RedisPage(object):
    max_redirection_depth = 10  # number of redirection link following until we consider the page as non-existent
    delegated_write_methods = {"move", "protect", "save", "touch", "undelete"}

    def __init__(
        self,
        site: RedisSite,
        title: str,
        offline: bool | str = "automatic",
    ) -> None:
        if offline == "automatic":
            self.offline = site.offline
        else:
            assert isinstance(offline, bool)
            self.offline = offline

        self.site = site
        self._title = title
        self._live_page = None

    def title(self, *args):
        return self._title

    def __repr__(self):
        return f"Page({self.site}/{self.title()})"

    def isEmpty(self):
        return self.get() == ""

    @retry_on_fail((redis.ConnectionError), retries=5, time_between_retries=0.5)
    def get(self, force_refresh: bool = False) -> str:
        """Return page text, optionally refreshing the Redis cache from the wiki."""
        if self._title is None:
            return ""

        cache_contents = None
        if not force_refresh or self.offline:
            cache_contents = self._get_cache_contents()

        if cache_contents is not None and (not force_refresh or self.offline):
            return self._decode_cache_contents(cache_contents)

        if self.offline:
            raise NoPage(
                f"Page  {self._title} at {self.site} not found in redis. "
                f"Offline mode is ON so there is no on-wiki fetching."
            )
        try:
            content = self._call_live(
                lambda: self._get_live_page().get(force=force_refresh)
            )
        except pywikibot.exceptions.NoPageError as error:
            raise NoPage(
                f"Page {self._title} at {self.site} not found "
                f"neither in-redis nor on-wiki"
            ) from error
        self.site.push_page(self._title, content)
        return content

    def put(
        self,
        content: str,
        summary: str = "",
        *args: Any,
        before_live_call: Callable[[], None] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Publish page text and update Redis only after the wiki write succeeds."""
        self._assert_write_destination()

        def publish() -> Any:
            if before_live_call is not None:
                before_live_call()
            return self._get_live_page().put(content, summary, *args, **kwargs)

        result = self._call_live(
            publish
        )
        self.site.push_page(self._title, content)
        return result

    def delete(self, reason: str, *args: Any, **kwargs: Any) -> Any:
        """Delete the live page and evict its cached content after success."""
        self._assert_write_destination()
        result = self._call_live(
            lambda: self._get_live_page().delete(reason, *args, **kwargs)
        )
        try:
            self.site.instance.delete(
                f"{self.site.wiki}.{self.site.language}/{self._title}"
            )
        except redis.RedisError:
            pass
        return result

    def _get_live_page(self) -> Any:
        """Return one Pywikibot page so a refreshed revision guards its write."""
        if self._live_page is None:
            self._live_page = pywikibot.Page(self.site.wikimedia_site, self._title)
        return self._live_page

    def _assert_write_destination(self) -> None:
        """Permit live mutations only on Malagasy Wiktionary."""
        if self.offline:
            raise UnsafeWikiWriteError("Live Wiktionary writes are disabled offline.")
        if self.site.language != "mg" or self.site.wiki != "wiktionary":
            raise UnsafeWikiWriteError(
                "Botjagwar live writes are restricted to mg.wiktionary; "
                f"got {self.site.wiki}.{self.site.language}."
            )

    def _get_cache_contents(self) -> bytes | str | None:
        try:
            return self.site.instance.get(
                f"{self.site.wiki}.{self.site.language}/{self._title}"
            )
        except redis.RedisError:
            return None

    @staticmethod
    def _decode_cache_contents(cache_contents: bytes | str) -> str:
        if isinstance(cache_contents, bytes):
            return cache_contents.decode("utf8")
        return cache_contents

    def _call_live(self, operation: Callable[[], Any]) -> Any:
        """Run one explicit live boundary after reserving its global start."""
        self.site.rate_limiter.acquire()
        try:
            return operation()
        except Exception as error:
            self.site.rate_limiter.observe_exception(error)
            raise

    def exists(self) -> bool:
        if self._get_cache_contents() is not None:
            return True
        if self.offline:
            return False
        if not self._call_live(lambda: self._get_live_page().exists()):
            return False

        wikipage = self._get_live_page()
        redirection_depth = 0
        while self._call_live(wikipage.isRedirectPage):
            redirection_depth += 1
            if redirection_depth == self.max_redirection_depth:
                return False
            wikipage = self._call_live(wikipage.getRedirectTarget)

        if redirection_depth:
            return bool(self._call_live(wikipage.exists))
        return True

    def namespace(self) -> Any:
        if self.offline:

            class Namespace(object):
                content = self.get()

            return Namespace()
        try:
            return self._call_live(lambda: self._get_live_page().namespace())
        except pywikibot.exceptions.InvalidTitleError:

            class Namespace(object):
                content = self.get()

            return Namespace()

    def isRedirectPage(self) -> bool:
        cache_contents = self._get_cache_contents()
        if cache_contents is not None:
            return "#REDIRECT [[" in self._decode_cache_contents(cache_contents)
        if self.offline:
            return False
        return bool(
            self._call_live(lambda: self._get_live_page().isRedirectPage())
        )

    def getRedirectTarget(self) -> Any:
        """Return the live redirect target after reserving a request start."""
        if self.offline:
            raise NoPage(f"Cannot resolve {self._title} while offline.")
        return self._call_live(lambda: self._get_live_page().getRedirectTarget())

    def __getattr__(self, item: str) -> Any:
        if hasattr(RedisPage, item):
            return getattr(self, item)
        if item in self.delegated_write_methods:
            self._assert_write_destination()
        return getattr(self._get_live_page(), item)


if __name__ == "__main__":
    print(
        """
    Download the en.wiktionary page dumps,
    split it into several chunks (e.g. using split) and run this script.
    All en.wiktionary pages will have their latest version uploaded in your Redis.
    Using RedisSite and RedisPage, you'll have a much faster read and offline access.
    """
    )
    language = sys.argv[1]
    site = RedisSite(language, "wiktionary", download_dump_if_not_exists=True)
    site.load_xml_dump(dump_path=f"user_data/dumps/{language}wikt.xml")
    # site.load_xml_dump('user_data/dumps/enwikt_2.xml')
    # site.load_xml_dump('user_data/dumps/enwikt_3.xml')
    # site.load_xml_dump('user_data/dumps/enwikt_4.xml')
    # site.load_xml_dump('user_data/dumps/enwikt_5.xml')
    # site.load_xml_dump('user_data/dumps/enwikt_6.xml')
    # site.load_xml_dump('user_data/dumps/enwikt_7.xml')
    # site.load_xml_dump('user_data/dumps/enwikt_8.xml')
    # site.load_xml_dump('user_data/dumps/enwikt_9.xml')
    # site.load_xml_dump('user_data/dumps/enwikt_10.xml')
    # site.load_xml_dump('user_data/dumps/enwikt_11.xml')
    # site.load_xml_dump('user_data/dumps/enwikt_13.xml')
    # site.load_xml_dump('user_data/dumps/enwikt_14.xml')
    # site.load_xml_dump('user_data/dumps/enwikt_15.xml')
    # site.load_xml_dump('user_data/dumps/enwikt_16.xml')
    # site.load_xml_dump('user_data/dumps/enwikt_17.xml')
