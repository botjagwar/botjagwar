import subprocess
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, call

import pytest

import configure_atlas_supervisor as configurator
from configure_atlas_supervisor import (
    Configuration,
    build_parser,
    build_remote_script,
    encoded,
    render_atlas_section,
    render_nginx_location,
    render_supervisor_listener,
    replace_atlas_section,
    replace_hosts_entry,
    validated_atlas_content,
    validated_configuration,
)
from supervisor_control_service import load_hosts


def configuration_arguments(*arguments: str) -> list[str]:
    """Return the required command-line arguments with optional overrides."""
    return [
        "--host",
        "dictionary",
        "--label",
        "Dictionary backend",
        "--address",
        "192.0.2.10",
        "--hostname",
        "dictionary.example.com",
        "--atlas-source",
        "192.0.2.20",
        "--program",
        "dictionary_service_1",
        *arguments,
    ]


def make_configuration(*arguments: str) -> Configuration:
    """Build a valid test configuration with optional extra arguments."""
    parser = build_parser()
    return validated_configuration(parser.parse_args(configuration_arguments(*arguments)))


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (("--label", "  "), "host label"),
        (("--address", "not-an-address"), "--address"),
        (("--ssh-target=-unsafe",), "SSH target"),
        (("--remote-nginx-config", "relative/nginx.conf"), "Remote configuration paths"),
    ],
)
def test_configuration_rejects_invalid_values(arguments: tuple[str, ...], message: str) -> None:
    """Validation rejects unsafe values before remote or privileged work starts."""
    with pytest.raises(ValueError, match=message):
        make_configuration(*arguments)


def test_configuration_rejects_forbidden_program() -> None:
    """The configurator applies the same privileged-program boundary as Atlas."""
    with pytest.raises(ValueError, match="cannot be controlled"):
        make_configuration("--program", "load_balancer")


def test_generated_configuration_uses_parameters_and_loopback_rpc() -> None:
    """Remote output restricts RPC while the Atlas section uses the public TLS endpoint."""
    config = make_configuration()

    remote_script = build_remote_script(config, "fresh-random-password")
    atlas_section = render_atlas_section(config, "fresh-random-password")
    supervisor_payload = encoded(render_supervisor_listener(config.username, "fresh-random-password"))
    nginx_payload = encoded(render_nginx_location(config.atlas_source))

    assert supervisor_payload in remote_script
    assert nginx_payload in remote_script
    assert "https://dictionary.example.com:38000/RPC2" in atlas_section
    assert "fresh-random-password" not in remote_script
    assert "/etc/botjagwar/supervisor-rpc-location.conf" in remote_script
    assert "/opt/botjagwar/current/frontend/config/nginx/supervisor-rpc-location.conf" in remote_script


def test_configure_remote_builds_ssh_command(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remote setup passes options as argv and the generated script over standard input."""
    config = make_configuration(
        "--ssh-target",
        "operator@dictionary.example.com",
        "--ssh-option",
        "BatchMode=yes",
        "--ssh-option",
        "IdentityFile=/tmp/test-key",
    )
    run = MagicMock()
    monkeypatch.setattr(configurator.subprocess, "run", run)

    configurator.configure_remote(config, "remote-password")

    run.assert_called_once_with(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "IdentityFile=/tmp/test-key",
            "operator@dictionary.example.com",
            "sudo",
            "-n",
            "bash",
            "-s",
        ],
        input=build_remote_script(config, "remote-password"),
        text=True,
        check=True,
    )


def test_configure_remote_converts_subprocess_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """SSH failures become an actionable error without exposing subprocess details."""
    failure = subprocess.CalledProcessError(1, ["ssh"])
    monkeypatch.setattr(configurator.subprocess, "run", MagicMock(side_effect=failure))

    with pytest.raises(RuntimeError, match="non-interactive sudo access") as error:
        configurator.configure_remote(make_configuration(), "remote-password")

    assert error.value.__cause__ is None


def test_atlas_section_replacement_is_idempotent_and_preserves_other_hosts(tmp_path: Path) -> None:
    """Rerunning replaces only the selected host section and leaves other hosts intact."""
    config = make_configuration()
    existing = (
        "[host:dictionary]\nurl = https://old.example/RPC2\n\n"
        "[host:translator]\n"
        "url = https://translator.example/RPC2\n"
        "username = atlas-control\n"
        "password = translator-password\n"
        "programs = entry_translator_1\n"
    )

    once = replace_atlas_section(existing, config.host_id, render_atlas_section(config, "first-password"))
    twice = replace_atlas_section(once, config.host_id, render_atlas_section(config, "second-password"))
    path = tmp_path / "supervisor.ini"
    path.write_text(validated_atlas_content(config, "second-password", twice), encoding="utf-8")

    assert twice.count("[host:dictionary]") == 1
    assert "first-password" not in twice
    assert "second-password" in twice
    assert "[host:translator]" in twice
    assert load_hosts(path)["dictionary"].programs == ("dictionary_service_1",)


def test_hosts_entry_replacement_is_idempotent() -> None:
    """The private hostname mapping is updated without accumulating stale entries."""
    original = "127.0.0.1 localhost\n192.0.2.9 dictionary.example.com # botjagwar-atlas-supervisor:dictionary\n"

    once = replace_hosts_entry(original, "dictionary", "192.0.2.10", "dictionary.example.com")
    twice = replace_hosts_entry(once, "dictionary", "192.0.2.10", "dictionary.example.com")

    assert once == twice
    assert "192.0.2.9" not in twice
    assert twice.count("dictionary.example.com") == 1


def test_install_local_file_updates_writable_existing_file(tmp_path: Path) -> None:
    """A writable existing file is updated in place with its requested mode."""
    path = tmp_path / "existing.ini"
    path.write_text("old", encoding="utf-8")

    configurator.install_local_file(path, "new content", 0o600, (0, 0))

    assert path.read_text(encoding="utf-8") == "new content"
    assert path.stat().st_mode & 0o777 == 0o600


def test_install_local_file_atomically_creates_file_in_writable_directory(tmp_path: Path) -> None:
    """A new local file is atomically installed when its parent is writable."""
    path = tmp_path / "new.ini"

    configurator.install_local_file(path, "new content", 0o640, (0, 0))

    assert path.read_text(encoding="utf-8") == "new content"
    assert path.stat().st_mode & 0o777 == 0o640


def test_validate_remote_accepts_all_configured_programs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remote validation accepts a reachable Supervisor containing every allowlisted program."""
    client = MagicMock()
    client.getAllProcessInfo.return_value = [{"name": "dictionary_service_1"}, {"name": "unmanaged"}]
    factory = MagicMock(return_value=client)
    monkeypatch.setattr(configurator, "create_supervisor_client", factory)
    config = make_configuration()

    configurator.validate_remote(config, "remote-password")

    host = factory.call_args.args[0]
    assert (host.identifier, host.url, host.password, host.programs) == (
        "dictionary",
        config.url,
        "remote-password",
        ("dictionary_service_1",),
    )


def test_validate_remote_converts_client_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Connection and protocol failures are converted to remote validation guidance."""
    client = MagicMock()
    client.getAllProcessInfo.side_effect = OSError("offline")
    monkeypatch.setattr(configurator, "create_supervisor_client", MagicMock(return_value=client))

    with pytest.raises(RuntimeError, match="Verify DNS, certificate trust") as error:
        configurator.validate_remote(make_configuration(), "remote-password")

    assert error.value.__cause__ is None


def test_validate_remote_reports_missing_programs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validation reports the configured programs absent from remote Supervisor."""
    client = MagicMock()
    client.getAllProcessInfo.return_value = []
    monkeypatch.setattr(configurator, "create_supervisor_client", MagicMock(return_value=client))

    with pytest.raises(RuntimeError, match="dictionary_service_1"):
        configurator.validate_remote(make_configuration(), "remote-password")


def test_configure_orchestrates_remote_and_local_installation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Configuration validates the remote endpoint before registering and restarting Atlas."""
    hosts_file = tmp_path / "hosts"
    hosts_file.write_text("127.0.0.1 localhost\n", encoding="utf-8")
    atlas_config = tmp_path / "supervisor.ini"
    atlas_config.write_text("[host:other]\nprograms = other_service\n", encoding="utf-8")
    config = replace(make_configuration(), hosts_file=hosts_file, atlas_config=atlas_config)
    configure_remote = MagicMock()
    install_local_file = MagicMock()
    validate_remote = MagicMock()
    validate_atlas = MagicMock(return_value="updated atlas config")
    run = MagicMock()
    monkeypatch.setattr(configurator, "generate_password", lambda: "generated-password")
    monkeypatch.setattr(configurator, "configure_remote", configure_remote)
    monkeypatch.setattr(configurator, "install_local_file", install_local_file)
    monkeypatch.setattr(configurator, "validate_remote", validate_remote)
    monkeypatch.setattr(configurator, "validated_atlas_content", validate_atlas)
    monkeypatch.setattr(configurator.subprocess, "run", run)

    configurator.configure(config)

    configure_remote.assert_called_once_with(config, "generated-password")
    validate_remote.assert_called_once_with(config, "generated-password")
    install_local_file.assert_has_calls(
        [
            call(
                hosts_file,
                "127.0.0.1 localhost\n192.0.2.10 dictionary.example.com "
                "# botjagwar-atlas-supervisor:dictionary\n",
                0o644,
                (0, 0),
            ),
            call(atlas_config, "updated atlas config", 0o600, (configurator.os.getuid(), configurator.os.getgid())),
        ]
    )
    validate_atlas.assert_called_once_with(
        config,
        "generated-password",
        "[host:other]\nprograms = other_service\n",
    )
    run.assert_called_once_with(
        ["sudo", "supervisorctl", "restart", "supervisor_control_service"],
        check=True,
    )
    assert "Configured Atlas Supervisor host dictionary" in capsys.readouterr().out


def test_main_runs_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    """The command entry point validates arguments and invokes orchestration."""
    configure = MagicMock()
    monkeypatch.setattr(configurator, "configure", configure)

    result = configurator.main(configuration_arguments("--skip-gateway-restart"))

    assert result == 0
    assert configure.call_args.args[0].skip_gateway_restart is True


def test_main_reports_validation_error(capsys: pytest.CaptureFixture[str]) -> None:
    """Expected command errors are printed to stderr and return a failure status."""
    result = configurator.main(configuration_arguments("--address", "invalid"))

    assert result == 1
    assert "Error: --address must be an IPv4 or IPv6 address." in capsys.readouterr().err


def test_setup_tls_accepts_help_and_rejects_invalid_domain() -> None:
    """The TLS script exposes the domain argument and validates it before privileged work."""
    script = Path(__file__).parents[2] / "frontend" / "setup-tls.sh"

    help_result = subprocess.run(["bash", str(script), "--help"], text=True, capture_output=True, check=False)
    invalid_result = subprocess.run(
        ["bash", str(script), "--domain", "not_a_hostname"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert help_result.returncode == 0
    assert "--domain DOMAIN" in help_result.stdout
    assert "ATLAS_DOMAIN" in help_result.stdout
    assert invalid_result.returncode == 2
    assert "not a valid DNS hostname" in invalid_result.stderr
