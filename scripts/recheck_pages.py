#!/usr/bin/env python3
"""Re-check a list of Malagasy Wiktionary pages through the page-check pipeline.

Read a newline-delimited list of page titles and submit each one to the
entry-translator v2 page checker, which verifies every language section of the
page against its source wiktionary and queues a corrected version for
publication when a section is wrong. Pages corrupted by the renderer section
deletion bug keep their untouched source content, so the checker detects the
mismatch and rewrites the section in place.

By default one asynchronous check job is queued per title
(``POST /wiktionary-pages/{language}/check-jobs``) while the active translation
job count (``GET /jobs``) stays below the configured threshold. Use ``--sync``
to run each check synchronously instead (``POST .../check``).
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Sequence
from typing import Any
from urllib.parse import quote

import requests

DEFAULT_SERVER = "127.0.0.1"
DEFAULT_PORT = 8000
DEFAULT_LANGUAGE = "mg"
DEFAULT_MAX_ACTIVE_JOBS = 10
DEFAULT_COOLDOWN_SECONDS = 15.0
DEFAULT_DELAY_SECONDS = 1.0
REQUEST_TIMEOUT_SECONDS = (3.05, 30)
USER_AGENT = "Botjagwar page recheck"


def read_titles(path: str) -> list[str]:
    """Return the unique page titles of a newline-delimited list file.

    Blank lines and ``#`` comment lines are skipped, underscores are converted
    to spaces, and duplicates are removed while keeping the file order.
    """
    with open(path, "r", encoding="utf-8") as list_file:
        titles = []
        seen = set()
        for raw_line in list_file:
            title = raw_line.strip().replace("_", " ")
            if not title or title.startswith("#") or title in seen:
                continue
            seen.add(title)
            titles.append(title)
    return titles


def active_job_count(base_url: str) -> int | None:
    """Return the current translation job count, or None when unavailable."""
    try:
        response = requests.get(
            f"{base_url}/jobs",
            headers={"Accept": "application/json", "User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
    except (ValueError, requests.RequestException):
        return None
    jobs = data.get("jobs") if isinstance(data, dict) else None
    return jobs if isinstance(jobs, int) else None


def wait_for_capacity(
    base_url: str,
    max_active_jobs: int,
    cooldown_seconds: float,
) -> None:
    """Block until the active translation job count drops below the threshold."""
    while True:
        jobs = active_job_count(base_url)
        if jobs is None:
            time.sleep(0.5)
            continue
        if jobs < max_active_jobs:
            print(f"There are {jobs} jobs currently in progress")
            return
        print(
            f"COOLING DOWN: sleeping for {cooldown_seconds:g} seconds as there "
            f"are {jobs} jobs currently in progress"
        )
        time.sleep(cooldown_seconds)


def queue_check_job(base_url: str, language: str, title: str) -> dict[str, Any]:
    """Queue one asynchronous page check job for a title."""
    attempts = 100

    for attempt in range(attempts):
        response = requests.post(
            f"{base_url}/wiktionary-pages/{quote(language, safe='')}/check-jobs",
            json={"titles": [title]},
            headers={"Accept": "application/json", "User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )

        if response.status_code != 202:
            time.sleep(1.05**attempt)
        else:
            data = response.json()
            job_ids = [job.get("job_id") for job in data.get("jobs", [])]
            return {"title": title, "job_ids": job_ids}

        raise RuntimeError(
            f"Page check for '{title}' was rejected "
            f"(HTTP {response.status_code}): {response.text}"
        )


def run_sync_check(base_url: str, language: str, title: str) -> dict[str, Any]:
    """Run one page check synchronously and return its result."""
    response = requests.post(
        f"{base_url}/wiktionary-pages/{quote(language, safe='')}/check",
        json={"titles": [title]},
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
        timeout=(REQUEST_TIMEOUT_SECONDS[0], 300),
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"Page check for '{title}' failed "
            f"(HTTP {response.status_code}): {response.text}"
        )
    data = response.json()
    results = data.get("results", [])
    return results[0] if results else {"word": title, "status": "unknown"}


def recheck_pages(
    base_url: str,
    language: str,
    titles: Sequence[str],
    *,
    sync: bool = False,
    max_active_jobs: int = DEFAULT_MAX_ACTIVE_JOBS,
    cooldown_seconds: float = DEFAULT_COOLDOWN_SECONDS,
    delay_seconds: float = DEFAULT_DELAY_SECONDS,
) -> dict[str, int]:
    """Submit every title for rechecking and return per-status counters.

    Returns:
        A counter keyed by outcome: "queued", "good", "fixed", "unverifiable",
        "error" (synchronous checks) and "failed" (submission errors).
    """
    counts: dict[str, int] = {}
    for title in titles:
        print(">>>", title, "<<<")
        if sync:
            time.sleep(delay_seconds)
            try:
                result = run_sync_check(base_url, language, title)
            except (RuntimeError, requests.RequestException) as exc:
                print(f"Recheck failed for {title}: {exc}")
                counts["failed"] = counts.get("failed", 0) + 1
                continue
            status = str(result.get("status", "unknown"))
            print(f"Recheck {status} for {title}: {result.get('message', '')}")
            counts[status] = counts.get(status, 0) + 1
            continue

        wait_for_capacity(base_url, max_active_jobs, cooldown_seconds)
        time.sleep(delay_seconds)
        try:
            queued = queue_check_job(base_url, language, title)
        except (RuntimeError, requests.RequestException) as exc:
            print(f"Recheck failed for {title}: {exc}")
            counts["failed"] = counts.get("failed", 0) + 1
            continue
        print(f"Queued recheck for {title}: {', '.join(queued['job_ids'])}")
        counts["queued"] = counts.get("queued", 0) + 1
    return counts


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "list_file",
        help="newline-delimited file with the page titles to recheck",
    )
    parser.add_argument(
        "--language",
        default=DEFAULT_LANGUAGE,
        help=f"Wiktionary language of the pages (default: {DEFAULT_LANGUAGE})",
    )
    parser.add_argument(
        "--server",
        default=DEFAULT_SERVER,
        help=f"entry-translator v2 host (default: {DEFAULT_SERVER})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"entry-translator v2 port (default: {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="run each check synchronously instead of queueing check jobs",
    )
    parser.add_argument(
        "--max-active-jobs",
        type=int,
        default=DEFAULT_MAX_ACTIVE_JOBS,
        help=(
            "pause submissions while the active translation job count reaches "
            f"this threshold (default: {DEFAULT_MAX_ACTIVE_JOBS})"
        ),
    )
    parser.add_argument(
        "--cooldown-seconds",
        type=float,
        default=DEFAULT_COOLDOWN_SECONDS,
        help=f"backpressure sleep duration (default: {DEFAULT_COOLDOWN_SECONDS:g})",
    )
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=DEFAULT_DELAY_SECONDS,
        help=f"delay between consecutive submissions (default: {DEFAULT_DELAY_SECONDS:g})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="only print the titles that would be rechecked",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Recheck every page of the list file against its source wiktionary."""
    args = parse_arguments(argv)
    try:
        titles = read_titles(args.list_file)
    except OSError as exc:
        print(f"Cannot read the list file: {exc}")
        return 1
    if not titles:
        print("No page titles to recheck.")
        return 0

    print(f"{len(titles)} pages will be rechecked.")
    if args.dry_run:
        for title in titles:
            print(title)
        return 0

    base_url = f"http://{args.server}:{args.port}"
    counts = recheck_pages(
        base_url,
        args.language,
        titles,
        sync=args.sync,
        max_active_jobs=args.max_active_jobs,
        cooldown_seconds=args.cooldown_seconds,
        delay_seconds=args.delay_seconds,
    )
    print(
        "Recheck finished: "
        + ", ".join(f"{status}={count}" for status, count in sorted(counts.items()))
    )
    return 1 if counts.get("failed") else 0


if __name__ == "__main__":
    sys.exit(main())
