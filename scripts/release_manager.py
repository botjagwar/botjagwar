#!/usr/bin/env python3
"""Atomically activate, roll back, and prune Botjagwar releases."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from pathlib import Path


RELEASE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def activate_release(deployment_root: Path, release_id: str) -> str | None:
    """Atomically point current at a complete release and return its previous target."""
    _validate_release_id(release_id)
    releases_root = deployment_root / "releases"
    release = releases_root / release_id
    if not release.is_dir():
        raise ValueError(f"Release does not exist: {release}")
    if not (release / ".release-complete").is_file():
        raise ValueError(f"Release is incomplete: {release}")
    current = deployment_root / "current"
    previous_target = os.readlink(current) if current.is_symlink() else None
    _replace_symlink(current, Path("releases") / release_id)
    return previous_target


def rollback_release(deployment_root: Path, target: str) -> None:
    """Atomically restore current to a previously returned release target."""
    normalized_target = _validated_target(deployment_root, target)
    _replace_symlink(deployment_root / "current", normalized_target)


def prune_releases(
    deployment_root: Path,
    keep: int,
    config_root: Path | None = None,
    protected_release_ids: tuple[str, ...] = (),
) -> list[Path]:
    """Remove old inactive releases while retaining at least two versions."""
    if keep < 2:
        raise ValueError("Release retention must keep at least two releases.")
    releases_root = deployment_root / "releases"
    if not releases_root.exists():
        return []
    current = deployment_root / "current"
    active = current.resolve() if current.is_symlink() else None
    all_releases = [path for path in releases_root.iterdir() if path.is_dir()]
    incomplete = [path for path in all_releases if not (path / ".release-complete").is_file() and path != active]
    releases = sorted(
        (path for path in all_releases if (path / ".release-complete").is_file()),
        key=lambda path: (path.stat().st_mtime_ns, path.name),
        reverse=True,
    )
    retained: set[Path] = set()
    if active:
        retained.add(active)
    for release_id in protected_release_ids:
        _validate_release_id(release_id)
        protected = releases_root / release_id
        if protected.is_dir():
            retained.add(protected)
    for release in releases:
        if len(retained) >= keep:
            break
        retained.add(release)
    removed: list[Path] = []
    for release in [*incomplete, *releases]:
        if release not in retained:
            shutil.rmtree(release)
            if config_root:
                (config_root / "deployments" / f"{release.name}.ini").unlink(missing_ok=True)
                (config_root / "haproxy-releases" / f"{release.name}.cfg").unlink(missing_ok=True)
                shutil.rmtree(config_root / "pgrest-releases" / release.name, ignore_errors=True)
            removed.append(release)
    return removed


def _validate_release_id(release_id: str) -> None:
    """Reject release identifiers that could escape the release directory."""
    if not RELEASE_ID_PATTERN.fullmatch(release_id):
        raise ValueError(f"Invalid release identifier {release_id!r}.")


def _validated_target(deployment_root: Path, target: str) -> Path:
    """Validate a rollback target and return its normalized relative path."""
    target_path = Path(target)
    if target_path.is_absolute() or len(target_path.parts) != 2 or target_path.parts[0] != "releases":
        raise ValueError(f"Invalid rollback target {target!r}.")
    _validate_release_id(target_path.parts[1])
    if not (deployment_root / target_path).is_dir():
        raise ValueError(f"Rollback target does not exist: {target}")
    if not (deployment_root / target_path / ".release-complete").is_file():
        raise ValueError(f"Rollback target is incomplete: {target}")
    return target_path


def _replace_symlink(path: Path, target: Path) -> None:
    """Replace a symlink with one atomic rename in its parent directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}")
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(target)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path, help="Deployment root containing releases and current")
    parser.add_argument("--config-root", type=Path, help="Optional root containing release-specific runtime config")
    parser.add_argument("--protect", action="append", default=[], help="Release identifier protected from pruning")
    subparsers = parser.add_subparsers(dest="command", required=True)
    activate = subparsers.add_parser("activate")
    activate.add_argument("release_id")
    rollback = subparsers.add_parser("rollback")
    rollback.add_argument("target")
    prune = subparsers.add_parser("prune")
    prune.add_argument("--keep", required=True, type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run a release-management command."""
    args = build_parser().parse_args(argv)
    try:
        if args.command == "activate":
            previous = activate_release(args.root, args.release_id)
            if previous:
                print(previous)
        elif args.command == "rollback":
            rollback_release(args.root, args.target)
        else:
            for removed in prune_releases(args.root, args.keep, args.config_root, tuple(args.protect)):
                print(removed)
    except (OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
