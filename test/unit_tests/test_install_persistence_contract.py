"""Contracts for state-preserving Botjagwar reinstalls."""

from pathlib import Path


ROOT = Path(__file__).parents[2]
REMOTE_STATISTICS_CONDITION = 'if [[ -n ${BOTJAGWAR_DASHBOARD_STATISTICS_SOURCE:-} ]]'


def test_root_install_stages_then_atomically_activates_a_versioned_release() -> None:
    """A candidate is validated before current changes and can be rolled back."""
    script = (ROOT / "install.sh").read_text(encoding="utf-8")

    activation_position = script.index('activate "$release_id"')
    assert script.index('release_dir="$releases_dir/$release_id"') < activation_position
    assert script.index('staging_dir="$release_dir"') < activation_position
    assert script.index("compileall") < activation_position
    assert script.index("haproxy -c") < activation_position
    assert 'rollback "$previous_release"' in script
    assert 'sudo rm -rf "$opt_dir"' not in script


def test_root_install_separates_release_config_and_state() -> None:
    """Machine configuration and writable state are linked outside releases."""
    script = (ROOT / "install.sh").read_text(encoding="utf-8")

    assert 'config_dir=${BOTJAGWAR_CONFIG_DIR:-/etc/botjagwar}' in script
    assert 'state_dir=${BOTJAGWAR_STATE_DIR:-/var/lib/botjagwar}' in script
    assert 'ln -s "$config_dir/config.ini" "$staging_dir/conf/config.ini"' in script
    assert 'ln -s "$state_dir/user_data" "$staging_dir/user_data"' in script
    assert 'install -m 0644 "$src_dir/user_data/basic_english.txt" "$state_dir/user_data/basic_english.txt"' in script
    assert 'config_candidates+=("$src_dir/conf/test_config.ini")' in script
    assert 'cp -R "$src_dir/api" "$src_dir/conf"' not in script
    assert '[[ ${conf_entry##*/} != config.ini ]]' in script
    assert 'sudo chmod 0600 "$config_dir/config.ini"' in script
    assert 'sudo chown "$current_user:$current_group" "$config_dir/config.ini"' in script
    assert "deployment.ini" in script


def test_root_install_stages_local_or_remote_dashboard_snapshot_before_completion() -> None:
    """Production releases validate the dashboard data source that they actually manage."""
    script = (ROOT / "install.sh").read_text(encoding="utf-8")

    validation_branches = script.split(REMOTE_STATISTICS_CONDITION, maxsplit=1)[1].split(
        "\n  fi", maxsplit=1
    )[0]
    remote_branch, local_branch = validation_branches.split("\n  else", maxsplit=1)
    assert "scripts/fetch_dashboard_statistics.py" in remote_branch
    assert "scripts/refresh_dashboard_statistics.py" not in remote_branch
    assert "scripts/snapshot_page_check_statistics.py" not in remote_branch
    assert "scripts/refresh_dashboard_statistics.py" in local_branch
    assert "scripts/snapshot_page_check_statistics.py" in local_branch
    assert "--check-storage" in local_branch

    refresh_position = script.index(
        '"$staging_dir/pyenv/bin/python" "$staging_dir/scripts/refresh_dashboard_statistics.py"'
    )
    assert script.rindex('if [[ -z ${TEST:-} ]]', 0, refresh_position) < refresh_position
    assert refresh_position < script.index('touch "$release_dir/.release-complete"')
    assert 'BOTJAGWAR_CONFIG="$config_dir/config.ini"' in script
    assert 'BOTJAGWAR_ATLAS_STATE_DIR="$state_dir/atlas"' in script
    storage_check_position = script.index(
        '"$staging_dir/scripts/snapshot_page_check_statistics.py"'
    )
    release_complete_position = script.index('touch "$release_dir/.release-complete"')
    assert script.index("--check-storage", storage_check_position) < release_complete_position
    assert storage_check_position < release_complete_position


def test_wiktionary_irc_is_an_automatic_managed_service() -> None:
    """Supervisor and release lifecycle management always include the IRC listener."""
    for filename in ("supervisor-botjagwar.conf.template", "supervisor-botjagwar.conf"):
        content = (ROOT / "conf" / filename).read_text(encoding="utf-8")
        section = content.split("[program:wiktionary_irc]", maxsplit=1)[1].split("\n[", maxsplit=1)[0]
        assert "autostart=true" in section
        assert "autorestart=true" in section

    script = (ROOT / "install.sh").read_text(encoding="utf-8")
    assert "wiktionary_irc) ;;" not in script
    assert 'managed_programs+=("$program")' in script
    assert 'previous_running_programs+=("$program")' in script
    assert 'sudo supervisorctl stop "$program"' in script
    rollback_body = script.split("rollback_managed_services() {", maxsplit=1)[1].split("\n}", maxsplit=1)[0]
    assert "program_was_running load_balancer" in rollback_body
    assert "http://127.0.0.1:8000/health" in rollback_body


def test_english_wiktionary_cache_irc_is_an_automatic_managed_service() -> None:
    """Supervisor and release management keep the cache listener running."""
    for filename in ("supervisor-botjagwar.conf.template", "supervisor-botjagwar.conf"):
        content = (ROOT / "conf" / filename).read_text(encoding="utf-8")
        section = content.split(
            "[program:english_wiktionary_cache_irc]", maxsplit=1
        )[1].split("\n[", maxsplit=1)[0]
        assert "english_wiktionary_cache_irc.py" in section
        assert "autostart=true" in section
        assert "autorestart=true" in section

    script = (ROOT / "install.sh").read_text(encoding="utf-8")
    assert 'managed_programs+=("$program")' in script
    assert 'previous_running_programs+=("$program")' in script


def test_tenymalagasy_mirror_is_an_automatic_managed_service() -> None:
    """Supervisor starts the persistent mirror and installation checks its health."""
    for filename in ("supervisor-botjagwar.conf.template", "supervisor-botjagwar.conf"):
        content = (ROOT / "conf" / filename).read_text(encoding="utf-8")
        section = content.split("[program:tenymalagasy_mirror]", maxsplit=1)[1].split("\n[", maxsplit=1)[0]
        assert "autostart=true" in section
        assert "autorestart=true" in section
        assert "tenymalagasy_mirror.sqlite3" in section

    script = (ROOT / "install.sh").read_text(encoding="utf-8")
    assert "http://127.0.0.1:8004/health" in script
    rollback_body = script.split("rollback_managed_services() {", maxsplit=1)[1].split("\n}", maxsplit=1)[0]
    assert "program_was_running tenymalagasy_mirror" in rollback_body


def test_installer_preserves_opt_in_program_state() -> None:
    """Generic opt-in services retain their running state across upgrades."""
    script = (ROOT / "install.sh").read_text(encoding="utf-8")
    managed_scan = script.split("managed_programs=()", maxsplit=1)[1].split(
        "restart_managed_services()", maxsplit=1
    )[0]
    assert "program_autostart == true" in managed_scan
    assert 'opt_in_programs+=("$program")' in managed_scan

    restore_opt_in = (
        'for program in "${opt_in_programs[@]}"; do\n'
        '  if program_was_running "$program"; then\n'
        '    managed_programs+=("$program")\n'
        "  fi\n"
        "done"
    )
    capture_position = script.index('previous_running_programs+=("$program")')
    restore_position = script.index(restore_opt_in)
    restart_position = script.index("restart_managed_services", restore_position)
    assert capture_position < restore_position < restart_position

    healthcheck_body = script.split(
        "healthcheck_managed_services() {", maxsplit=1
    )[1].split("\n}", maxsplit=1)[0]
    assert 'if [[ $deployment_autostart != True ]]; then\n        return 0' in healthcheck_body
    activation_body = script.split(
        'if [[ -z ${TEST:-} && -z ${RESTART_ALL:-} ]]; then', maxsplit=1
    )[1].split("\nfi", maxsplit=1)[0]
    assert "$deployment_autostart == True" not in activation_body
    assert "restart_managed_services" in activation_body
    assert "healthcheck_managed_services" in activation_body


def test_ctranslate_programs_share_restart_and_rollback_state() -> None:
    """CTranslate services preserve their exact running state across upgrades."""
    script = (ROOT / "install.sh").read_text(encoding="utf-8")
    rendered_scan = script.split(
        "collect_rendered_programs() {", maxsplit=1
    )[1].split("restart_managed_services()", maxsplit=1)[0]
    capture_scan = script.split(
        'switch_managed_link pgrest "pgrest-releases/$release_id"', maxsplit=1
    )[1].split('for program in "${opt_in_programs[@]}"', maxsplit=1)[0]
    rollback_scan = script.split(
        "rollback_managed_services() {", maxsplit=1
    )[1].split("\n}", maxsplit=1)[0]

    assert 'collect_rendered_programs "$rendered_config_dir/supervisor-ctranslate.conf"' in rendered_scan
    assert "/etc/supervisor/conf.d/supervisor-ctranslate.conf" in capture_scan
    assert 'previous_running_programs+=("$program")' in capture_scan
    assert '"$rollback_dir/supervisor-ctranslate.conf"' in rollback_scan
    assert 'program_was_running "$program"' in rollback_scan


def test_install_validates_configuration_before_activation() -> None:
    """Upgrades fail safely instead of activating invalid configuration."""
    script = (ROOT / "install.sh").read_text(encoding="utf-8")
    validation = '"$src_dir/scripts/validate_config.py" "$config_dir/config.ini"'

    assert validation in script
    assert script.index(validation) < script.index('activate "$release_id"')
    assert "TEST must be unset for production or exactly 1" in script


def test_cron_installation_is_transactional() -> None:
    """Managed cron changes have exact backup or removal paths on rollback."""
    script = (ROOT / "install.sh").read_text(encoding="utf-8")

    assert 'sudo cp -a "$materialized_cron_file" "$rollback_dir/botjagwar-materialized-views"' in script
    assert 'sudo cp -a "$dashboard_cron_file" "$rollback_dir/botjagwar-dashboard-statistics"' in script
    assert 'restore_cron_file() {' in script
    cleanup_condition = (
        'if [[ $status != 0 \\\n'
        '    && ( $materialized_cron_switched == 1 || $dashboard_cron_switched == 1 ) ]]'
    )
    assert cleanup_condition in script
    assert 'sudo install -o root -g root -m 0644 "$materialized_cron_source" "$materialized_cron_file"' in script
    assert 'sudo install -o root -g root -m 0644 "$dashboard_cron_source" "$dashboard_cron_file"' in script
    assert script.count("*/5 * * * * $current_user BOTJAGWAR_CONFIG=$config_dir/config.ini") == 1
    assert "scripts/snapshot_page_check_statistics.py" in script
    assert "page_check_statistics_snapshot.log" in script

    cron_branches = script.rsplit(REMOTE_STATISTICS_CONDITION, maxsplit=1)[1].split(
        "\n  fi", maxsplit=1
    )[0]
    remote_cron_branch, local_cron_branch = cron_branches.split("\n  else", maxsplit=1)
    assert "scripts/snapshot_page_check_statistics.py" not in remote_cron_branch
    assert "scripts/snapshot_page_check_statistics.py" in local_cron_branch

    rollback_body = script.split("restore_scheduled_jobs() {", maxsplit=1)[1].split("\n}", maxsplit=1)[0]
    assert "botjagwar-materialized-views" in rollback_body
    assert "botjagwar-dashboard-statistics" in rollback_body
    assert "sudo service cron restart" in rollback_body


def test_frontend_install_does_not_replace_persistent_rpc_configuration() -> None:
    """The frontend overlay no longer manages the persistent RPC include."""
    script = (ROOT / "frontend/install.sh").read_text(encoding="utf-8")
    upstream_loop = script.split("for upstream_file in ", maxsplit=1)[1].split("; do", maxsplit=1)[0]

    assert "supervisor-rpc-location.conf" not in upstream_loop
    assert "if [[ ! -e /etc/botjagwar/supervisor-rpc-location.conf ]]" in script
