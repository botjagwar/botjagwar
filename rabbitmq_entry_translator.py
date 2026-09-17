import asyncio
import configparser
import re
import sys
from typing import Any, Callable, Dict

import aiohttp
import mwparserfromhell
from aiohttp import ClientTimeout

from api.config import BotjagwarConfig
from api.rabbitmq import RabbitMqConsumer
from redis_wikicache import NoPage, RedisPage as Page, RedisSite as Site

entry_translator_clients = 32
try:
    frontend_port = int(BotjagwarConfig().get("backend_port", "translator"))
except (configparser.Error, KeyError):
    frontend_port = 8000
DELETE_TEMPLATE = "{{fafao}}"
DELETE_SUMMARY = "Pejy voafafa tao amin'ny Wiktionary loharano"
IRC_FORMATTING_RE = re.compile(r"\x03(?:\d{1,2}(?:,\d{1,2})?)?|[\x02\x0f\x16\x1d\x1f]")
DELETE_LOG_RE = re.compile(
    r"^(?:\[\[)?Special:Log/delete\]\]\s+delete\b.*?\[\[([^\[\]]+?)(?:\]\]|$)"
)
MAX_TRANSLATOR_JOBS = 30
JOB_QUEUE_BACKOFF_SECONDS = 2


def _strip_irc_formatting(value: str) -> str:
    """Remove formatting controls retained in broker event titles."""
    return IRC_FORMATTING_RE.sub("", value)


def _is_delete_log_entry(value: str) -> bool:
    """Return whether a broker title comes from Wikimedia's deletion log."""
    clean_value = _strip_irc_formatting(value)
    return re.match(r"^(?:\[\[)?Special:Log/delete(?:\]\]|$)", clean_value) is not None


def extract_deleted_page_title(value: str) -> str | None:
    """Extract the page targeted by a true delete action from a broker title."""
    match = DELETE_LOG_RE.match(_strip_irc_formatting(value))
    if match is None:
        return None
    title = match.group(1).strip()
    return title or None


def _malagasy_page(page_title: str) -> Page:
    """Build a live Malagasy Wiktionary page without import-time network access."""
    return Page(Site("mg", "wiktionary"), page_title, offline=False)


def _contains_delete_template(content: str) -> bool:
    """Return whether Malagasy wikitext already transcludes the deletion template."""
    wikicode = mwparserfromhell.parse(content)
    return any(
        str(template.name).strip().casefold()
        in {
            "fafao",
            "endrika:fafao",
            "template:fafao",
            "delete",
            "endrika:delete",
            "template:delete",
        }
        for template in wikicode.ifilter_templates(recursive=True)
    )


def mark_page_for_deletion(
    page_title: str,
    page_factory: Callable[[str], Any] = _malagasy_page,
) -> bool:
    """Prepend the Malagasy deletion marker when the live page exists."""
    page = page_factory(page_title)
    if not page.exists():
        print(f"SKIPPING deleted source page missing from mg.wiktionary: {page_title}")
        return False

    try:
        content = page.get(force_refresh=True)
    except NoPage:
        print(f"SKIPPING deleted source page missing from mg.wiktionary: {page_title}")
        return False

    if _contains_delete_template(content):
        print(f"SKIPPING page already marked for deletion: {page_title}")
        return False

    page.put(
        f"{DELETE_TEMPLATE}\n\n{content}",
        DELETE_SUMMARY,
        force=True,
        minor=False,
        nocreate=True,
    )
    print(f"MARKED page for deletion on mg.wiktionary: {page_title}")
    return True


async def read_json_response(resp: aiohttp.ClientResponse) -> Dict[str, Any]:
    """Return response JSON with a fallback payload for non-JSON API responses."""
    try:
        data = await resp.json()
    except (aiohttp.ContentTypeError, ValueError):
        return {
            "status": "error",
            "message": await resp.text(),
            "http_status": resp.status,
        }
    if isinstance(data, dict):
        data.setdefault("http_status", resp.status)
        return data
    return {
        "status": "unknown",
        "message": "Translation API returned a non-object response.",
        "response": data,
        "http_status": resp.status,
    }


def is_failed_api_response(status_code: int, data: Dict[str, Any]) -> bool:
    """Return True when an HTTP or structured translation response failed."""
    return status_code >= 400 or data.get("status") == "error"


class SimpleEntryTranslatorClientFeeder:
    def __init__(
        self,
        host: str = "localhost",
        port: int | None = None,
        page_factory: Callable[[str], Any] = _malagasy_page,
    ) -> None:
        self.host = host
        self.port = int(port) if port is not None else frontend_port
        self.page_factory = page_factory
        self.consumer = RabbitMqConsumer("edit2", callback_function=self.on_page_edit)

    def run(self) -> None:
        self.consumer.run()

    def on_page_edit(self, **arguments: Any) -> None:
        title = arguments.get("title", "")
        if isinstance(title, str) and _is_delete_log_entry(title):
            deleted_page_title = extract_deleted_page_title(title)
            if deleted_page_title is not None:
                mark_page_for_deletion(deleted_page_title, self.page_factory)
            return

        additional_args = {"context": self}
        arguments |= additional_args
        try:
            asyncio.run(self.on_page_edit_async(**arguments))
        except Exception as error:
            print(error)
            return

    @staticmethod
    async def on_page_edit_async(**arguments: Any) -> None:
        context = arguments.get("context")
        async with aiohttp.ClientSession(timeout=ClientTimeout(total=10)) as session:
            while True:
                async with session.get(f"http://{context.host}:{context.port}/jobs") as resp:
                    data = await resp.json()
                    print(data["jobs"], f"jobs in queue for {context.port}")

                if data["jobs"] <= MAX_TRANSLATOR_JOBS:
                    break
                print(
                    f"Job queue is over {MAX_TRANSLATOR_JOBS}; retrying in "
                    f"{JOB_QUEUE_BACKOFF_SECONDS} seconds"
                )
                await asyncio.sleep(JOB_QUEUE_BACKOFF_SECONDS)

            site = arguments.get("site", "en")
            title = arguments.get("title", "")
            print(f">>> {site} :: {title} <<<")
            url = f"http://{context.host}:{context.port}/wiktionary-pages/{site}/jobs"
            print(url)
            for attempt in range(5):
                async with session.post(url, json={"title": title}) as resp:
                    response_data = await read_json_response(resp)
                    print(
                        resp.status,
                        response_data.get("status", response_data.get("message")),
                    )
                    if resp.status == 503 and attempt < 4:
                        print("Translator capacity is full; retrying in 3 seconds")
                        await asyncio.sleep(3)
                        continue
                    if is_failed_api_response(resp.status, response_data):
                        print("Error! ", resp.status, response_data)
                    break


if __name__ == "__main__":
    service_port = 8000 if len(sys.argv) < 2 else int(sys.argv[1])
    bot = SimpleEntryTranslatorClientFeeder(host="localhost", port=service_port)
    bot.run()
