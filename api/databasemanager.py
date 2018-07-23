#!/usr/bin/python3.6

import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import SingletonThreadPool

from database.dictionary import Base as WordBase
from database.language import Base as LanguageBase

log = logging.getLogger(__file__)


class DatabaseManager(object):
    database_file = None

    def __init__(self, base):
        if self.database_file is None:
            self.engine = create_engine(
                'sqlite://',
                poolclass=SingletonThreadPool)
        else:
            self.engine = create_engine(
                'sqlite:///%s' % self.database_file,
                poolclass=SingletonThreadPool)

        base.metadata.create_all(self.engine)
        self.SessionClass = sessionmaker(bind=self.engine)
        self.session = self.SessionClass()


class LanguageDatabaseManager(DatabaseManager):
    database_file = 'data/language.db'

    def __init__(self, database_file='default'):
        if database_file != 'default':
            self.database_file = database_file

        super(LanguageDatabaseManager, self).__init__(LanguageBase)


class DictionaryDatabaseManager(DatabaseManager):
    database_file = 'data/word_database.db'

    def __init__(self, database_file='default'):
        if database_file != 'default':
            self.database_file = database_file

        super(DictionaryDatabaseManager, self).__init__(WordBase)