import sys
from csv import DictReader

from api.servicemanager import DictionaryServiceManager
from api.storage import MissingTranslationCsvWriter
from database.exceptions.http import WordAlreadyExists


class Extractor(object):
    def __init__(self, language):
        self.language = language
        self.writer = MissingTranslationCsvWriter(self.language)

    def start(self):
        self.writer.to_csv()


class Loader(object):
    """
    Loads CSV file containing referenced English words into database through
    the dictionary REST service.
    The CSV is expected to have a header. Expected CSV column names are:
    - english (column #1): the english word
    - hits (column #2): contains number of times a translation of it has been asked for
    - malagasy (column #3): its malagasy translation
    Part of speech is determined automatically by looking up in a monolingual dictionary CSV file.
    """
    POS_DICT = {
        '1': 'ana',
        '2': 'mat',
        '3': 'mpam-ana',
        '4': 'mpampiankina',
        '5': 'tamb'
    }

    def __init__(self, language):
        self.language = language
        self.monolingual_dictionary_filepath = 'user_data/%s.csv' % language
        self.bilingual_dictionary_filepath = 'user_data/%s-mg.csv' % language
        self.dictionary_service = DictionaryServiceManager()
        self.monolingual = {}
        self.bilingual = {}

    def determine_part_of_speech(self, word, malagasy_translation, pos_list):
        if 'mat' in pos_list and 'ana' in pos_list:
            if malagasy_translation.startswith('man') \
                    or malagasy_translation.startswith('mi')\
                    or malagasy_translation.endswith('aina')\
                    or malagasy_translation.endswith('aina'):
                return 'mat'
            else:
                return 'ana'
        else:
            return pos_list[0]

    def load_monolingual(self):
        print('reading monolingual dictionary')
        with open(self.monolingual_dictionary_filepath, 'r') as fd:
            reader = DictReader(fd)
            for row in reader:
                if not row['pos_id']:
                    continue
                english = row['anglisy'].lower()
                if english in self.monolingual:

                    self.monolingual[english].append(
                        self.POS_DICT[row['pos_id']])
                else:
                    self.monolingual[english] = [self.POS_DICT[row['pos_id']]]

    def load_bilingual(self):
        with open(self.bilingual_dictionary_filepath, 'r') as fd:
            reader = DictReader(fd)
            for row in reader:
                english = row['english'].lower()
                if english and row['malagasy'] and row['hits']:
                    self.bilingual[english] = row['malagasy']

    def start(self):
        self.load_monolingual()
        self.load_bilingual()
        for word, malagasy_translation in self.bilingual.items():
            print('>>>>', word, '<<<<')
            definition = {
                'definition': malagasy_translation,
                'definition_language': 'mg'
            }
            word = word.strip()
            if word not in self.monolingual:
                continue
            pos_list = self.monolingual[word]
            pos = self.determine_part_of_speech(
                word, malagasy_translation, pos_list)

            entry = {
                'language': self.language,
                'definitions': [definition],
                'word': word.strip(),
                'part_of_speech': pos,
            }

            resp = self.dictionary_service.post(
                'entry/%s/create' % self.language,
                json=entry
            )
            if resp.status_code == WordAlreadyExists.status_code:
                continue


if __name__ == '__main__':
    actions = {
        'x': Extractor,
        'l': Loader
    }
    bot = actions[sys.argv[1]](sys.argv[2])
    bot.start()
