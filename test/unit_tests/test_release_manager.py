"""Tests for atomic release activation and retention."""

import os
from pathlib import Path

import pytest

from scripts.release_manager import activate_release, prune_releases, rollback_release


def create_release(root: Path, release_id: str, timestamp: int) -> Path:
    """Create a release directory with a controlled modification time."""
    release = root / "releases" / release_id
    release.mkdir(parents=True)
    (release / ".release-complete").touch()
    os.utime(release, ns=(timestamp, timestamp))
    return release


def test_activation_and_rollback_replace_only_current_symlink(tmp_path: Path) -> None:
    """Activation returns the exact prior target so rollback can restore it."""
    first = create_release(tmp_path, "first", 1)
    second = create_release(tmp_path, "second", 2)
    (tmp_path / "current").symlink_to(Path("releases") / first.name)

    previous = activate_release(tmp_path, second.name)

    assert previous == "releases/first"
    assert (tmp_path / "current").resolve() == second
    rollback_release(tmp_path, previous)
    assert (tmp_path / "current").resolve() == first


def test_failed_activation_leaves_current_unchanged(tmp_path: Path) -> None:
    """An invalid or incomplete candidate cannot replace the active release."""
    first = create_release(tmp_path, "first", 1)
    (tmp_path / "current").symlink_to(Path("releases") / first.name)

    with pytest.raises(ValueError, match="does not exist"):
        activate_release(tmp_path, "missing")

    assert (tmp_path / "current").resolve() == first


def test_incomplete_release_cannot_be_activated(tmp_path: Path) -> None:
    """An interrupted build is never exposed through current."""
    incomplete = tmp_path / "releases" / "incomplete"
    incomplete.mkdir(parents=True)

    with pytest.raises(ValueError, match="incomplete"):
        activate_release(tmp_path, incomplete.name)


def test_pruning_keeps_newest_releases_and_never_removes_active(tmp_path: Path) -> None:
    """Retention remains bounded without deleting an older active version."""
    releases = [create_release(tmp_path, f"release-{index}", index) for index in range(1, 5)]
    (tmp_path / "current").symlink_to(Path("releases") / releases[0].name)

    removed = prune_releases(tmp_path, keep=2)

    assert {path.name for path in removed} == {"release-2", "release-3"}
    assert releases[0].exists()
    assert not releases[2].exists()
    assert releases[3].exists()


def test_pruning_keeps_the_five_newest_releases(tmp_path: Path) -> None:
    """The default retention target removes only releases older than the newest five."""
    releases = [create_release(tmp_path, f"release-{index}", index) for index in range(1, 8)]
    (tmp_path / "current").symlink_to(Path("releases") / releases[-1].name)

    removed = prune_releases(tmp_path, keep=5)

    assert {path.name for path in removed} == {"release-1", "release-2"}
    assert all(release.exists() for release in releases[2:])


def test_pruning_removes_matching_runtime_configuration(tmp_path: Path) -> None:
    """Application and generated configuration retention remain aligned."""
    config_root = tmp_path / "etc"
    old = create_release(tmp_path, "old", 1)
    current = create_release(tmp_path, "current", 2)
    newest = create_release(tmp_path, "newest", 3)
    (tmp_path / "current").symlink_to(Path("releases") / current.name)
    for directory, suffix in (("deployments", ".ini"), ("haproxy-releases", ".cfg")):
        path = config_root / directory / f"{old.name}{suffix}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    (config_root / "pgrest-releases" / old.name).mkdir(parents=True)

    prune_releases(tmp_path, keep=2, config_root=config_root)

    assert not old.exists()
    assert newest.exists()
    assert not (config_root / "deployments" / "old.ini").exists()
    assert not (config_root / "haproxy-releases" / "old.cfg").exists()
    assert not (config_root / "pgrest-releases" / "old").exists()


def test_pruning_protects_the_immediate_rollback_release(tmp_path: Path) -> None:
    """Retention never removes the target needed for the latest rollback."""
    releases = [create_release(tmp_path, f"release-{index}", index) for index in range(1, 4)]
    (tmp_path / "current").symlink_to(Path("releases") / releases[2].name)

    prune_releases(tmp_path, keep=2, protected_release_ids=(releases[0].name,))

    assert releases[0].exists()
    assert not releases[1].exists()
    assert releases[2].exists()


@pytest.mark.parametrize("target", ["/tmp/release", "../release", "releases/missing", "releases/a/b"])
def test_rollback_rejects_targets_outside_known_releases(tmp_path: Path, target: str) -> None:
    """Rollback accepts only an existing direct child of releases."""
    with pytest.raises(ValueError):
        rollback_release(tmp_path, target)
