"""Trusted interactive approval boundary for reviewed Wiktionary fixes."""

from __future__ import annotations

import argparse
import re
import sys
from typing import Any, Dict, Sequence, TextIO

from api.services.page_check_review_queue import PageCheckReviewQueueError
from api.services.wiktionary_review_service import (
    WiktionaryReviewError,
    WiktionaryReviewService,
)
from api.wiktionary_mcp import get_configured_review_service


_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_CONTRACT_FIELDS = (
    "schema_version",
    "event_id",
    "target_title",
    "target_content_sha256",
    "english_title",
    "english_content_sha256",
    "replacement_content_sha256",
    "diff_sha256",
    "summary",
    "minor",
    "publication_queue",
    "publication_action",
    "environment_fingerprint",
    "prepared_at",
    "expires_at",
    "proposal_id",
    "approval_digest",
)


class WiktionaryReviewCliError(RuntimeError):
    """Raised when trusted terminal approval cannot be established."""


def _terminal_safe(value: str) -> str:
    """Render untrusted text without terminal controls or ambiguous backslashes."""
    rendered = []
    for character in value:
        codepoint = ord(character)
        if character == "\n":
            rendered.append(character)
        elif character == "\\":
            rendered.append("\\\\")
        elif character.isprintable():
            rendered.append(character)
        elif codepoint <= 0xFF:
            rendered.append(f"\\x{codepoint:02x}")
        elif codepoint <= 0xFFFF:
            rendered.append(f"\\u{codepoint:04x}")
        else:
            rendered.append(f"\\U{codepoint:08x}")
    return "".join(rendered)


def _validate_identifiers(proposal_id: str, approval_digest: str) -> None:
    """Reject malformed or mutually inconsistent proposal identifiers."""
    if not _SHA256_PATTERN.fullmatch(approval_digest):
        raise WiktionaryReviewCliError(
            "The approval digest must be 64 lowercase hex characters."
        )
    if proposal_id != f"wiktionary-fix:{approval_digest}":
        raise WiktionaryReviewCliError(
            "The proposal ID must be the wiktionary-fix ID for the approval digest."
        )


def _display_proposal(proposal: Dict[str, Any], output: TextIO) -> None:
    """Display the complete immutable contract and safely escaped exact diff."""
    output.write("Reviewed Wiktionary fix contract\n")
    for field in _CONTRACT_FIELDS:
        output.write(f"{field}: {_terminal_safe(str(proposal[field]))}\n")
    output.write("diff (backslashes and terminal controls escaped):\n")
    diff = str(proposal["diff"])
    output.write(_terminal_safe(diff))
    if not diff.endswith("\n"):
        output.write("\n")


def confirm_and_queue(
    proposal_id: str,
    approval_digest: str,
    *,
    service: WiktionaryReviewService | None = None,
    input_stream: TextIO | None = None,
    output_stream: TextIO | None = None,
) -> Dict[str, Any]:
    """Require a trusted TTY confirmation before queueing one exact proposal."""
    source = input_stream or sys.stdin
    output = output_stream or sys.stdout
    if not source.isatty() or not output.isatty():
        raise WiktionaryReviewCliError(
            "Approval requires interactive terminal input and output."
        )
    _validate_identifiers(proposal_id, approval_digest)
    review_service = service or get_configured_review_service()
    proposal = review_service.get_fix_proposal(proposal_id)
    if proposal.get("state") != "prepared":
        raise WiktionaryReviewCliError("Only a prepared proposal can be approved.")
    if proposal.get("approval_digest") != approval_digest:
        raise WiktionaryReviewCliError(
            "The supplied approval digest does not match the stored proposal."
        )
    _display_proposal(proposal, output)
    phrase = f"QUEUE {approval_digest[:12]}"
    output.write(f"Type {phrase} to queue this exact proposal: ")
    output.flush()
    response = source.readline()
    if not response:
        raise WiktionaryReviewCliError("Approval was cancelled.")
    response = response.removesuffix("\n").removesuffix("\r")
    if response != phrase:
        raise WiktionaryReviewCliError("The confirmation phrase did not match.")
    return review_service.queue_reviewed_fix(proposal_id, approval_digest)


def _argument_parser() -> argparse.ArgumentParser:
    """Build the non-abbreviating trusted approval argument parser."""
    parser = argparse.ArgumentParser(
        description="Review and queue one prepared Malagasy Wiktionary fix.",
        allow_abbrev=False,
    )
    parser.add_argument("--proposal-id", required=True)
    parser.add_argument("--approval-digest", required=True)
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    service: WiktionaryReviewService | None = None,
    input_stream: TextIO | None = None,
    output_stream: TextIO | None = None,
    error_stream: TextIO | None = None,
) -> int:
    """Run one interactive approval attempt without automatic retries."""
    arguments = _argument_parser().parse_args(argv)
    output = output_stream or sys.stdout
    errors = error_stream or sys.stderr
    try:
        result = confirm_and_queue(
            arguments.proposal_id,
            arguments.approval_digest,
            service=service,
            input_stream=input_stream,
            output_stream=output,
        )
    except KeyboardInterrupt:
        errors.write("Approval was cancelled.\n")
        return 1
    except (
        PageCheckReviewQueueError,
        WiktionaryReviewCliError,
        WiktionaryReviewError,
        ValueError,
    ) as error:
        errors.write(f"Error: {_terminal_safe(str(error))}\n")
        return 1
    output.write(
        "Queued for publication; the Malagasy Wiktionary write is not yet confirmed.\n"
    )
    output.write(f"queue: {_terminal_safe(str(result['queue']))}\n")
    output.write(f"proposal_id: {_terminal_safe(str(result['proposal_id']))}\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
