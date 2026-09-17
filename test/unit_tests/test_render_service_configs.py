import re
from pathlib import Path

import pytest

from scripts.deployment_config import DEFAULT_INSTANCE_COUNTS, configured_instance_counts, instance_counts
from scripts.render_service_configs import render_configurations, render_template


REPOSITORY_ROOT = Path(__file__).parents[2]


def program_names(content: str, prefix: str) -> list[str]:
    """Return generated Supervisor program names with the requested prefix."""
    return re.findall(rf"^\[program:({re.escape(prefix)}_\d+)]$", content, re.MULTILINE)


def server_ports(content: str, prefix: str) -> list[int]:
    """Return generated HAProxy ports for one backend server prefix."""
    return [
        int(port)
        for port in re.findall(rf"^server {re.escape(prefix)}\d+ 127\.0\.0\.1:(\d+) check$", content, re.MULTILINE)
    ]


def test_default_configurations_have_consistent_instance_pools(tmp_path: Path) -> None:
    """Default Supervisor processes and HAProxy servers use the same counts and ports."""
    render_configurations(REPOSITORY_ROOT / "conf", tmp_path, DEFAULT_INSTANCE_COUNTS, "botjagwar", True)

    supervisor = (tmp_path / "supervisor-botjagwar.conf").read_text(encoding="utf-8")
    ctranslate = (tmp_path / "supervisor-ctranslate.conf").read_text(encoding="utf-8")
    haproxy = (tmp_path / "haproxy.cfg").read_text(encoding="utf-8")

    assert program_names(supervisor, "dictionary_service") == [
        f"dictionary_service_{index}" for index in range(1, 7)
    ]
    assert program_names(supervisor, "entry_translator") == [f"entry_translator_{index}" for index in range(1, 11)]
    assert program_names(supervisor, "postgrest") == [f"postgrest_{index}" for index in range(2, 12)]
    assert supervisor.count("[program:tenymalagasy_mirror]") == 1
    assert supervisor.count("[program:english_wiktionary_cache_irc]") == 1
    assert supervisor.count(
        'BOTJAGWAR_CONFIG="/etc/botjagwar/config.ini"'
    ) == 21
    mirror_section = supervisor.split("[program:tenymalagasy_mirror]", maxsplit=1)[1].split("\n[", maxsplit=1)[0]
    assert "--database /var/lib/botjagwar/user_data/tenymalagasy_mirror.sqlite3" in mirror_section
    assert "autorestart=true" in mirror_section
    cache_section = supervisor.split(
        "[program:english_wiktionary_cache_irc]", maxsplit=1
    )[1].split("\n[", maxsplit=1)[0]
    assert "english_wiktionary_cache_irc.py" in cache_section
    assert "autorestart=true" in cache_section
    assert program_names(ctranslate, "translator") == [f"translator_{index}" for index in range(1, 4)]
    assert server_ports(haproxy, "dictionary") == list(range(28001, 28007))
    assert server_ports(haproxy, "entry_translator") == list(range(18001, 18011))
    assert server_ports(haproxy, "pgrest") == list(range(8101, 8111))
    assert server_ports(haproxy, "translator") == list(range(8886, 8889))
    assert "bind 0.0.0.0:" not in haproxy
    assert haproxy.count("bind 127.0.0.1:") == 4

    pgrest_dir = tmp_path / "pgrest"
    assert pgrest_dir.is_dir()
    for index in range(2, 12):
        pgrest_file = pgrest_dir / f"pgrest_{index}.ini"
        assert pgrest_file.is_file(), f"Missing PostgREST config: {pgrest_file}"
        content = pgrest_file.read_text(encoding="utf-8")
        assert f"server-port = {8100 + index - 1}" in content
        assert "db-uri" in content


def test_checked_in_supervisor_config_matches_default_render(tmp_path: Path) -> None:
    """Keep the operator-facing generated example synchronized with its template."""
    render_configurations(
        REPOSITORY_ROOT / "conf",
        tmp_path,
        DEFAULT_INSTANCE_COUNTS,
        "user",
        True,
    )

    assert (REPOSITORY_ROOT / "conf/supervisor-botjagwar.conf").read_text(
        encoding="utf-8"
    ) == (tmp_path / "supervisor-botjagwar.conf").read_text(encoding="utf-8")


def test_custom_counts_and_no_autostart_apply_to_every_instance(tmp_path: Path) -> None:
    """Custom pool sizes stay aligned and NO_AUTOSTART disables generated programs."""
    counts = instance_counts(
        {
            "DICTIONARY_SERVICE_INSTANCES": "2",
            "ENTRY_TRANSLATOR_INSTANCES": "3",
            "POSTGREST_INSTANCES": "4",
            "TRANSLATOR_INSTANCES": "4",
        }
    )
    render_configurations(REPOSITORY_ROOT / "conf", tmp_path, counts, "botjagwar", False)

    supervisor = (tmp_path / "supervisor-botjagwar.conf").read_text(encoding="utf-8")
    ctranslate = (tmp_path / "supervisor-ctranslate.conf").read_text(encoding="utf-8")
    haproxy = (tmp_path / "haproxy.cfg").read_text(encoding="utf-8")

    assert len(program_names(supervisor, "dictionary_service")) == 2
    assert len(program_names(supervisor, "entry_translator")) == 3
    assert len(program_names(supervisor, "postgrest")) == 4
    assert len(program_names(ctranslate, "translator")) == 4
    assert supervisor.count("autostart=false") == 2 + 3 + 4
    assert ctranslate.count("autostart=false") == 4
    assert server_ports(haproxy, "dictionary") == [28001, 28002]
    assert server_ports(haproxy, "entry_translator") == [18001, 18002, 18003]
    assert server_ports(haproxy, "pgrest") == [8101, 8102, 8103, 8104]
    assert server_ports(haproxy, "translator") == [8886, 8887, 8888, 8889]

    pgrest_dir = tmp_path / "pgrest"
    assert pgrest_dir.is_dir()
    pgrest_files = sorted(pgrest_dir.glob("pgrest_*.ini"))
    assert len(pgrest_files) == 4
    assert [f.name for f in pgrest_files] == [
        "pgrest_2.ini", "pgrest_3.ini", "pgrest_4.ini", "pgrest_5.ini"
    ]


def test_existing_supervisor_counts_survive_without_environment_override(tmp_path: Path) -> None:
    """Reinstall keeps deployed pool sizes unless an operator explicitly changes them."""
    supervisor = tmp_path / "supervisor.conf"
    supervisor.write_text(
        "\n".join(
            [
                "[program:dictionary_service_1]",
                "[program:dictionary_service_8]",
                "[program:entry_translator_12]",
                "[program:postgrest_2]",
                "[program:postgrest_17]",
                "[program:translator_4]",
            ]
        ),
        encoding="utf-8",
    )

    existing = configured_instance_counts([supervisor])

    assert instance_counts({}, existing) == {
        "dictionary_service": 8,
        "entry_translator": 12,
        "postgrest": 16,
        "translator": 4,
    }
    assert instance_counts({"DICTIONARY_SERVICE_INSTANCES": "3"}, existing)["dictionary_service"] == 3


@pytest.mark.parametrize(
    ("variable", "value"),
    [("DICTIONARY_SERVICE_INSTANCES", "0"), ("ENTRY_TRANSLATOR_INSTANCES", "many"), ("POSTGREST_INSTANCES", "17")],
)
def test_invalid_instance_counts_are_rejected(variable: str, value: str) -> None:
    """Invalid environment settings fail instead of producing partial configurations."""
    with pytest.raises(ValueError, match=variable):
        instance_counts({variable: value})


def test_runtime_paths_and_network_policy_are_rendered_from_deployment_roots(tmp_path: Path) -> None:
    """Generated services separate immutable code from configuration and writable state."""
    render_configurations(
        REPOSITORY_ROOT / "conf",
        tmp_path,
        DEFAULT_INSTANCE_COUNTS,
        "botjagwar",
        True,
        Path("/srv/botjagwar/current"),
        Path("/etc/botjagwar"),
        Path("/var/lib/botjagwar"),
        Path("/srv/botjagwar/current/frontend"),
        "192.0.2.10",
        ("192.0.2.20/32",),
    )

    supervisor = (tmp_path / "supervisor-botjagwar.conf").read_text(encoding="utf-8")
    haproxy = (tmp_path / "haproxy.cfg").read_text(encoding="utf-8")

    assert "/srv/botjagwar/current/pyenv/bin/python" in supervisor
    assert 'BOTJAGWAR_CONFIG="/etc/botjagwar/config.ini"' in supervisor
    assert "/etc/botjagwar/pgrest/pgrest_2.ini" in supervisor
    assert "/var/lib/botjagwar/user_data/" in supervisor
    assert (
        "command=/srv/botjagwar/current/pyenv/bin/python "
        "/srv/botjagwar/current/tenymalagasy_mirror.py "
        "--database /var/lib/botjagwar/user_data/tenymalagasy_mirror.sqlite3"
    ) in supervisor
    assert "/srv/botjagwar/pyenv" not in supervisor
    assert haproxy.count("bind 192.0.2.10:") == 4
    assert haproxy.count("acl atlas_backend_source src 192.0.2.20/32") == 4
    assert haproxy.count("192.0.2.20/32 127.0.0.0/8 ::1/128") == 4
    assert haproxy.count("http-request deny if !atlas_backend_source") == 4


def test_template_substitution_is_single_pass(tmp_path: Path) -> None:
    """A marker inside another marker's value is never substituted a second time."""
    template = tmp_path / "template.conf"
    template.write_text("a={{A}} b={{B}}\n", encoding="utf-8")

    rendered = render_template(template, {"A": "x{{B}}y", "B": "z"})

    assert rendered == "a=x{{B}}y b=z\n"


def test_template_rejects_unknown_and_malformed_markers(tmp_path: Path) -> None:
    """Unknown placeholders and stray braces fail instead of rendering silently."""
    unknown = tmp_path / "unknown.conf"
    unknown.write_text("value={{KNOWN}} stray={{UNKNOWN}}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="UNKNOWN"):
        render_template(unknown, {"KNOWN": "ok"})

    malformed = tmp_path / "malformed.conf"
    malformed.write_text("value={{MARKER\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Malformed"):
        render_template(malformed, {"MARKER": "ok"})
