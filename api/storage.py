import pickle
from csv import DictWriter
from threading import Lock

from api.data_caching import FastTranslationLookup
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
        self.language = language
        self.mising_translations_file = open('user_data/missing_translations-%s.pickle' % self.language, 'rb')

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


class MissingTranslationCsvWriter(object):
    def __init__(self, language):
        self.language = language
        self.reader = MissingTranslationFileReader(language)
        self.reader.read()
        self.lookup = FastTranslationLookup('en', 'mg')
        self.lookup.build_table()

    def to_csv(self, filename_pattern='user_data/missing_translations-%s.csv'):
        # missing_translations is a dictionary where the key is a translation file
        # and where the value is the number of times it's been looked for
        out_file = open(filename_pattern % self.language, 'w')
        dict_list = [
            {'word': translation, 'hits': hits}
            for translation, hits in self.reader.mising_translations.items()
            if not self.lookup.word_exists(translation)
        ]
        writer = DictWriter(out_file, ['word', 'hits'])
        writer.writeheader()
        writer.writerows(dict_list)
        out_file.close()


class CacheMissError(KeyError):
    pass


class SiteExtractorCacheEngine(object):
    def __init__(self, sitename):
        self.sitename = sitename
        try:
            old_dump_file = open('user_data/site-extractor-%s.pkl' % self.sitename, 'rb')
        except FileNotFoundError:
            self.page_dump = {}
        else:
            self.page_dump = pickle.load(old_dump_file)
            old_dump_file.close()

        self.counter = 0

    def get(self, word):
        if word in self.page_dump:
            return self.page_dump[word]
        else:
            raise CacheMissError()

    def iterate(self):
        for word in self.page_dump:
            yield self.page_dump[word]

    def add(self, word, content):
        self.page_dump[word] = content

    def write(self):
        page_dump_file = open('user_data/site-extractor-%s.pkl' % self.sitename, 'wb')
        pickle.dump(self.page_dump, page_dump_file, pickle.HIGHEST_PROTOCOL)
        page_dump_file.close()
