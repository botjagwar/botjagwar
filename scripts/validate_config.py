#!/usr/bin/env python3
"""Validate security-sensitive Botjagwar deployment configuration."""

from __future__ import annotations

import argparse
import configparser
import os
import re
from pathlib import Path

QUEUE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,255}$")


def validate_config(path: Path, *, test_mode: bool = False) -> None:
    """Validate RabbitMQ review settings without exposing credentials."""
    parser = configparser.ConfigParser(interpolation=None)
    if not parser.read(path, encoding="utf-8"):
        raise ValueError("Unable to read protected Botjagwar configuration.")
    gateway_secret = parser.get(
        "rabbitmq", "gateway_hmac_secret", fallback=""
    ).strip()
    if gateway_secret and len(gateway_secret.encode("utf-8")) < 32:
        raise ValueError(
            "rabbitmq.gateway_hmac_secret must contain at least 32 bytes."
        )
    environment_id = parser.get(
        "wiktionary_review", "environment_id", fallback=""
    ).strip()
    if environment_id and (
        environment_id.lower() == "default"
        or len(environment_id) > 128
        or any(ord(character) < 32 for character in environment_id)
    ):
        raise ValueError(
            "wiktionary_review.environment_id must identify this deployment."
        )

    generic_queue = parser.get("rabbitmq", "queue", fallback="botjagwar").strip()
    page_check_queue = parser.get(
        "rabbitmq", "page_check_queue", fallback="translated"
    ).strip()
    review_queue = parser.get(
        "rabbitmq", "page_check_review_queue", fallback="page-check-review"
    ).strip()
    role_queues = {
        generic_queue,
        page_check_queue,
        review_queue,
    }
    if any(not QUEUE_NAME_PATTERN.fullmatch(queue) for queue in role_queues):
        raise ValueError("RabbitMQ queue names are invalid.")
    if review_queue in {page_check_queue, generic_queue}:
        raise ValueError(
            "RabbitMQ review and publication queue roles must be distinct."
        )
    replay_path = Path(
        parser.get(
            "rabbitmq",
            "gateway_replay_ledger",
            fallback="/var/lib/botjagwar/user_data/rabbitmq-gateway-replays.sqlite3",
        )
    ).expanduser()
    if gateway_secret and not test_mode and not replay_path.is_absolute():
        raise ValueError("rabbitmq.gateway_replay_ledger must be absolute.")


def main(argv: list[str] | None = None) -> int:
    """Run deployment configuration validation from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    args = parser.parse_args(argv)
    try:
        validate_config(args.config, test_mode=os.environ.get("TEST") == "1")
    except (configparser.Error, OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
