from modules.database import Database
from set_database_password import PasswordManager
import MySQLdb as db
verbose = True


class WordDatabase(object):
    def __init__(self, params={}, Loaded_DB=None):
        """"params-> dict {key:value,...}; Loaded_DB-> DB object"""
        self.pw_manager = PasswordManager()
        self.db_passwd = self.pw_manager.get_password()

        if not params:
            # Currently hard-coded parameters, parameters read-in-file in the future.
            self.params = {
                'host': 'localhost',
                'login': 'root',
                'passwd': self.db_passwd
            }
        else:
            self.params = params
        self.famaritana_fiteny = 'mg'

        if Loaded_DB != None:
            self.DB = Loaded_DB
        else:
            self.DB = Database(self.params['host'], self.params['login'], self.params['passwd'])

    def __del__(self):
        self.close()

    def close(self):
        if self.DB:
            self.DB.close()

    def set_contentlanguage(self, ISOcode):
        """Contentlanguage is the language in which words are translated.
            Default is 'mg'. This parameter is used when trying to read
            entry or when checking if the entry is translated in DB"""
        self.famaritana_fiteny = ISOcode

    def save_entry(self, entry):
        paramsdict = {
            'teny': entry.entry,
            'famaritana': entry.entry_definition,
            'karazany': entry.part_of_speech,
            'fiteny': entry.language
        }
        self.DB.insert(paramsdict)

    def append(self, entry, definition, pos, language):
        """
        Inserts an entry in `teny` table
        Args:
            entry: word to be put
            definition: translation of the word
            pos: part of speech
            language: language code

        Returns:

        """
        entry = self._to_unicode(entry)
        definition = self._to_unicode(definition)

        paramsdict = {
            'teny': entry,
            'famaritana': definition,
            'karazany': str(pos),
            'fiteny': str(language)}
        self.DB.insert(paramsdict)

    def _to_unicode(self, string):
        if type(string) is not str:
            try:
                string = str(string, 'latin1')
            except TypeError:
                string = str(string)
            finally:
                return string

    def do_commit(self):
        self.DB.connect.commit()

    def exists_in_specialised_dictionary(self, entry, language, POS):
        entry = db.escape_string(entry.encode('utf8'))
        language = db.escape_string(language.encode('utf8'))
        language = language.decode('utf8')
        entry = entry.decode('utf8')
        sql = "select mg from data_botjagwar.%s_mg where %s='%s'" % (language, language, entry)
        result = self.DB.raw_query(sql)

        if result:
            return True
        else:
            return False

    def _check_existence(self, entry_col_name, entry, lang_col_name, lang, POS):
        # OLD VERSION USING DB ACCESS
        conditions = {entry_col_name: entry,
                      lang_col_name: self.famaritana_fiteny}  # see explanation in "set_contentlanguage(ISOcode)"

        if POS: conditions['karazany'] = POS
        if lang: conditions['fiteny'] = lang
        rep = self.DB.read(conditions, 'teny')  # execution of SQL
        if rep:
            return True
        else:
            return False

    def exists(self, entry, lang='', POS=''):
        """Checks if entry exists in database"""
        # TODO: harmonise encoding to ease detection in DB
        # t0 = datetime.datetime.now()
        orig_entry = entry
        encodings_list = ['latin1', 'cp850', 'cp1252', 'utf8']
        for encoding in encodings_list:
            try:
                entry = entry.decode(encoding)
            except UnicodeError:
                pass
                # entry = unicode(entry)
        return self._check_existence('teny', entry, 'fiteny', lang, POS)

    def raw_translate(self, word, pos, language='fr'):
        """gives the translation of the given word in the given language.
           Returns [translation, ...]. All strings are Unicode objects."""
        word = word.encode('utf8')
        db.escape_string(word)
        if type(word) is not str:
            try:
                word = word.decode('utf8')
            except UnicodeEncodeError:
                word = word.decode('latin1')

        translations = []
        # Find definition in special dictionary
        if language in ['fr', 'en']:
            sql_query_result = self.DB.raw_query(
                "select mg from data_botjagwar.%s_mg where %s='%s'"
                % (language, language, word))
            for translation in sql_query_result:
                translation = translation
                translations.append(translation)

        # No translation found in pecial dictionary? Look up in the general one!
        if not translations:
            sql_query_result2 = self.DB.raw_query(
                "select famaritana from data_botjagwar.teny where fiteny='%s' and teny='%s'"
                % (language, word))
            for translation in sql_query_result2:
                translation = translation[0]
                # Remove unneeded characters
                for char in '[]':
                    # Try decoding using different encoding if UnicodeErrors occur
                    for encoding in ['utf8', 'latin-1']:
                        try:
                            translation = translation.replace(char, '')
                            break
                        except UnicodeError:
                            translation = translation.decode(encoding)
                    # Make string unicode when all's over
                    translation = str(translation)

                # Pack up translations for delivery
                for t in translation.split(','):  # Translation in this dictionary are comma-separated...
                    translations.append((t.strip(),))

        return translations

    def translate(self, word, language, pos='ana'):
        translations = self.raw_translate(word, pos, language)

        # Post-process to directly have Wikibolana's definitions formatting
        tstring = ""
        for translation in translations:
            s = translation[0].strip()
            try:
                tstring += "[[%s]], " % s
            except UnicodeDecodeError:
                tstring += "[[%s]], " % s.decode("latin1")

        tstring = tstring.strip(", ")
        return tstring