#!/usr/bin/env python3
"""Synchronize PostgREST database URIs from protected Botjagwar configuration."""

from __future__ import annotations

import argparse
import configparser
import re
from pathlib import Path


def sync_postgrest_database_uri(config_path: Path, postgrest_directory: Path) -> int:
    """Write the configured database URI into every PostgREST instance file."""
    parser = configparser.ConfigParser(interpolation=None)
    if not parser.read(config_path, encoding="utf-8"):
        raise ValueError(f"Unable to read Botjagwar configuration: {config_path}")
    try:
        database_uri = parser.get("global", "database_uri")
    except (configparser.NoOptionError, configparser.NoSectionError) as error:
        raise ValueError(f"Missing global.database_uri in {config_path}") from error
    if any(character in database_uri for character in {'"', "\n", "\r"}):
        raise ValueError("Database URI contains unsupported characters")

    updated_files = 0
    for postgrest_path in sorted(postgrest_directory.glob("pgrest_*.ini")):
        content = postgrest_path.read_text(encoding="utf-8")
        updated, count = re.subn(
            r'(?m)^db-uri\s*=.*$',
            f'db-uri = "{database_uri}"',
            content,
            count=1,
        )
        if count != 1:
            raise ValueError(f"Missing db-uri in {postgrest_path}")
        postgrest_path.write_text(updated, encoding="utf-8")
        updated_files += 1
    if updated_files == 0:
        raise ValueError(f"No PostgREST configuration files found in {postgrest_directory}")
    return updated_files


def main() -> int:
    """Run the PostgREST database URI synchronizer."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config_path", type=Path)
    parser.add_argument("postgrest_directory", type=Path)
    args = parser.parse_args()
    try:
        sync_postgrest_database_uri(args.config_path, args.postgrest_directory)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
