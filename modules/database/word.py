from modules.database import Database
from set_database_password import PasswordManager
verbose = True


class WordDatabase(object):
    def __init__(self, params={}, Loaded_DB=None):
        """"params-> dict {key:value,...}; Loaded_DB-> DB object"""
        self.pw_manager = PasswordManager()
        self.db_passwd = self.pw_manager.get_password()

        if not params:
            # Currently hard-coded parameters, parameters read-in-file in the future.
            self.params = {
                u'host': u'localhost',
                u'login': u'root',
                u'passwd': self.db_passwd
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
            u'teny': entry,
            u'famaritana': definition,
            u'karazany': unicode(pos),
            u'fiteny': unicode(language)}
        self.DB.insert(paramsdict)

    def _to_unicode(self, string):
        if type(string) is not unicode:
            try:
                string = unicode(string, 'latin1')
            except TypeError:
                string = unicode(string)
            finally:
                return string

    def do_commit(self):
        self.DB.connect.commit()

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

            # OLD VERSION USING DB ACCESS
            conditions = {u'teny': entry,
                          u'famaritana_fiteny': self.famaritana_fiteny}  # see explanation in "set_contentlanguage(ISOcode)"

            if POS: conditions[u'karazany'] = POS
            if lang: conditions[u'fiteny'] = lang
            rep = self.DB.read(conditions, u' teny ')  # execution of SQL
            if rep:
                # if verbose: print("ct. encding : %s"%encoding)
                return True
            else:
                entry = orig_entry
                continue

        return False

    def raw_translate(self, word, language='fr'):
        """gives the translation of the given word in the given language.
           Returns [translation, ...]. All strings are Unicode objects."""
        if type(word) is not unicode:
            try:
                word = word.decode('utf8')
            except UnicodeEncodeError:
                word = word.decode('latin1')

        translations = []
        # Find definition in special dictionary
        if language in [u'fr', u'en']:
            sql_query_result = self.DB.raw_query(u"select mg from data_botjagwar.%s_mg where %s='%s'"
                                        % (language, language, word.replace(u"'", u"\\'")))
            for translation in sql_query_result:
                translation = translation
                translations.append(translation)

        # No translation found in pecial dictionary? Look up in the general one!
        if not translations:
            sql_query_result2 = self.DB.raw_query(u"select famaritana from data_botjagwar.teny where fiteny='%s' and teny='%s'"
                                         % (language, word.replace(u"'", u"\\'")))
            for translation in sql_query_result2:
                translation = translation[0]
                # Remove unneeded characters
                for char in u'[]':
                    # Try decoding using different encoding if UnicodeErrors occur
                    for encoding in ['utf8', 'latin-1']:
                        try:
                            translation = translation.replace(char, u'')
                            break
                        except UnicodeError:
                            translation = translation.decode(encoding)
                    # Make string unicode when all's over
                    translation = unicode(translation)

                # Pack up translations for delivery
                for t in translation.split(u','):  # Translation in this dictionary are comma-separated...
                    translations.append((t.strip(),))

        return translations

    def translate(self, word, language='fr'):
        translations = self.raw_translate(word, language)

        # Post-process to directly have Wikibolana's definitions formatting
        tstring = u""
        for translation in translations:
            s = translation[0].strip()
            try:
                tstring += u"[[%s]], " % s
            except UnicodeDecodeError:
                tstring += u"[[%s]], " % s.decode("latin1")

        tstring = tstring.strip(u", ")
        return tstring