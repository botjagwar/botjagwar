import fcntl
from pathlib import Path

import pytest

from scripts.fetch_dashboard_statistics import (
    LOCK_FILENAME,
    SOURCE_ENVIRONMENT_VARIABLE,
    copy_remote_statistics,
    fetch_dashboard_statistics,
    main,
    parse_statistics_source,
)
from scripts.refresh_dashboard_statistics import (
    acquire_statistics_lock,
    render_statistics,
    validate_statistics_file,
)


def statistics_row(entry_count: int = 12) -> dict[str, object]:
    """Return one complete row in the shape consumed by Atlas."""
    return {
        "period": "last_day",
        "period_start": "2026-08-13T18:00:00+00:00",
        "period_end": "2026-08-14T18:00:00+00:00",
        "entry_count": entry_count,
        "translated_languages": [{"language": "fr", "translated_entries": 3}],
        "generated_at": "2026-08-14T18:00:00+00:00",
        "missing_timestamp_count": 0,
    }


def hold_refresh_lock(directory: Path):
    """Acquire the refresh lock out-of-band and return its open file handle."""
    lock_file = (directory / LOCK_FILENAME).open("a", encoding="utf-8")
    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    return lock_file


def test_parse_statistics_source_accepts_host_and_path() -> None:
    """The source is split into an SSH target and a remote path."""
    assert parse_statistics_source("trano:/var/lib/botjagwar/atlas/logs/dashboard-statistics.json") == (
        "trano",
        "/var/lib/botjagwar/atlas/logs/dashboard-statistics.json",
    )


@pytest.mark.parametrize("source", ["", "trano", ":path", "host:"])
def test_parse_statistics_source_rejects_malformed_sources(source: str) -> None:
    """Missing host or path is rejected before any SSH work happens."""
    with pytest.raises(ValueError, match="host:path"):
        parse_statistics_source(source)


def test_copy_remote_statistics_runs_scp_in_batch_mode(mocker) -> None:
    """The remote snapshot is copied without any interactive prompt."""
    completed = mocker.Mock()
    completed.returncode = 0
    subprocess = mocker.patch("scripts.fetch_dashboard_statistics.subprocess.run", return_value=completed)

    copy_remote_statistics("trano", "/remote/dashboard-statistics.json", Path("/tmp/local.json"))

    command = subprocess.call_args.args[0]
    assert command[0] == "scp"
    assert "BatchMode=yes" in command
    assert command[-2:] == ["trano:/remote/dashboard-statistics.json", "/tmp/local.json"]


def test_copy_remote_statistics_raises_on_scp_failure(mocker) -> None:
    """A failed copy surfaces as a fetch error instead of a blank snapshot."""
    completed = mocker.Mock()
    completed.returncode = 1
    completed.stderr = "Connection refused"
    completed.stdout = ""
    mocker.patch("scripts.fetch_dashboard_statistics.subprocess.run", return_value=completed)

    with pytest.raises(RuntimeError, match="Could not fetch dashboard statistics"):
        copy_remote_statistics("trano", "/remote/dashboard-statistics.json", Path("/tmp/local.json"))


def test_fetch_dashboard_statistics_copies_validates_and_replaces(mocker, tmp_path: Path) -> None:
    """The remote snapshot is copied through a temporary file and atomically renamed."""
    output = tmp_path / "atlas" / "logs" / "dashboard-statistics.json"
    completed = mocker.Mock()
    completed.returncode = 0
    completed.stderr = ""
    completed.stdout = ""

    def copy_remote_side_effect(target, remote_path, local_path):
        local_path.write_text(render_statistics([statistics_row()]), encoding="utf-8")

    mocker.patch("scripts.fetch_dashboard_statistics.copy_remote_statistics", side_effect=copy_remote_side_effect)

    assert fetch_dashboard_statistics("trano:/remote/dashboard-statistics.json", output) == 1

    validate_statistics_file(output)
    assert list(output.parent.glob(".dashboard-statistics.json.*")) == []
    released_lock = acquire_statistics_lock(output.parent / LOCK_FILENAME)
    assert released_lock is not None
    released_lock.close()


def test_fetch_dashboard_statistics_keeps_previous_snapshot_when_copy_fails(mocker, tmp_path: Path) -> None:
    """A failed copy never blanks the file that Nginx serves."""
    output = tmp_path / "dashboard-statistics.json"
    previous_snapshot = render_statistics([statistics_row(entry_count=5)])
    output.write_text(previous_snapshot, encoding="utf-8")
    mocker.patch(
        "scripts.fetch_dashboard_statistics.copy_remote_statistics",
        side_effect=RuntimeError("Could not fetch dashboard statistics from trano"),
    )

    with pytest.raises(RuntimeError, match="Could not fetch dashboard statistics"):
        fetch_dashboard_statistics("trano:/remote/dashboard-statistics.json", output)

    assert output.read_text(encoding="utf-8") == previous_snapshot


@pytest.mark.parametrize("remote_content", ["not-json", "[]", '[{"period":"last_day"}]'])
def test_fetch_dashboard_statistics_keeps_previous_snapshot_when_remote_is_invalid(
    mocker, tmp_path: Path, remote_content: str
) -> None:
    """Invalid remote content never replaces the file that Nginx serves."""
    output = tmp_path / "dashboard-statistics.json"
    previous_snapshot = render_statistics([statistics_row(entry_count=5)])
    output.write_text(previous_snapshot, encoding="utf-8")

    def copy_remote_side_effect(target, remote_path, local_path):
        local_path.write_text(remote_content, encoding="utf-8")

    mocker.patch("scripts.fetch_dashboard_statistics.copy_remote_statistics", side_effect=copy_remote_side_effect)

    with pytest.raises((RuntimeError, ValueError)):
        fetch_dashboard_statistics("trano:/remote/dashboard-statistics.json", output)

    assert output.read_text(encoding="utf-8") == previous_snapshot


def test_fetch_dashboard_statistics_skips_an_overlapping_refresh(mocker, tmp_path: Path) -> None:
    """A second cron process exits before copying or replacing the snapshot."""
    output = tmp_path / "dashboard-statistics.json"
    previous_snapshot = render_statistics([statistics_row(entry_count=5)])
    output.write_text(previous_snapshot, encoding="utf-8")
    copy = mocker.patch("scripts.fetch_dashboard_statistics.copy_remote_statistics")
    holder = hold_refresh_lock(tmp_path)

    try:
        assert fetch_dashboard_statistics("trano:/remote/dashboard-statistics.json", output) == 0
    finally:
        holder.close()

    copy.assert_not_called()
    assert output.read_text(encoding="utf-8") == previous_snapshot


def test_fetch_dashboard_statistics_fails_on_lock_contention_without_valid_snapshot(
    mocker, tmp_path: Path
) -> None:
    """Lock contention is unsuccessful unless Nginx already has a valid snapshot."""
    output = tmp_path / "dashboard-statistics.json"
    copy = mocker.patch("scripts.fetch_dashboard_statistics.copy_remote_statistics")
    holder = hold_refresh_lock(tmp_path)

    try:
        with pytest.raises(RuntimeError, match="no valid snapshot"):
            fetch_dashboard_statistics("trano:/remote/dashboard-statistics.json", output)
    finally:
        holder.close()

    copy.assert_not_called()


def test_main_fails_without_the_source_environment_variable(monkeypatch) -> None:
    """The cron entry reports failure when no remote source is configured."""
    monkeypatch.delenv(SOURCE_ENVIRONMENT_VARIABLE, raising=False)

    assert main() == 1


def test_main_fetches_the_configured_source(mocker, monkeypatch, tmp_path: Path) -> None:
    """The configured remote source lands in the Atlas state directory."""
    output = tmp_path / "atlas" / "logs" / "dashboard-statistics.json"

    def copy_remote_side_effect(target, remote_path, local_path):
        local_path.write_text(render_statistics([statistics_row()]), encoding="utf-8")

    monkeypatch.setenv(SOURCE_ENVIRONMENT_VARIABLE, "trano:/remote/dashboard-statistics.json")
    monkeypatch.setenv("BOTJAGWAR_ATLAS_STATE_DIR", str(tmp_path / "atlas"))
    mocker.patch("scripts.fetch_dashboard_statistics.copy_remote_statistics", side_effect=copy_remote_side_effect)

    assert main() == 0

    validate_statistics_file(output)


def test_main_returns_failure_when_the_fetch_fails(mocker, monkeypatch, tmp_path: Path) -> None:
    """A failed fetch is reported as a cron failure."""
    monkeypatch.setenv(SOURCE_ENVIRONMENT_VARIABLE, "trano:/remote/dashboard-statistics.json")
    monkeypatch.setenv("BOTJAGWAR_ATLAS_STATE_DIR", str(tmp_path / "atlas"))
    mocker.patch(
        "scripts.fetch_dashboard_statistics.copy_remote_statistics",
        side_effect=RuntimeError("Could not fetch dashboard statistics"),
    )

    assert main() == 1
