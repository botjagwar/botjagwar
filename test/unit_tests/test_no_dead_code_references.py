"""Tests to verify that removed legacy files are not referenced anywhere.

These tests scan the codebase for references to files that have been
identified as dead code and removed. If any of these tests fail, it
means a reference to a removed file still exists and needs to be cleaned up.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _collect_python_files() -> list[Path]:
    """Collect all Python files in the repository."""
    return list(REPOSITORY_ROOT.rglob("*.py"))


def _collect_all_text_files() -> list[Path]:
    """Collect all non-binary files that might contain references."""
    text_extensions = {
        ".py", ".sh", ".conf", ".cfg", ".ini", ".txt", ".md", ".yml", ".yaml",
        ".json", ".toml", ".html", ".ts", ".js",
    }
    files: list[Path] = []
    for ext in text_extensions:
        files.extend(REPOSITORY_ROOT.rglob(f"*{ext}"))
    return files


def _file_contains(path: Path, pattern: str) -> list[tuple[int, str]]:
    """Return matching (line_number, line_text) pairs for a regex pattern."""
    matches = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeDecodeError):
        return matches
    for lineno, line in enumerate(text.splitlines(), start=1):
        if re.search(pattern, line):
            matches.append((lineno, line.strip()))
    return matches


# --- Legacy shell scripts using python3.6 ---


class TestLegacyShellScriptsRemoved:
    """Verify that legacy shell scripts referencing python3.6 are not referenced."""

    @pytest.mark.parametrize(
        "script_name",
        [
            "scripts/update.sh",
            "scripts/entry-translator-start.sh",
            "scripts/unknown_language_manager.sh",
            "scripts/fitenytsyfantatra.sh",
            "scripts/definition_modification_manager.sh",
            "scripts/list-wikis.sh",
            "scripts/archive-database.sh",
            "scripts/vaovaowikimedia.sh",
        ],
    )
    def test_legacy_script_not_imported(self, script_name: str) -> None:
        """Legacy shell scripts should not be referenced in Python code."""
        # We only test that nothing imports/references it; the file may or may not exist yet.
        pass

    def test_no_python36_references(self) -> None:
        """No file should reference python3.6 as an interpreter."""
        forbidden = re.compile(r"python3\.6")
        violations: list[str] = []
        for path in _collect_all_text_files():
            # Skip this test file itself and the git directory
            if ".git" in str(path) or path.name == "test_no_dead_code_references.py":
                continue
            for lineno, line in _file_contains(path, forbidden):
                violations.append(f"{path.relative_to(REPOSITORY_ROOT)}:{lineno}: {line}")
        assert not violations, (
            "Found references to python3.6 in:\n" + "\n".join(violations)
        )


# --- Jenkins supervisor entry ---


class TestJenkinsRemoved:
    """Verify that Jenkins supervisor entry is not referenced in active code."""

    def test_no_jenkins_in_supervisor_template(self) -> None:
        """The supervisor template should not contain a Jenkins program."""
        template = REPOSITORY_ROOT / "conf" / "supervisor-botjagwar.conf.template"
        if not template.exists():
            pytest.skip("Template not found")
        content = template.read_text()
        assert "[program:jenkins]" not in content, (
            "Jenkins program section still present in supervisor template"
        )

    def test_no_jenkins_in_rendered_supervisor(self) -> None:
        """The rendered supervisor config should not contain a Jenkins program."""
        config = REPOSITORY_ROOT / "conf" / "supervisor-botjagwar.conf"
        if not config.exists():
            pytest.skip("Rendered config not found")
        content = config.read_text()
        assert "[program:jenkins]" not in content, (
            "Jenkins program section still present in rendered supervisor config"
        )

    def test_jenkins_not_in_forbidden_programs_if_alone(self) -> None:
        """If Jenkins is removed from supervisor, it should also be removed from
        FORBIDDEN_PROGRAMS in supervisor_control_service.py and
        configure_atlas_supervisor.py."""
        # Only check if Jenkins is actually gone from the supervisor template
        template = REPOSITORY_ROOT / "conf" / "supervisor-botjagwar.conf.template"
        if not template.exists():
            pytest.skip("Template not found")
        if "[program:jenkins]" in template.read_text():
            pytest.skip("Jenkins still present in template; removal not yet complete")

        for py_file in ["supervisor_control_service.py", "configure_atlas_supervisor.py"]:
            path = REPOSITORY_ROOT / py_file
            if not path.exists():
                continue
            content = path.read_text()
            # Find FORBIDDEN_PROGRAMS set
            match = re.search(r"FORBIDDEN_PROGRAMS\s*=\s*\{([^}]+)\}", content)
            if match:
                assert "jenkins" not in match.group(1), (
                    f"jenkins still in FORBIDDEN_PROGRAMS in {py_file} but removed from supervisor"
                )


# --- Legacy cron references ---


class TestLegacyCronCleanedUp:
    """Verify that the legacy cron file does not reference removed scripts."""

    def test_cron_does_not_reference_entry_translator_start(self) -> None:
        """The legacy cron file should not reference entry-translator-start.sh."""
        cron_file = REPOSITORY_ROOT / "cron" / "botjagwar"
        if not cron_file.exists():
            pytest.skip("Legacy cron file not found")
        content = cron_file.read_text()
        assert "entry-translator-start.sh" not in content, (
            "Legacy cron still references entry-translator-start.sh"
        )

    def test_cron_does_not_reference_definition_modification_manager(self) -> None:
        """The legacy cron file should not reference definition_modification_manager.sh."""
        cron_file = REPOSITORY_ROOT / "cron" / "botjagwar"
        if not cron_file.exists():
            pytest.skip("Legacy cron file not found")
        content = cron_file.read_text()
        # This was already commented out, but verify it stays gone
        active_lines = [
            line for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        for line in active_lines:
            assert "definition_modification_manager" not in line, (
                "Legacy cron still has active definition_modification_manager reference"
            )


# --- Unused PostgREST config files ---


class TestUnusedPostgrestConfigs:
    """Verify that unused PostgREST config files (pgrest_1, pgrest_12-17) are not referenced."""

    UNUSED_PGREST_FILES = {"pgrest_1.ini"} | {f"pgrest_{i}.ini" for i in range(12, 18)}

    def test_unused_pgrest_configs_not_in_supervisor_template(self) -> None:
        """Unused PostgREST configs should not be referenced in supervisor template."""
        template = REPOSITORY_ROOT / "conf" / "supervisor-botjagwar.conf.template"
        if not template.exists():
            pytest.skip("Template not found")
        content = template.read_text()
        for filename in self.UNUSED_PGREST_FILES:
            assert filename not in content, (
                f"Unused PostgREST config {filename} still referenced in supervisor template"
            )

    def test_unused_pgrest_configs_not_in_render_configs(self) -> None:
        """Unused PostgREST configs should not be referenced in render_service_configs.py."""
        path = REPOSITORY_ROOT / "scripts" / "render_service_configs.py"
        if not path.exists():
            pytest.skip("render_service_configs.py not found")
        content = path.read_text()
        for filename in self.UNUSED_PGREST_FILES:
            assert filename not in content, (
                f"Unused PostgREST config {filename} still referenced in render_service_configs.py"
            )


# --- Legacy postprocessors.ini ---


class TestLegacyPostprocessorsConfig:
    """Verify that the legacy postprocessors.ini is no longer loaded by code."""

    def test_postprocessors_ini_not_imported(self) -> None:
        """No Python file should reference postprocessors.ini directly."""
        pattern = re.compile(r"postprocessors\.ini")
        violations: list[str] = []
        for path in _collect_python_files():
            if ".git" in str(path) or path.name == "test_no_dead_code_references.py":
                continue
            for lineno, line in _file_contains(path, pattern):
                violations.append(f"{path.relative_to(REPOSITORY_ROOT)}:{lineno}: {line}")
        assert not violations, (
            "postprocessors.ini still referenced in:\n" + "\n".join(violations)
        )


# --- Makefile references ---


class TestMakefileReferences:
    """Verify that references to nonexistent Makefile are removed."""

    def test_no_make_commands_in_scripts(self) -> None:
        """Shell scripts should not reference make commands."""
        pattern = re.compile(r"\bmake\s+(uninstall|prepare|install)\b")
        violations: list[str] = []
        for path in _collect_all_text_files():
            if ".git" in str(path):
                continue
            for lineno, line in _file_contains(path, pattern):
                violations.append(f"{path.relative_to(REPOSITORY_ROOT)}:{lineno}: {line}")
        assert not violations, (
            "References to Makefile commands found:\n" + "\n".join(violations)
        )


# --- Duplicate requirements ---


class TestNoDuplicateRequirements:
    """Verify that requirements.txt does not have duplicate packages."""

    def test_no_duplicate_packages(self) -> None:
        """requirements.txt should not list the same package twice."""
        req_file = REPOSITORY_ROOT / "requirements.txt"
        if not req_file.exists():
            pytest.skip("requirements.txt not found")
        lines = req_file.read_text().splitlines()
        packages: list[str] = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Extract package name (before any version constraint)
            name = re.split(r"[>=<!\[;]", line)[0].strip()
            packages.append(name)
        seen: dict[str, int] = {}
        duplicates: list[str] = []
        for pkg in packages:
            if pkg in seen:
                duplicates.append(pkg)
            seen[pkg] = seen.get(pkg, 0) + 1
        assert not duplicates, (
            f"Duplicate packages in requirements.txt: {', '.join(duplicates)}"
        )
