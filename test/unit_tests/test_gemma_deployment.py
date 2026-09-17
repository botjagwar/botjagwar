"""Focused contracts for standalone Gemma rendering and installation."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from scripts.render_service_configs import main, render_gemma_configuration


ROOT = Path(__file__).parents[2]


def test_gemma_renderer_creates_one_standalone_service(tmp_path: Path) -> None:
    """Gemma rendering produces one process without HAProxy or root service output."""
    render_gemma_configuration(ROOT / "conf", tmp_path, "gemma-user", False, Path("/srv/gemma"))

    content = (tmp_path / "supervisor-gemma.conf").read_text(encoding="utf-8")
    assert content.count("[program:gemma]") == 1
    assert (
        "/srv/gemma/venv/bin/python /srv/gemma/gemma_service.py "
        "--model-path /srv/gemma/model/model.gguf"
    ) in content
    assert "user=gemma-user" in content
    assert "autostart=false" in content
    assert not (tmp_path / "haproxy.cfg").exists()
    assert not (tmp_path / "supervisor-botjagwar.conf").exists()


def test_gemma_only_cli_does_not_resolve_shared_deployment(tmp_path: Path, monkeypatch: object) -> None:
    """The standalone render path is independent from shared instance configuration."""
    monkeypatch.setenv("TRANSLATOR_INSTANCES", "invalid")  # type: ignore[attr-defined]
    result = main(
        [
            "--gemma-only",
            "--template-dir",
            str(ROOT / "conf"),
            "--output-dir",
            str(tmp_path),
            "--gemma-root",
            "/opt/gemma",
        ]
    )

    assert result == 0
    assert (tmp_path / "supervisor-gemma.conf").is_file()


def _write_fake_model(path: Path) -> None:
    """Create the local GGUF file accepted by the installer."""
    path.parent.mkdir()
    path.write_bytes(b"GGUF offline-test")


def test_test_install_stages_default_local_model_outside_production(tmp_path: Path) -> None:
    """TEST installation copies the default source without Supervisor or production writes."""
    source = tmp_path / "gemma-4-E2B-it-GGUF" / "gemma-4-E2B-it-Q4_K_M.gguf"
    destination = tmp_path / "installed-gemma"
    _write_fake_model(source)
    environment = {
        **os.environ,
        "HOME": str(tmp_path),
        "TEST": "1",
        "GEMMA_INSTALL_DIR": str(destination),
        "GEMMA_SKIP_DEPENDENCIES": "1",
    }

    result = subprocess.run(
        ["bash", str(ROOT / "install-gemma.sh")],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert (destination / "model" / "model.gguf").is_file()
    assert (destination / "gemma_service.py").is_file()
    assert (destination / "venv" / "bin" / "python").is_file()


def test_invalid_source_does_not_replace_existing_deployment(tmp_path: Path) -> None:
    """Source validation completes before an old deployment can be replaced."""
    source = tmp_path / "gemma-4-E2B-it-GGUF" / "missing.gguf"
    destination = tmp_path / "installed-gemma"
    source.parent.mkdir()
    destination.mkdir()
    sentinel = destination / "keep-me"
    sentinel.write_text("old deployment", encoding="utf-8")

    result = subprocess.run(
        ["bash", str(ROOT / "install-gemma.sh")],
        cwd=ROOT,
        env={
            **os.environ,
            "TEST": "1",
            "GEMMA_SOURCE_DIR": str(source),
            "GEMMA_INSTALL_DIR": str(destination),
            "GEMMA_SKIP_DEPENDENCIES": "1",
        },
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert sentinel.read_text(encoding="utf-8") == "old deployment"


def test_test_install_refuses_production_destination(tmp_path: Path) -> None:
    """TEST mode exits before inspecting or writing the production deployment."""
    result = subprocess.run(
        ["bash", str(ROOT / "install-gemma.sh")],
        cwd=ROOT,
        env={
            **os.environ,
            "TEST": "1",
            "GEMMA_SOURCE_DIR": str(tmp_path / "missing-source"),
            "GEMMA_INSTALL_DIR": "/opt/gemma/test-child",
            "GEMMA_SKIP_DEPENDENCIES": "1",
        },
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "outside /opt/gemma" in result.stderr
