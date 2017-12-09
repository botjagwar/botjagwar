import MySQLdb as db
import datetime
import pywikibot as wikipedia
from set_database_password import PasswordManager

verbose = True


class Database(object):
    def __init__(self,
                 host='localhost',
                 login='root',
                 passwd=None,
                 dbname=None,
                 table='teny'):
        self.pw_manager = PasswordManager()
        if passwd is None:
            self.db_passwd = self.pw_manager.get_password()
        else:
            self.db_passwd = passwd

        self.infos = {
            'host': host,
            'login': login,
            'passwd': self.db_passwd,
            'table': table
        }
        self.tablename = 'teny'
        self.connect = db.connect(host, login, self.db_passwd)
        self.cursor = self.connect.cursor()
        if dbname is None:
            dbname = u"data_botjagwar"
        self.infos['DB'] = dbname

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
        """Set the current database we're working on"""
        self.infos['DB'] = dbname

    def set_table(self, table):
        """Set the current table we're working on"""
        self.infos['table'] = table

    def insert(self, valuesdict):
        """Insert in database values in valuesdict"""
        if hasattr(valuesdict, 'append'):
            if verbose:
                print("mampiditra am-paran'ny lisitra...")
            self._insert_many(valuesdict)
        elif hasattr(valuesdict, 'has_key'):
            if verbose:
                print('mampiditra tsirairay...')
            self._insert_one(valuesdict)

    def _do_insert(self, valuesdict):
        sqlreq = u"insert into `%(DB)s`.`%(table)s` (" % self.infos
        for i in valuesdict:
            sqlreq += u"`%s`," % self.connect.escape_string(i)
        sqlreq = sqlreq.strip(',')
        sqlreq += u") values ("
        for i in valuesdict:
            valuesdict[i] = valuesdict[i].replace("'", "\\'")
            sqlreq += u"'%s'," % valuesdict[i]
        sqlreq = sqlreq.strip(',')
        sqlreq += u")"
        try:
            self.cursor.execute(sqlreq)
        except UnicodeError:
            sqlreq = sqlreq.encode('utf8')
            self.cursor.execute(sqlreq)
        except Exception as e:
            if verbose:
                wikipedia.output(sqlreq)
            raise e

        self.querycount += 1
        if not self.querycount % 1000:
            qcstr = str(self.querycount)
            qcstr = qcstr + chr(8) * (len(qcstr) + 1)
            if verbose: print(qcstr,)

    def _insert_one(self, valuesdict):
        self._do_insert(valuesdict)
        if self.autocommit:
            self.connect.commit()

    def _insert_many(self, list_valuesdict):
        for valuesdict in list_valuesdict:
            self._do_insert(valuesdict)
        if self.autocommit:
            self.connect.commit()

    def _action(self, conditionsdict={}, initstring=unicode(), operand=u'='):
        """action for SELECT or DELETE statements, specified by initstring"""
        sqlreq = initstring
        if not conditionsdict:
            sqlreq += u"from `%(DB)s`.`%(table)s` WHERE `fiteny`='mg'" % self.infos
        elif conditionsdict == {'fiteny': 'REHETRA'}:
            sqlreq += u"from `%(DB)s`.`%(table)s`"
        else:
            sqlreq += u"from `%(DB)s`.`%(table)s` WHERE " % self.infos
            for key, value in conditionsdict.items():
                try:
                    sqlreq += u"`%s` %s '%s' AND " % (
                        unicode(key), operand, db.escape_string(value))
                except UnicodeDecodeError:
                    sqlreq += u"`%s` %s '%s' AND " % (
                        unicode(key), operand, db.escape_string(value.decode('utf8')))

            sqlreq = sqlreq.strip('AND ')

        # if verbose: wikipedia.output(u'\03{lightyellow}%s\03{default}'%sqlreq )
        sqlreq = unicode(sqlreq)
        rep = ()
        try:
            self.cursor.execute(sqlreq)
            rep = self.cursor.fetchall()
        except UnicodeEncodeError as e:
            sqlreq = sqlreq.encode('utf8')
            # rep = self.cursor.fetchall()
            try:
                self.cursor.execute(sqlreq)
                rep = self.cursor.fetchall()
            except Exception as e:
                if verbose:
                    wikipedia.output("HADISOANA: %s" % e.message)
                    wikipedia.output(u'\03{red}%s\03{default}' % sqlreq)
                    print(e.message)
                return tuple()
        except Exception as e:
            if verbose:
                wikipedia.output(u'HADISOANA ANATY: \03{red}%s\03{default}' % sqlreq)
            raise e  # Unhandled Exception
        finally:
            return rep

    def read(self, conditionsdict={}, select='*'):
        """Read data from the current DB"""
        return self._action(conditionsdict, "select %s " % select, 'like')

    def read_all(self):
        return self.raw_query(u"select * from `%(DB)s`.`%(table)s`" % self.infos)

    def update(self, conditionsdict, newvaluesdict):
        "Update SQL line with new values following conditions in conditionsdict"
        raise NotImplementedError()

    def delete(self, conditionsdict=False):
        "Delete data from the DB"
        return self._action(conditionsdict, "delete ")

    def raw_query_noFetch(self, sql):
        "Raw SQL query (returns cursor) does not fetch, does not commit."
        for i in range(4):
            try:
                self.cursor.execute(sql)
                return self.cursor
            except UnicodeEncodeError:
                self.cursor.execute(sql.encode('utf8'))
                return self.cursor


    def raw_query(self, sql, returnFetched=True, commitAfterQuery=True):
        "Raw SQL query (returns fetched result)"
        q = self.raw_query_noFetch(sql)
        if commitAfterQuery:
            self.connect.commit()
        if returnFetched:
            return q.fetchall()


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
            'karazany': unicode(pos),
            'fiteny': unicode(language)}
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
        listencodings = ['latin1', 'cp850', 'cp1252', 'utf8']
        for encoding in listencodings:
            try:
                entry = entry.decode(encoding)
            except UnicodeError:
                pass
                # entry = unicode(entry)

            # OLD VERSION USING DB ACCESS
            conditions = {'teny': entry,
                          'famaritana_fiteny': self.famaritana_fiteny}  # see explanation in "set_contentlanguage(ISOcode)"

            if POS: conditions['karazany'] = POS
            if lang: conditions['fiteny'] = lang
            rep = self.DB.read(conditions, ' teny ')  # execution of SQL
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
            qresult = self.DB.raw_query(u"select mg from data_botjagwar.%s_mg where %s='%s'"
                                        % (language, language, word.replace(u"'", u"\\'")))
            for translation in qresult:
                translation = translation
                translations.append(translation)

        # No translation found in pecial dictionary? Look up in the general one!
        if not translations:
            qresult2 = self.DB.raw_query(u"select famaritana from data_botjagwar.teny where fiteny='%s' and teny='%s'"
                                         % (language, word.replace(u"'", u"\\'")))
            for translation in qresult2:
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