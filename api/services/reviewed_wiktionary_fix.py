"""Approval integrity helpers for explicitly reviewed Wiktionary edits."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict


REVIEWED_FIX_SCHEMA_VERSION = 2
REVIEWED_FIX_VALIDITY_SECONDS = 3_600


class ReviewedWiktionaryFixError(ValueError):
    """Raised when a reviewed-edit integrity contract is malformed."""


def approval_digest(contract: Dict[str, Any]) -> str:
    """Return the canonical SHA-256 digest for an approval contract."""
    try:
        encoded = json.dumps(
            contract,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ReviewedWiktionaryFixError(
            "The reviewed-edit approval contract is not serializable."
        ) from exc
    return hashlib.sha256(encoded).hexdigest()


def validate_review_environment_id(environment_id: str) -> str:
    """Return an explicit bounded deployment identity for reviewed edits."""
    if (
        not isinstance(environment_id, str)
        or not environment_id.strip()
        or environment_id.strip().lower() == "default"
        or len(environment_id.strip()) > 128
        or any(ord(character) < 32 for character in environment_id)
    ):
        raise ReviewedWiktionaryFixError(
            "A non-default reviewed-publication environment ID is required."
        )
    return environment_id.strip()


def review_environment_fingerprint(
    *,
    configuration_mode: str,
    environment_id: str,
    entry_translator_url: str,
    rabbitmq_host: str,
    rabbitmq_virtual_host: str,
    review_queue_name: str,
    publication_queue_name: str,
) -> str:
    """Hash the non-secret runtime identity that constrains one approval."""
    if configuration_mode not in {"test", "production"}:
        raise ReviewedWiktionaryFixError(
            "Reviewed-publication configuration mode is invalid."
        )
    environment_id = validate_review_environment_id(environment_id)
    if not all(
        isinstance(value, str) and value.strip()
        for value in (
            entry_translator_url,
            rabbitmq_host,
            rabbitmq_virtual_host,
            review_queue_name,
            publication_queue_name,
        )
    ):
        raise ReviewedWiktionaryFixError(
            "Reviewed-publication runtime identity is incomplete."
        )
    identity = {
        "schema_version": 1,
        "configuration_mode": configuration_mode,
        "environment_id": environment_id,
        "entry_translator_url": entry_translator_url.rstrip("/"),
        "rabbitmq_host": rabbitmq_host.strip(),
        "rabbitmq_virtual_host": rabbitmq_virtual_host.strip(),
        "review_queue": review_queue_name,
        "publication_queue": publication_queue_name,
        "target_language": "mg",
        "target_site": "wiktionary",
    }
    encoded = json.dumps(
        identity,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
