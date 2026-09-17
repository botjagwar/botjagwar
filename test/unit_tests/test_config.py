import importlib
from pathlib import Path


def test_specific_config_overrides_default(tmp_path) -> None:
    # create default config
    default_config = tmp_path / "config.ini"
    default_config.write_text("[global]\nfoo=bar\n")

    # create specific config
    specific_config = tmp_path / "specific.ini"
    specific_config.write_text("[global]\nfoo=baz\n")

    # import module and patch CONF_ROOT_PATH
    import api.config as config_module
    importlib.reload(config_module)  # ensure module is fresh
    original_conf_root = config_module.CONF_ROOT_PATH
    try:
        config_module.CONF_ROOT_PATH = str(tmp_path)
        cfg = config_module.BotjagwarConfig(name="specific.ini")
        assert cfg.get("foo") == "baz"
    finally:
        config_module.CONF_ROOT_PATH = original_conf_root


def test_repo_conf_path_is_discovered() -> None:
    import api.config as config_module

    importlib.reload(config_module)

    assert Path(config_module.CONF_ROOT_PATH).name == "conf"
    assert config_module.BotjagwarConfig().get("debug") is not None


def test_home_directory_config_overrides_default(tmp_path) -> None:
    """Config file at ~/.config/botjagwar/config.ini takes highest priority."""
    import api.config as config_module
    importlib.reload(config_module)
    original_conf_root = config_module.CONF_ROOT_PATH
    original_home = config_module.HOME_CONFIG_PATH
    try:
        config_module.CONF_ROOT_PATH = str(tmp_path)
        # Write default config
        (tmp_path / "config.ini").write_text("[global]\nfoo=default\n")
        # Write home override config
        home_config = tmp_path / "home_override.ini"
        home_config.write_text("[global]\nfoo=home_override\n")
        config_module.HOME_CONFIG_PATH = str(home_config)
        cfg = config_module.BotjagwarConfig()
        assert cfg.get("foo") == "home_override"
    finally:
        config_module.CONF_ROOT_PATH = original_conf_root
        config_module.HOME_CONFIG_PATH = original_home


def _write_default_config(tmp_path) -> Path:
    """Write the default config file using the name BotjagwarConfig expects."""
    import os

    default_name = "test_config.ini" if os.environ.get("TEST") == "1" else "config.ini"
    config_file = tmp_path / default_name
    config_file.write_text("[global]\nfoo=default\n")
    return config_file


def test_home_directory_config_falls_back_to_default(tmp_path) -> None:
    """When home config doesn't have the key, fall back to default."""
    import api.config as config_module
    importlib.reload(config_module)
    original_conf_root = config_module.CONF_ROOT_PATH
    original_home = config_module.HOME_CONFIG_PATH
    try:
        config_module.CONF_ROOT_PATH = str(tmp_path)
        _write_default_config(tmp_path)
        # Home config exists but doesn't have 'foo'
        home_config = tmp_path / "home_override.ini"
        home_config.write_text("[global]\nbar=only_bar\n")
        config_module.HOME_CONFIG_PATH = str(home_config)
        cfg = config_module.BotjagwarConfig()
        assert cfg.get("foo") == "default"
    finally:
        config_module.CONF_ROOT_PATH = original_conf_root
        config_module.HOME_CONFIG_PATH = original_home


def test_missing_home_config_falls_back_to_default(tmp_path) -> None:
    """When home config path doesn't exist, fall back to default."""
    import api.config as config_module
    importlib.reload(config_module)
    original_conf_root = config_module.CONF_ROOT_PATH
    original_home = config_module.HOME_CONFIG_PATH
    try:
        config_module.CONF_ROOT_PATH = str(tmp_path)
        _write_default_config(tmp_path)
        config_module.HOME_CONFIG_PATH = str(tmp_path / "nonexistent" / "config.ini")
        cfg = config_module.BotjagwarConfig()
        assert cfg.get("foo") == "default"
    finally:
        config_module.CONF_ROOT_PATH = original_conf_root
        config_module.HOME_CONFIG_PATH = original_home


def test_explicit_config_is_authoritative(monkeypatch, tmp_path: Path) -> None:
    """Managed services must not let a home override shadow protected config."""
    import api.config as config_module

    explicit = tmp_path / "protected.ini"
    explicit.write_text("[global]\nfoo=protected\n", encoding="utf-8")
    home = tmp_path / "home.ini"
    home.write_text("[global]\nfoo=home\n", encoding="utf-8")
    monkeypatch.setenv("BOTJAGWAR_CONFIG", str(explicit))
    monkeypatch.setattr(config_module, "HOME_CONFIG_PATH", str(home))

    assert config_module.BotjagwarConfig().get("foo") == "protected"


def test_config_values_allow_literal_percent_signs(monkeypatch, tmp_path: Path) -> None:
    """Credentials and URIs may contain percent-encoded values."""
    explicit = tmp_path / "protected.ini"
    explicit.write_text(
        "[global]\ndatabase_uri=postgresql://user:p%40ss@localhost/db\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("BOTJAGWAR_CONFIG", str(explicit))

    import api.config as config_module

    assert (
        config_module.BotjagwarConfig().get("database_uri")
        == "postgresql://user:p%40ss@localhost/db"
    )


def test_explicit_config_keeps_packaged_named_overlays(
    monkeypatch, tmp_path: Path
) -> None:
    """An explicit default must not relocate packaged processor overlays."""
    import api.config as config_module

    explicit = tmp_path / "protected.ini"
    explicit.write_text("[global]\nfoo=protected\n", encoding="utf-8")
    overlay_root = tmp_path / "overlays"
    overlay_root.mkdir()
    (overlay_root / "specific.ini").write_text(
        "[global]\nfoo=overlay\n", encoding="utf-8"
    )
    monkeypatch.setenv("BOTJAGWAR_CONFIG", str(explicit))
    monkeypatch.setattr(config_module, "CONF_ROOT_PATH", str(overlay_root))

    assert config_module.BotjagwarConfig("specific.ini").get("foo") == "overlay"


def test_missing_explicit_config_fails_clearly(monkeypatch, tmp_path: Path) -> None:
    """A configured source of truth must not silently degrade to defaults."""
    import pytest

    import api.config as config_module

    missing = tmp_path / "missing.ini"
    monkeypatch.setenv("BOTJAGWAR_CONFIG", str(missing))

    with pytest.raises(FileNotFoundError, match="BOTJAGWAR_CONFIG"):
        config_module.BotjagwarConfig()
