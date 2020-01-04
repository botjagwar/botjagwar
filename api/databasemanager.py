#!/usr/bin/python3.6

import configparser
import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import SingletonThreadPool

from database.dictionary import Base as WordBase
from database.language import Base as LanguageBase

log = logging.getLogger(__file__)


class DatabaseManager(object):
    conf_key = 'database_uri'
    database_file = None
    db_type = 'default'

    def __init__(self, base):
        assert self.db_header is not None
        scheme_head = self.db_header.split('://')[0]
        if 'sqlite' in scheme_head:
            self.db_type = 'sqlite'
        elif 'mysql' in scheme_head:
            self.db_type = 'mysql'

        if self.database_file is not None:
            if self.db_type == 'sqlite':
                self.db_header = 'sqlite:///%s' % self.database_file

        log.info('Using database %s' % self.db_header)
        self.engine = create_engine(
            self.db_header,
            poolclass=SingletonThreadPool)

        base.metadata.create_all(self.engine)
        self.SessionClass = sessionmaker(bind=self.engine)
        self.session = self.SessionClass()

    def read_configuration(self):
        self.config_parser = configparser.ConfigParser()
        self.config_parser.read('/opt/botjagwar/conf/config.ini')
        self.db_header = self.config_parser.get('global', self.conf_key)


class LanguageDatabaseManager(DatabaseManager):
    database_file = 'data/language.db'

    def __init__(self, database_file='default', db_header='sqlite:///'):
        if database_file != 'default': # when defined, assumed a sqlite database file
            self.database_file = database_file
            self.db_header = db_header + database_file
        else:
            self.read_configuration()

        super(LanguageDatabaseManager, self).__init__(LanguageBase)


class DictionaryDatabaseManager(DatabaseManager):
    database_file = ''

    def __init__(self, database_file='default', db_header='sqlite:///'):
        log.debug('database_file is %s' % database_file)
        if database_file != 'default': # when defined, assumed a sqlite database file
            self.database_file = database_file
            self.db_header = db_header + database_file
        else:
            self.read_configuration()

        super(DictionaryDatabaseManager, self).__init__(WordBase)
        log.debug('database file/URL: %s' % self.database_file)