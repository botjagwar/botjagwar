from datetime import datetime
from zoneinfo import ZoneInfo  # available in Python 3.9+

import configparser
import hashlib
import json
import math
import os
import re
import sys
import time
from typing import Any


import pika
from pywikibot import config as pywikibot_config

from api.config import BotjagwarConfig
from api.wikimedia_rate_limiter import WikimediaRateLimitError
from redis_wikicache import NoPage, RedisPage as Page, RedisSite as Site

# Reduce wait time between edits
pywikibot_config.put_throttle = .864  # wait only 1 second between edits

TEST_MODE = os.environ.get("TEST") == "1"
settings = BotjagwarConfig()

# RabbitMQ connection parameters
RABBITMQ_HOST = settings.get("host", "rabbitmq")
RABBITMQ_QUEUE = settings.get("queue", "rabbitmq")
RABBITMQ_USERNAME = settings.get("username", "rabbitmq")
RABBITMQ_PASSWORD = settings.get("password", "rabbitmq")
RABBITMQ_VIRTUAL_HOST = settings.get("virtual_host", "rabbitmq")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
QUEUE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,255}$")
MAX_QUEUED_WIKITEXT_MESSAGE_BYTES = 16 * 1024 * 1024


def _configure_standard_streams() -> None:
    """Keep Unicode page titles and errors writable to worker logs."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="backslashreplace")


def _optional_config(key: str, section: str, default: str) -> str:
    """Return one optional worker setting without hiding malformed values."""
    try:
        value = settings.get(key, section)
    except (configparser.Error, KeyError, ValueError):
        return default
    return value.strip() or default


CONSUMER_QUEUE = os.environ.get("BOTJAGWAR_WIKTIONARY_QUEUE", RABBITMQ_QUEUE)
PAGE_CHECK_REVIEW_QUEUE = os.environ.get(
    "BOTJAGWAR_PAGE_CHECK_REVIEW_QUEUE"
) or _optional_config("page_check_review_queue", "rabbitmq", "page-check-review")
def _validate_consumer_configuration() -> None:
    """Reject review evidence queues before executable consumption."""
    if not QUEUE_NAME_PATTERN.fullmatch(CONSUMER_QUEUE):
        raise ValueError("Wiktionary consumer queue configuration is invalid.")
    if CONSUMER_QUEUE == PAGE_CHECK_REVIEW_QUEUE:
        raise ValueError("A generic Wiktionary consumer cannot use a protected queue.")


def get_current_hour():
    now = datetime.now(ZoneInfo("Indian/Antananarivo"))
    return now.hour + now.minute / 60 + now.second / 3600


def get_sleep_time():
    x = get_current_hour()
    def f(h):
        return .5 * (20 + 10 *( (math.sin(1*( x * math.pi) / 12 + (5 * math.pi / 2))) +
                            (1/3)*math.sin(3*((x * math.pi) / 12 + (5 * math.pi / 2))) +
                            (1/5)*math.sin(5*((x * math.pi) / 12 + (5 * math.pi / 2))) +
                            (1/7)*math.sin(7*((x * math.pi) / 12 + (5 * math.pi / 2)))
                      ))
    r = f(x)
    print("Sleep time:", round(r, 2), "seconds")
    return r


def save_to_wiki(
    pagename: str,
    page_content: str,
    summary: str,
    action: str,
    expected_content_sha256: str | None = None,
    minor: bool = False,
) -> bool:
    page = Page(Site("mg", "wiktionary"), pagename, offline=TEST_MODE)
    if not summary.strip():
        if page.exists():
            summary = "fanitsiana"
        else:
            summary = f"Pejy noforonina amin'ny « {page_content} »"

    if action == "edit":
        if expected_content_sha256 is not None:
            try:
                current_content = page.get(force_refresh=True)
            except NoPage:
                print(f"SKIPPING stale queued edit for missing page: {pagename}")
                return False
            current_content_sha256 = hashlib.sha256(
                current_content.encode("utf-8")
            ).hexdigest()
            if current_content_sha256 != expected_content_sha256:
                print(f"SKIPPING stale queued edit for page: {pagename}")
                return False
        #print(f"SAVING   page: {pagename}, Summary - {summary}")
        write_options: dict[str, Any] = {"force": True, "minor": minor}
        if expected_content_sha256 is not None:
            write_options.update(nocreate=True, recreate=False)

        page.put(page_content, summary, **write_options)
    elif action == "delete":
        print(f"DELETING page: {pagename}, Summary - {summary}")
        page.delete("Hadisoana teo amim-pamoronana ilay pejy")
    else:
        raise ValueError("Unknown queued Wiktionary action.")
    return True


def _valid_title(value: Any) -> bool:
    """Return whether a queued title is non-empty and display-safe."""
    return (
        isinstance(value, str)
        and bool(value)
        and value == value.strip()
        and len(value) <= 512
        and not any(ord(character) < 32 for character in value)
    )


def callback(ch, method, properties, body):
    pagename = "<unknown>"
    try:
        if not isinstance(body, bytes) or len(body) > MAX_QUEUED_WIKITEXT_MESSAGE_BYTES:
            raise ValueError("Queued Wiktionary message is too large.")
        data = json.loads(body.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Queued Wiktionary message must be an object.")
        pagename = data["page"]
        content = data["content"]
        summary = data["summary"]
        minor = data["minor"]
        action = data.get("action", "edit")
        expected_content_sha256 = data.get("expected_content_sha256")
        if (
            data.get("language") != "mg"
            or data.get("site") != "wiktionary"
            or not _valid_title(pagename)
            or not isinstance(content, str)
            or not isinstance(summary, str)
            or not isinstance(minor, bool)
            or action not in {"edit", "delete"}
            or "expected_content_sha256" in data
            and (
                not isinstance(expected_content_sha256, str)
                or not SHA256_PATTERN.fullmatch(expected_content_sha256)
            )
        ):
            raise ValueError("Queued Wiktionary message is invalid.")
    except (
        KeyError,
        RecursionError,
        TypeError,
        ValueError,
        UnicodeDecodeError,
    ) as error:
        print(f"Discarding invalid queued Wiktionary message: {error}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        time.sleep(get_sleep_time())
        return

    try:
        save_to_wiki(
            pagename,
            content,
            summary,
            action,
            expected_content_sha256=expected_content_sha256,
            minor=minor,
        )
    except Exception as error:
        # Preserve limiter failures; retry other failures once.
        requeue = isinstance(error, WikimediaRateLimitError) or not bool(
            getattr(method, "redelivered", False)
        )
        disposition = "retrying" if requeue else "discarding"
        print(f"Error saving page {pagename}; {disposition} queued edit: {error}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=requeue)
    else:
        ch.basic_ack(delivery_tag=method.delivery_tag)
    time.sleep(get_sleep_time())


def consume_wiki_messages():
    _validate_consumer_configuration()
    # Create credentials for RabbitMQ authentication
    credentials = pika.PlainCredentials(RABBITMQ_USERNAME, RABBITMQ_PASSWORD)

    # Establish a connection to RabbitMQ with authentication and vhost
    parameters = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        virtual_host=RABBITMQ_VIRTUAL_HOST,
        credentials=credentials,
        heartbeat=60,
        blocked_connection_timeout=20,
    )
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()

    # Declare the queue from which messages will be consumed
    # channel.queue_delete(queue=RABBITMQ_QUEUE)
    print(f"Resetting current queue in use: {CONSUMER_QUEUE}")
    channel.queue_declare(queue=CONSUMER_QUEUE, durable=True)
    # Set the maximum number of unacknowledged messages
    channel.basic_qos(prefetch_count=1)

    # Set the callback function to consume messages
    print(f"Consuming {CONSUMER_QUEUE}")
    channel.basic_consume(queue=CONSUMER_QUEUE, on_message_callback=callback)

    # Start consuming messages
    channel.start_consuming()


def main() -> None:
    """Run the Wiktionary queue worker."""
    _configure_standard_streams()
    print(f"Connecting to RabbitMQ at {RABBITMQ_HOST} with queue {CONSUMER_QUEUE}")
    print(f"Using RabbitMQ user {RABBITMQ_USERNAME} on vhost {RABBITMQ_VIRTUAL_HOST}")
    consume_wiki_messages()


if __name__ == "__main__":
    main()
