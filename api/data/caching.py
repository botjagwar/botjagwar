from api.databasemanager import DictionaryDatabaseManager
from api.decorator import time_this

from database.dictionary import Word


class FastTranslationLookup:
    def __init__(
            self,
            source_language='en',
            target_language='mg',
            database_file='default'):
        self.output_database = DictionaryDatabaseManager(
            database_file=database_file)
        self.fast_tree = {}
        self.target_language = target_language
        self.source_language = source_language

    @time_this('Fast translation lookup tree building')
    def build_table(self):
        """
        Builds the lookup table.

        Table lookups are IO-expensive, so build a fast lookup tree to check entry existence in database.

        For some reason, using the ORM uses up lots of CPU, so we'll resort to using a more traditional
        SQL query in this particular function.
        :return:
        """
        print("--- building fast translation lookup tree ---")
        with self.output_database.engine.connect() as connection:
            query = connection.execute(
                """
            select
                word.id,
                word.word,
                word.language,
                word.part_of_speech,
                definitions.definition,
                definitions.definition_language
            from
                dictionary,
                word,
                definitions
            where
                dictionary.definition = definitions.id
                and word.id = dictionary.word
                and language = '%s'
                and definition_language = '%s'
            """ % (
                    self.source_language,
                    self.target_language)
            )
            for w in query.fetchall():
                word, language, part_of_speech, definition = w[1], w[2], w[3], w[4]
                key = (word, language, part_of_speech)
                if key in self.fast_tree:
                    if definition not in self.fast_tree[key]:
                        self.fast_tree[key].append(definition)
                else:
                    self.fast_tree[key] = [definition]

            print('translation lookup tree contains %d items' %
                  len(self.fast_tree))
        print("--- done building fast tree ---")

    def translate_word(self, entry, language, part_of_speech):
        data = (entry, language, part_of_speech)
        if data in self.fast_tree:
            return self.fast_tree[data]

        raise LookupError('No found: %s' % str(data))

    def translate(self, entry):
        return self.translate_word(
            entry.entry,
            entry.language,
            entry.part_of_speech)

    def lookup(self, entry):
        data = (entry.entry, entry.language, entry.part_of_speech)
        if data in self.fast_tree:
            return True

        return False

    def word_exists(self, word):
        for data in self.fast_tree:
            if data[0] == word:
                return True

        return False


class FastWordLookup:
    def __init__(self, database_file='default'):
        self.output_database = DictionaryDatabaseManager(
            database_file=database_file)
        self.fast_tree = set()

    @time_this('Fast tree building')
    def build_fast_word_tree(self):
        """
        Table lookups are IO-expensive, so build a fast lookup tree to check entry existence in database
        :return:
        """
        print("--- building fast word lookup tree ---")
        q = self.output_database.session.query(Word)
        for w in q.yield_per(1000):
            self.fast_tree.add((w.word, w.language))
        print('out fast tree contains %d items' % len(self.fast_tree))
        print("--- done building fast tree ---")

    def lookup(self, entry):
        if (entry.entry, entry.language) in self.fast_tree:
            return True

        return False
