import configparser
import os

try:
    login = os.getlogin()
except OSError:
    import getpass
    login = getpass.getuser()

conf_paths = [
    f'/home/{login}/botjagwar/conf',
    f'/home/{login}/Documents/botjagwar/conf',
    '/opt/botjagwar/conf'
]

CONF_ROOT_PATH = '/opt/botjagwar/conf'

for confpath in conf_paths:
    if os.path.exists(confpath):
        CONF_ROOT_PATH = confpath
        break



class BotjagwarConfig(object):
    """
    Manage global and script specific configuration.
    All config files should be stored in CONF_ROOT_PATH
    """

    def __init__(self, name=None):
        self.default_config_parser = configparser.ConfigParser()
        self.default_config_parser.read(CONF_ROOT_PATH + '/config.ini')
        try:
            if name is not None:
                self.specific_config_parser = configparser.ConfigParser()
                self.specific_config_parser.read(CONF_ROOT_PATH + '/' + name)
            else:
                self.specific_config_parser = None
        except FileNotFoundError:
            self.specific_config_parser = None

    def get(self, key, section='global'):
        if self.specific_config_parser is not None:
            try:
                self.specific_config_parser.get(section, key)
            except configparser.NoSectionError:
                return self.default_config_parser.get(section, key)
            except KeyError:
                raise KeyError(f'No key {key} in section {section}')
        else:
            return self.default_config_parser.get(section, key)
