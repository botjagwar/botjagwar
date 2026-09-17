"""Tests for reviewed-fix approval integrity helpers."""

import pytest

from api.services.reviewed_wiktionary_fix import (
    ReviewedWiktionaryFixError,
    approval_digest,
    review_environment_fingerprint,
    validate_review_environment_id,
)


def test_approval_digest_is_canonical() -> None:
    """Equivalent approval contracts should have the same digest."""
    assert approval_digest({"title": "saka", "content": "new"}) == approval_digest(
        {"content": "new", "title": "saka"}
    )


def test_approval_digest_rejects_non_json_contract() -> None:
    with pytest.raises(ReviewedWiktionaryFixError, match="not serializable"):
        approval_digest({"invalid": object()})


@pytest.mark.parametrize("environment_id", ["", "default", "bad\nvalue"])
def test_environment_id_must_be_explicit(environment_id: str) -> None:
    with pytest.raises(ReviewedWiktionaryFixError, match="environment ID"):
        validate_review_environment_id(environment_id)


def test_environment_fingerprint_binds_direct_amqp_destination() -> None:
    """Changing the broker destination must invalidate stored approvals."""
    options = {
        "configuration_mode": "production",
        "environment_id": "mgwikt-production",
        "entry_translator_url": "http://translator:8000",
        "rabbitmq_host": "rabbitmq",
        "rabbitmq_virtual_host": "botjagwar",
        "review_queue_name": "page-check-review",
        "publication_queue_name": "translated",
    }

    first = review_environment_fingerprint(**options)
    second = review_environment_fingerprint(
        **(options | {"publication_queue_name": "other-edits"})
    )

    assert len(first) == 64
    assert first != second
