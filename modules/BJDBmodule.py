import MySQLdb as db
import pywikibot
from set_database_password import PasswordManager
verbose = True

class DatabaseException(Exception):
    pass

class Database(object):
    def __init__(self, host=u'localhost', login=u'root', passwd=None, dbname=None, table=u'teny'):
        assert type(host) is unicode
        assert type(host) is unicode

        self.pw_manager = PasswordManager()
        if passwd is None:
            self.db_passwd = self.pw_manager.get_password()
        else:
            self.db_passwd = passwd

        self.infos = {
            u'host': host,
            u'login': login,
            u'passwd': self.db_passwd,
            u'table': table
        }
        self.tablename = u'teny'
        self.connect = db.connect(host, login, self.db_passwd)
        self.cursor = self.connect.cursor()
        if dbname is None:
            dbname = u"data_botjagwar"
        self.infos[u'DB'] = dbname

        self.querycount = 0
        self.autocommit = True

        self.words = []

    def __del__(self):
        self.cursor.close()

    def close(self):
        self.cursor.close()

    def load(self):
        sqlreq = u"select * from `%(DB)s`.`%(table)s` WHERE 1" % self.infos
        return self.raw_query(sqlreq)

    def set_dbname(self, dbname):
        assert type(dbname) is unicode
        """Set the current database we're working on"""
        self.infos[u'DB'] = dbname

    def set_table(self, table):
        assert type(table) is unicode
        """Set the current table we're working on"""
        self.infos[u'table'] = table

    def insert(self, values_dict):
        """Insert in database values in values_dict"""
        if isinstance(values_dict, list):
            self._insert_many(values_dict)
        elif isinstance(values_dict, dict):
            self._insert_one(values_dict)

    def _do_insert(self, values_dict):
        sql = u"insert into `%(DB)s`.`%(table)s` (" % self.infos
        for i in values_dict:
            sql += u"`%s`," % self.connect.escape_string(i)
        sql = sql.strip(u',')
        sql += u") values ("
        for key, value in values_dict.items():
            if value is None:
                value = u'NULL'
            value = db.escape_string(value)
            sql += u"'%s'," % value
        sql = sql.strip(u',')
        sql += u")"
        try:
            self.cursor.execute(sql)
        except UnicodeError:
            sql = sql.encode('utf8')
            self.cursor.execute(sql)
        except Exception as e:
            if verbose:
                pywikibot.output(sql)
            raise e

        self.querycount += 1
        if not self.querycount % 1000:
            qcstr = str(self.querycount)
            qcstr = qcstr + chr(8) * (len(qcstr) + 1)
            if verbose: print(qcstr,)

    def _insert_one(self, values_dict):
        self._do_insert(values_dict)
        if self.autocommit:
            self.connect.commit()

    def _insert_many(self, list_values_dict):
        for values_dict in list_values_dict:
            self._do_insert(values_dict)
        if self.autocommit:
            self.connect.commit()

    def _action(self, conditions={}, initstring=unicode(), operand=u'='):
        """action for SELECT or DELETE statements, specified by initstring"""
        sql = initstring
        if not conditions:
            sql += u"from `%(DB)s`.`%(table)s` WHERE `fiteny`='mg'" % self.infos
        elif conditions == {u'fiteny': u'REHETRA'}:
            sql += u"from `%(DB)s`.`%(table)s`"
        else:
            sql += u"from `%(DB)s`.`%(table)s` WHERE " % self.infos
            for key, value in conditions.items():
                value = value.encode('utf8')     # Yay!
                value = db.escape_string(value)  # Python 2
                value = value.decode('utf8')     # for the win!
                sql += u"`%s` %s '%s' AND " % (key, operand, value)

            sql = sql.strip(u'AND ')

        rep = ()
        try:
            self.cursor.execute(sql)
            rep = self.cursor.fetchall()
        except UnicodeEncodeError as e:
            sql = sql.encode('utf8')
            try:
                self.cursor.execute(sql)
                rep = self.cursor.fetchall()
            except Exception as e:
                if verbose:
                    pywikibot.output("HADISOANA: %s" % e.message)
                    pywikibot.output(u'\03{red}%s\03{default}' % sql)
                    print(e.message)
                return tuple()
        except Exception as e:
            if verbose:
                pywikibot.output(u'HADISOANA ANATY: \03{red}%s\03{default}' % sql)
            raise e  # Unhandled Exception
        finally:
            return rep


    def read(self, conditions={}, select=u'*'):
        """Read data from the current DB"""
        return self._action(conditions, u"select %s " % select, u'like')

    def read_all(self):
        return self.raw_query(u"select * from `%(DB)s`.`%(table)s`" % self.infos)

    def update(self, conditions, newvalues_dict):
        "Update SQL line with new values following conditions in conditions"
        raise NotImplementedError()

    def delete(self, conditions=False):
        "Delete data from the DB"
        return self._action(conditions, u"delete ")

    def raw_query_noFetch(self, sql):
        "Raw SQL query (returns cursor) does not fetch, does not commit."
        for i in range(4):
            try:
                self.cursor.execute(sql)
                return self.cursor
            except UnicodeEncodeError:
                self.cursor.execute(sql.encode('utf8'))
                return self.cursor


    def raw_query(self, sql, return_fetched_results=True, commit_after_query=True):
        "Raw SQL query (returns fetched result)"
        q = self.raw_query_noFetch(sql)
        if commit_after_query:
            self.connect.commit()
        if return_fetched_results:
            return q.fetchall()


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