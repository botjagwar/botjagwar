import pickle
from threading import Lock

from api.decorator import critical_section, singleton
from object_model.word import Entry

entry_page_cs_lock = Lock()
missing_translation_cs_lock = Lock()


class Reader(object):
    pass


class Writer(object):
    pass


@singleton
class EntryPageFileWriter(Writer):
    def __init__(self, language):
        self.page_dump_file = open('user_data/dump-%s.pkl' % language, 'wb')
        self.page_dump = {}
        self.counter = 0

    @critical_section(entry_page_cs_lock)
    def add(self, entry: Entry):
        self.counter += 1
        if self.counter % 250 == 0:
            print(self.counter)

        if entry.entry in self.page_dump:
            if entry not in self.page_dump[entry.entry]:
                self.page_dump[entry.entry].append(entry)
        else:
            self.page_dump[entry.entry] = [entry]

    def write(self):
        pickle.dump(self.page_dump, self.page_dump_file, pickle.HIGHEST_PROTOCOL)
        self.page_dump_file.close()


@singleton
class EntryPageFileReader(Reader):
    def __init__(self, language):
        self.page_dump_file = open('user_data/dump-%s.pkl' % language, 'rb')
        self.page_dump = {}

    def read(self):
        self.page_dump = pickle.load(self.page_dump_file)


@singleton
class MissingTranslationFileReader(Reader):
    def __init__(self, language):
        self.mising_translations = {}
        self.mising_translations_file = open('user_data/missing_translations-%s.pickle' % language, 'rb')

    def read(self):
        self.mising_translations = pickle.load(self.mising_translations_file)


@singleton
class MissingTranslationFileWriter(Writer):
    def __init__(self, language):
        self.mising_translations = {}
        self.mising_translations_file = open('user_data/missing_translations-%s.pickle' % language, 'wb')

    @critical_section(missing_translation_cs_lock)
    def add(self, translation):
        if translation in self.mising_translations:
            self.mising_translations[translation] += 1
        else:
            self.mising_translations[translation] = 1

    def write(self):
        pickle.dump(self.mising_translations, self.mising_translations_file, pickle.HIGHEST_PROTOCOL)