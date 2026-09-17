import configparser
import os
from pathlib import Path

REPO_CONF_PATH = Path(__file__).resolve().parents[1] / "conf"
DEFAULT_CONFIG_NAME = "test_config.ini" if os.environ.get("TEST") == "1" else "config.ini"

conf_paths = [
    os.environ.get("BOTJAGWAR_CONF_PATH"),
    str(REPO_CONF_PATH),
    str(Path.cwd() / "conf"),
    str(Path.home() / ".config/botjagwar"),
    str(Path.home() / "botjagwar/conf"),
    str(Path.home() / "Documents/botjagwar/conf"),
    "/opt/botjagwar/conf",
]

CONF_ROOT_PATH = next(
    (
        confpath
        for confpath in conf_paths
        if confpath and (Path(confpath).expanduser() / DEFAULT_CONFIG_NAME).is_file()
    ),
    str(REPO_CONF_PATH),
)

HOME_CONFIG_PATH = str(Path.home() / ".config/botjagwar/config.ini")


class BotjagwarConfig(object):
    """
    Manage global and script specific configuration.
    All config files should be stored in CONF_ROOT_PATH.
    BOTJAGWAR_CONFIG selects one authoritative file. Otherwise, an optional
    override at ~/.config/botjagwar/config.ini takes highest priority.
    """

    def __init__(self, name: str | None = None) -> None:
        self.default_config_parser = configparser.ConfigParser(interpolation=None)
        explicit_config = os.environ.get("BOTJAGWAR_CONFIG")
        default_config_path = (
            Path(explicit_config).expanduser()
            if explicit_config
            else Path(CONF_ROOT_PATH) / DEFAULT_CONFIG_NAME
        )
        loaded = self.default_config_parser.read(default_config_path)
        if explicit_config and not loaded:
            raise FileNotFoundError(
                f"BOTJAGWAR_CONFIG does not identify a readable file: {default_config_path}"
            )

        self.home_config_parser = configparser.ConfigParser(interpolation=None)
        if not explicit_config and os.path.exists(HOME_CONFIG_PATH):
            self.home_config_parser.read(HOME_CONFIG_PATH)
        else:
            self.home_config_parser = None

        if name is not None:
            self.specific_config_parser = configparser.ConfigParser(interpolation=None)
            self.specific_config_parser.read(Path(CONF_ROOT_PATH) / name)
        else:
            self.specific_config_parser = None

    def get(self, key: str, section: str = "global") -> str:
        # Priority: home override > specific config > default config
        if self.home_config_parser is not None:
            try:
                return self.home_config_parser.get(section, key)
            except (configparser.NoSectionError, configparser.NoOptionError):
                pass

        if self.specific_config_parser is None:
            return self.default_config_parser.get(section, key)
        try:
            # Return the value from the specific configuration if available
            return self.specific_config_parser.get(section, key)
        except configparser.NoSectionError:
            # Fall back to the default configuration when the section is
            # missing in the specific config file
            return self.default_config_parser.get(section, key)
        except (configparser.NoOptionError, KeyError) as e:
            # Mirror the previous behaviour of raising KeyError when the key
            # does not exist in either configuration file
            raise KeyError(f"No key {key} in section {section}") from e
