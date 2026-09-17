"""Offline unit tests for the page recheck script."""
from pathlib import Path
from unittest import mock

import pytest
import requests

from scripts.recheck_pages import (
    active_job_count,
    main,
    queue_check_job,
    read_titles,
    recheck_pages,
    run_sync_check,
    wait_for_capacity,
)


def _response(status_code: int, payload: object = None, text: str = "") -> mock.Mock:
    """Build a fake requests.Response."""
    response = mock.Mock(spec=requests.Response)
    response.status_code = status_code
    response.text = text
    response.json.return_value = payload
    if status_code >= 400:
        response.raise_for_status.side_effect = requests.HTTPError(str(status_code))
    else:
        response.raise_for_status.return_value = None
    return response


def test_read_titles_normalises_and_deduplicates(tmp_path: Path) -> None:
    """Titles keep file order, lose underscores, skip blanks and comments."""
    list_file = tmp_path / "pages.txt"
    list_file.write_text(
        "Alphabeter\n\n# affected by the section bug\nvolana\nAlphabeter\n  bevohoka  \n",
        encoding="utf-8",
    )
    assert read_titles(str(list_file)) == ["Alphabeter", "volana", "bevohoka"]


def test_active_job_count_reads_jobs_field() -> None:
    """The /jobs payload provides the active job count."""
    with mock.patch(
        "scripts.recheck_pages.requests.get",
        return_value=_response(200, {"jobs": 4}),
    ):
        assert active_job_count("http://translator:8000") == 4


def test_active_job_count_returns_none_on_failure() -> None:
    """Network or payload problems are reported as unknown capacity."""
    with mock.patch(
        "scripts.recheck_pages.requests.get",
        side_effect=requests.ConnectionError("down"),
    ):
        assert active_job_count("http://translator:8000") is None
    with mock.patch(
        "scripts.recheck_pages.requests.get",
        return_value=_response(200, {"jobs": "many"}),
    ):
        assert active_job_count("http://translator:8000") is None


def test_wait_for_capacity_cools_down_until_below_threshold() -> None:
    """Submission pauses while too many translation jobs are active."""
    with mock.patch(
        "scripts.recheck_pages.active_job_count", side_effect=[12, 3]
    ), mock.patch("scripts.recheck_pages.time.sleep") as sleep:
        wait_for_capacity("http://translator:8000", max_active_jobs=10, cooldown_seconds=15.0)
    sleep.assert_called_once_with(15.0)


def test_queue_check_job_posts_one_title() -> None:
    """The async route receives a single-title payload and returns job ids."""
    with mock.patch(
        "scripts.recheck_pages.requests.post",
        return_value=_response(202, {"jobs": [{"job_id": "abc123"}]}),
    ) as post:
        result = queue_check_job("http://translator:8000", "mg", "Alphabeter")
    post.assert_called_once()
    (url,), kwargs = post.call_args
    assert url == "http://translator:8000/wiktionary-pages/mg/check-jobs"
    assert kwargs["json"] == {"titles": ["Alphabeter"]}
    assert result == {"title": "Alphabeter", "job_ids": ["abc123"]}


def test_queue_check_job_rejects_non_202() -> None:
    """A non-202 response aborts the submission."""
    with mock.patch(
        "scripts.recheck_pages.requests.post",
        return_value=_response(503, {"error": "full"}, text="full"),
    ):
        with pytest.raises(RuntimeError, match="rejected"):
            queue_check_job("http://translator:8000", "mg", "Alphabeter")


def test_run_sync_check_returns_first_result() -> None:
    """The sync route returns the serialized check result of the title."""
    payload = {"results": [{"word": "volana", "status": "fixed", "message": "ok"}]}
    with mock.patch(
        "scripts.recheck_pages.requests.post", return_value=_response(200, payload)
    ) as post:
        result = run_sync_check("http://translator:8000", "mg", "volana")
    (url,), kwargs = post.call_args
    assert url == "http://translator:8000/wiktionary-pages/mg/check"
    assert result["status"] == "fixed"


def test_recheck_pages_queues_every_title() -> None:
    """Every listed page is queued when capacity is available."""
    with mock.patch(
        "scripts.recheck_pages.wait_for_capacity"
    ) as wait, mock.patch(
        "scripts.recheck_pages.queue_check_job",
        side_effect=[{"title": "a", "job_ids": ["1"]}, {"title": "b", "job_ids": ["2"]}],
    ), mock.patch("scripts.recheck_pages.time.sleep"):
        counts = recheck_pages("http://translator:8000", "mg", ["a", "b"])
    assert wait.call_count == 2
    assert counts == {"queued": 2}


def test_recheck_pages_counts_failures() -> None:
    """A rejected submission is counted without aborting the run."""
    with mock.patch("scripts.recheck_pages.wait_for_capacity"), mock.patch(
        "scripts.recheck_pages.queue_check_job",
        side_effect=[RuntimeError("rejected"), {"title": "b", "job_ids": ["2"]}],
    ), mock.patch("scripts.recheck_pages.time.sleep"):
        counts = recheck_pages("http://translator:8000", "mg", ["a", "b"])
    assert counts == {"failed": 1, "queued": 1}


def test_main_dry_run_only_lists_titles(tmp_path: Path, capsys) -> None:
    """The dry run performs no HTTP call."""
    list_file = tmp_path / "pages.txt"
    list_file.write_text("Alphabeter\nvolana\n", encoding="utf-8")
    with mock.patch("scripts.recheck_pages.requests.post") as post:
        assert main([str(list_file), "--dry-run"]) == 0
    post.assert_not_called()
    output = capsys.readouterr().out
    assert "2 pages will be rechecked." in output
    assert "Alphabeter" in output and "volana" in output


def test_main_missing_file_returns_error() -> None:
    """An unreadable list file exits with an error code."""
    assert main(["/nonexistent/pages.txt"]) == 1


def test_main_empty_file_is_a_noop(tmp_path: Path) -> None:
    """An empty list succeeds without contacting the service."""
    list_file = tmp_path / "pages.txt"
    list_file.write_text("", encoding="utf-8")
    with mock.patch("scripts.recheck_pages.requests.post") as post:
        assert main([str(list_file)]) == 0
    post.assert_not_called()


def test_main_reports_failed_rechecks(tmp_path: Path) -> None:
    """A submission failure makes the script exit with an error code."""
    list_file = tmp_path / "pages.txt"
    list_file.write_text("Alphabeter\n", encoding="utf-8")
    with mock.patch("scripts.recheck_pages.wait_for_capacity"), mock.patch(
        "scripts.recheck_pages.queue_check_job",
        side_effect=RuntimeError("rejected"),
    ), mock.patch("scripts.recheck_pages.time.sleep"):
        assert main([str(list_file)]) == 1
