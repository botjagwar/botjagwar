import configparser

from api.decorator import singleton

CONF_ROOT_PATH = '/home/rado/botjagwar/conf'


@singleton
class BotjagwarConfig(object):
    """
    Manage global and script specific configuration.
    All config files should be stored in CONF_ROOT_PATH
    """
    def __init__(self, name=None):
        self.default_config_parser = configparser.ConfigParser()
        self.default_config_parser.read(CONF_ROOT_PATH+ '/config.ini')
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
            self.specific_config_parser.get(section, key)
        else:
            return self.default_config_parser.get(section, key)
