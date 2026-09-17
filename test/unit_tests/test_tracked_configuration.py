"""Repository hygiene tests for checked-in configuration examples."""

import re
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).parents[2]
CREDENTIAL_URI = re.compile(r'^[^#\n]*://[^/\s:"]+:[^/@\s"]+@', re.MULTILINE)


def test_postgrest_template_does_not_contain_passwords() -> None:
    """Keep database passwords out of the checked-in PostgREST template."""
    template_path = REPOSITORY_ROOT / "conf/pgrest/pgrest.ini.template"
    config = template_path.read_text(encoding="utf-8")
    assert not CREDENTIAL_URI.search(config), template_path
    assert 'server-host = "127.0.0.1"' in config, template_path
    assert "{{SERVER_PORT}}" in config, template_path


def test_runtime_configuration_is_ignored() -> None:
    """Keep machine-specific credentials out of future commits."""
    ignored_paths = (REPOSITORY_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()

    assert "/conf/config.ini" in ignored_paths
    assert "pywikibot.lwp" in ignored_paths


def test_queue_scripts_do_not_print_rabbitmq_credentials() -> None:
    """Prevent legacy utility output from disclosing broker credentials."""
    for filename in ("add_to_edit_queue.py", "delete_unmatched.py"):
        script = (REPOSITORY_ROOT / filename).read_text(encoding="utf-8")

        assert "RABBITMQ_PASSWORD}" not in script
        assert "RABBITMQ_USERNAME}" not in script
