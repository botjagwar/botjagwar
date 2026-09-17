"""Tests for the trusted terminal Wiktionary approval boundary."""

from __future__ import annotations

import io
from typing import Any, Dict

import pytest

import api.wiktionary_review_cli as review_cli
from api.services.wiktionary_review_service import WiktionaryReviewError


DIGEST = "a" * 64
PROPOSAL_ID = f"wiktionary-fix:{DIGEST}"


class TtyBuffer(io.StringIO):
    """String buffer with a configurable interactive-terminal identity."""

    def __init__(self, value: str = "", *, interactive: bool = True) -> None:
        super().__init__(value)
        self.interactive = interactive

    def isatty(self) -> bool:
        """Return the configured terminal identity."""
        return self.interactive


class InterruptingTty(TtyBuffer):
    """Interactive input that simulates Ctrl-C at confirmation."""

    def readline(self, *_args: Any, **_kwargs: Any) -> str:
        """Interrupt the pending confirmation read."""
        raise KeyboardInterrupt


class DummyReviewService:
    """Capture trusted CLI proposal reads and queue attempts."""

    def __init__(self) -> None:
        self.get_calls: list[str] = []
        self.queue_calls: list[tuple[str, str]] = []
        self.state = "prepared"
        self.stored_digest = DIGEST
        self.queue_error: Exception | None = None

    def get_fix_proposal(self, proposal_id: str) -> Dict[str, Any]:
        """Return one complete test proposal."""
        self.get_calls.append(proposal_id)
        return {
            "schema_version": 2,
            "event_id": "page-check:job-1",
            "target_title": "alika",
            "target_content_sha256": "b" * 64,
            "english_title": "dog",
            "english_content_sha256": "c" * 64,
            "replacement_content_sha256": "d" * 64,
            "diff_sha256": "e" * 64,
            "summary": "fanitsiana",
            "minor": False,
            "publication_queue": "translated",
            "publication_action": "edit_malagasy_wiktionary_page",
            "environment_fingerprint": "f" * 64,
            "prepared_at": 10.0,
            "expires_at": 20.0,
            "proposal_id": proposal_id,
            "approval_digest": self.stored_digest,
            "state": self.state,
            "diff": "--- old\n+++ new\n-old\x1b[2J\\value\n+new\n",
        }

    def queue_reviewed_fix(
        self, proposal_id: str, approval_digest: str
    ) -> Dict[str, Any]:
        """Capture one queue attempt or raise its configured outcome."""
        self.queue_calls.append((proposal_id, approval_digest))
        if self.queue_error is not None:
            raise self.queue_error
        return {
            "status": "queued_for_publication",
            "published": False,
            "queue": "translated",
            "proposal_id": proposal_id,
        }


def _arguments() -> list[str]:
    """Return valid trusted CLI identifiers."""
    return ["--proposal-id", PROPOSAL_ID, "--approval-digest", DIGEST]


def test_non_tty_invocation_refuses_before_reading_proposal() -> None:
    service = DummyReviewService()
    errors = TtyBuffer()

    status = review_cli.main(
        _arguments(),
        service=service,  # type: ignore[arg-type]
        input_stream=TtyBuffer(interactive=False),
        output_stream=TtyBuffer(),
        error_stream=errors,
    )

    assert status == 1
    assert "interactive terminal" in errors.getvalue()
    assert service.get_calls == []
    assert service.queue_calls == []


def test_wrong_confirmation_displays_safe_complete_contract_without_queueing() -> None:
    service = DummyReviewService()
    output = TtyBuffer()

    status = review_cli.main(
        _arguments(),
        service=service,  # type: ignore[arg-type]
        input_stream=TtyBuffer("no\n"),
        output_stream=output,
        error_stream=TtyBuffer(),
    )

    rendered = output.getvalue()
    assert status == 1
    assert "target_content_sha256: " + "b" * 64 in rendered
    assert "approval_digest: " + DIGEST in rendered
    assert "-old\\x1b[2J\\\\value" in rendered
    assert "\x1b" not in rendered
    assert service.queue_calls == []


def test_exact_proposal_confirmation_queues_once() -> None:
    service = DummyReviewService()
    output = TtyBuffer()

    status = review_cli.main(
        _arguments(),
        service=service,  # type: ignore[arg-type]
        input_stream=TtyBuffer(f"QUEUE {DIGEST[:12]}\n"),
        output_stream=output,
        error_stream=TtyBuffer(),
    )

    assert status == 0
    assert service.queue_calls == [(PROPOSAL_ID, DIGEST)]
    assert "Queued for publication" in output.getvalue()
    assert "write is not yet confirmed" in output.getvalue()


@pytest.mark.parametrize("state", ["queued", "queueing", "queue_unknown"])
def test_non_prepared_proposal_cannot_be_approved(state: str) -> None:
    service = DummyReviewService()
    service.state = state

    status = review_cli.main(
        _arguments(),
        service=service,  # type: ignore[arg-type]
        input_stream=TtyBuffer(f"QUEUE {DIGEST[:12]}\n"),
        output_stream=TtyBuffer(),
        error_stream=TtyBuffer(),
    )

    assert status == 1
    assert service.queue_calls == []


def test_unknown_queue_outcome_is_not_retried() -> None:
    service = DummyReviewService()
    service.queue_error = WiktionaryReviewError(
        "The reviewed fix queue outcome is unknown and requires reconciliation."
    )
    errors = TtyBuffer()

    status = review_cli.main(
        _arguments(),
        service=service,  # type: ignore[arg-type]
        input_stream=TtyBuffer(f"QUEUE {DIGEST[:12]}\n"),
        output_stream=TtyBuffer(),
        error_stream=errors,
    )

    assert status == 1
    assert len(service.queue_calls) == 1
    assert "requires reconciliation" in errors.getvalue()


def test_interrupted_confirmation_cancels_without_queueing() -> None:
    service = DummyReviewService()

    status = review_cli.main(
        _arguments(),
        service=service,  # type: ignore[arg-type]
        input_stream=InterruptingTty(),
        output_stream=TtyBuffer(),
        error_stream=TtyBuffer(),
    )

    assert status == 1
    assert service.queue_calls == []


def test_cli_has_no_noninteractive_approval_option() -> None:
    with pytest.raises(SystemExit):
        review_cli._argument_parser().parse_args(  # pylint: disable=protected-access
            [*_arguments(), "--yes"]
        )
