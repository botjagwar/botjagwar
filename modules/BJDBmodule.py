import MySQLdb as db
import pywikibot as wikipedia
import sys, time

default_passwd = 'washakie'
verbose = False

class Database(object):
    def __init__(self, host='localhost', login='root', passwd=default_passwd, dbname=u"data_botjagwar", table='teny'):
        self.infos = {
            'host':host,
            'login':login,
            'passwd':passwd,
            'table':table
        }
        #TODO: configuration file to read
        self.tablename = 'teny'
        self.connect = db.connect(host,login,passwd)
        self.cursor = self.connect.cursor()
        self.infos['DB'] = u"data_botjagwar"
        self.querycount = 0
        self.autocommit = True


        self.words = []
    
    def __del__(self):
        self.cursor.close()
        del self
    
    def close(self):
        self.cursor.close()
    
    def load(self):
        sqlreq = u"select * from `%(DB)s`.`%(table)s` WHERE 1"%self.infos
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
            if verbose: print "mampiditra am-paran'ny lisitra..."
            self._insert_many(valuesdict)
        elif hasattr(valuesdict,'has_key'):
            if verbose: print 'mampiditra tsirairay...'
            self._insert_one(valuesdict)


    def _do_insert(self, valuesdict):
        sqlreq = u"insert into `%(DB)s`.`%(table)s` ("%self.infos
        for i in valuesdict:
            sqlreq += u"`%s`,"%self.connect.escape_string(i)
        sqlreq = sqlreq.strip(',')
        sqlreq += u") values ("
        for i in valuesdict:
            valuesdict[i]=valuesdict[i].replace("'","\\'")
            sqlreq += u"'%s',"%valuesdict[i]
        sqlreq = sqlreq.strip(',')
        sqlreq += u")"
        try:
            self.cursor.execute(sqlreq)
        except UnicodeError:
            sqlreq = sqlreq.encode('utf8')
            self.cursor.execute(sqlreq)
        except Exception as e:
            if verbose: wikipedia.output(sqlreq)
            raise e

        self.querycount+=1
        if not self.querycount%1000:
            qcstr = str(self.querycount)
            qcstr = qcstr + chr(8)*(len(qcstr)+1)
            if verbose: print qcstr,


    def _insert_one(self, valuesdict):
        self._do_insert(valuesdict)
        if self.autocommit:
            self.connect.commit()


    def _insert_many(self, list_valuesdict):
        for valuesdict in list_valuesdict:
            self._do_insert(valuesdict)
        if self.autocommit:
            self.connect.commit()


    def _action(self, conditionsdict=False, initstring=unicode(), operand=u'='):
        """action for SELECT or DELETE statements, specified by initstring"""

        sqlreq = initstring
        if conditionsdict is False:
            sqlreq += u"from `%(DB)s`.`%(table)s` WHERE `fiteny`='mg'"%self.infos
        elif conditionsdict == {'fiteny':'REHETRA'}:
            sqlreq += u"from `%(DB)s`.`%(table)s` WHERE 1"
        else:
            sqlreq += u"from `%(DB)s`.`%(table)s` WHERE "%self.infos
            for i in conditionsdict:
                #if verbose: wikipedia.output(sqlreq)
                try:
                    val_i = conditionsdict[i]
                    val_i = val_i.replace("'","\\'")
                except UnicodeEncodeError:
                    val_i = conditionsdict[i]
                    val_i = val_i.decode('utf8')
                    val_i = val_i.replace("'","\\'")

                try:
                    sqlreq += u"`%s` %s '%s' AND "%(unicode(i), operand, val_i)
                except UnicodeDecodeError:
                    sqlreq += u"`%s` %s '%s' AND "%(unicode(i), operand, val_i.decode('utf8'))

            sqlreq=sqlreq.strip('AND ')

        #if verbose: wikipedia.output(u'\03{lightyellow}%s\03{default}'%sqlreq )
        sqlreq=unicode(sqlreq)
        rep=()
        try:
            self.cursor.execute(sqlreq)
            rep = self.cursor.fetchall()
        except UnicodeEncodeError as e:
            sqlreq=sqlreq.encode('utf8')
            #rep = self.cursor.fetchall()
            try:
                self.cursor.execute(sqlreq)
                rep = self.cursor.fetchall()
            except Exception as e:
                if verbose: 
                    wikipedia.output("HADISOANA: %s"%e.message)
                    wikipedia.output(u'\03{red}%s\03{default}'%sqlreq )
                if verbose: print e.message
                return tuple()
        except Exception as e:
            if verbose: wikipedia.output(u'\03{red}%s\03{default}'%sqlreq )
            raise e #Unhandled Exception
        finally:
            return rep
            return tuple()



    def read(self, conditionsdict=False, select='*'):
        """Read data from the current DB"""
        return self._action(conditionsdict, "select %s "%select, 'like')

    def read_all(self):
        return self.raw_query(u"select * from `%(DB)s`.`%(table)s` where 1"%self.infos)


    def update(self, conditionsdict, newvaluesdict):
        "Update SQL line with new values following conditions in conditionsdict"


    def delete(self, conditionsdict=False):
        "Delete data from the DB"
        return self._action(conditionsdict, "delete ")


    def raw_query_noFetch(self, sql):
        "Raw SQL query (returns cursor) does not fetch, does not commit."
        error = None
        for i in range(4):
            try:
                self.cursor.execute(sql)
                return self.cursor
                break            
            except UnicodeEncodeError:
                self.cursor.execute(sql.encode('utf8'))
                return self.cursor
            except Exception as e:
                error = e
                if verbose: print sql
                print e, 'Manandrana afaka 5 segondra...'
                time.sleep(5)
        if error:
            raise e
        
    

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
        if not params:
            #Currently hard-coded parameters, parameters read-in-file in the future.
            self.params = {
                'host':'localhost',
                'login':'root',
                'passwd':default_passwd}
        else: self.params = params
        self.famaritana_fiteny='mg'

        if Loaded_DB!=None: self.DB = Loaded_DB
        else: self.DB = Database(self.params['host'], self.params['login'], self.params['passwd'])

    def close(self):
        if self.DB:
            self.DB.close()

    def set_contentlanguage(self, ISOcode):
        """Contentlanguage is the language in which words are translated.
            Default is 'mg'. This parameter is used when trying to read
            entry or when checking if the entry is translated in DB"""
        self.famaritana_fiteny=ISOcode


    def append(self, entry, definition, pos, language):
        t0 = datetime.datetime.now()
        entry = self._to_unicode(entry)
        definition = self._to_unicode(definition)

        paramsdict = {
            'teny':entry,
            'famaritana':definition,
            'karazany':unicode(pos),
            'fiteny':unicode(language)}
        self.DB.insert(paramsdict)
        t1 = datetime.datetime.now()
        dt = t1-t0
        d = dt.seconds*1000+dt.microseconds/1000
        if verbose: print '<i>Tanteraka ny fanampiana. Fototana : %s ms\n'%(d)


    def _to_unicode(self, string):
        try:
            string = unicode(string, 'latin1')
        except TypeError:
            string = unicode(string)
        finally:
            return string


    def do_commit(self):
        if verbose: print "manavao ny DB..."
        self.DB.connect.commit()


    def exists(self, entry, lang='', POS=''):
        """Checks if entry exists in database"""
        #TODO: harmonise encoding to ease detection in DB
        #t0 = datetime.datetime.now()
        orig_entry = entry
        listencodings = ['latin1', 'cp850', 'cp1252', 'utf8']
        for encoding in listencodings:
            try:
                entry = entry.decode(encoding)
            except UnicodeError:
                pass
                #entry = unicode(entry)

            #OLD VERSION USING DB ACCESS
            conditions = {'teny': entry,
                          'famaritana_fiteny':self.famaritana_fiteny} #see explanation in "set_contentlanguage(ISOcode)"

            if POS: conditions['karazany']=POS
            if lang: conditions['fiteny']=lang
            rep = self.DB.read(conditions, ' teny ') #execution of SQL
            if rep :
                #if verbose: print "ct. encding : %s"%encoding
                return True
            else:
                entry = orig_entry
                continue

        #if verbose: print "ct. encding : %s (all other failed)"%encoding
        return False



    def translate(self, word, language='fr'):
        """gives the translation of the given word in the given language.
           Returns [translation, ...]. All strings are Unicode objects."""
        if type(word) is not unicode:
            try:
                word = word.decode('utf8')
            except UnicodeEncodeError:
                word = word.decode('latin1')
        qresult = self.DB.raw_query(u"select mg from data_botjagwar.%s_mg where %s='%s'"
                                    % (language,language, word.replace(u"'",u"\\'")))
        translations = []
        for translation in qresult:
            translations.append(translation)
        if not translations: # No translation has been found in the special disctionary? Look up in the general one!
            qresult2 = self.DB.raw_query(u"select famaritana from data_botjagwar.teny where fiteny='%s' and teny='%s'"
                                         % (language, word.replace(u"'",u"\\'")))
            for translation in qresult2:
                translation = translation[0]
                for char in (u'[]'):
                    translation = translation.replace(char, '')
                for t in translation.split(','):  # Translation in this dictionary are comma-separated...
                    translations.append( (t.strip(),) )

        tstring = u""
        for translation in translations:
            try:
                tstring += u"[[%s]], "%translation[0].decode("utf8")
            except UnicodeDecodeError:
                tstring += u"[[%s]], "%translation[0].decode("latin1")

        tstring = tstring.strip(u", ")
        return tstring


class SynonymsDatabase(object):
    def __init__(self):
        pass

import datetime
""" TESTS FUNCTIONS"""
wdb = WordDatabase()

def exists(tinput):
    t0 = datetime.datetime.now()
    e =tinput
    e.encode('cp1252')

    if verbose: print 'teny %d'%len(tinput)

    if verbose: print wdb.exists(tinput)
    t1 = datetime.datetime.now()
    dt = t1-t0
    d = dt.seconds*1000+dt.microseconds/1000
    if verbose: print 'chrono : %s ms'%(d)
    if verbose: print 'resp : ', tinput

def Gettranslation():
    r = wdb.translate(u"May", "en")
    ret = []
    for item in r:
        ret.append( (item[3], item[5], item[2]) )
    if verbose: print ret

def readDB():
    db = Database('localhost', 'root', '')
    if verbose: print db.read()


def upload_batch(splitter="-->"):
    import entryprocessor
    EP = entryprocessor.process_enwikt()
    for line in file("data/Eng-mlg.txt", "r").readlines():
        entries = line.split()
        if len(entries)<2: continue
        eng = entries[0].strip()
        mlg = entries[1].strip()
        Page = wikipedia.Page(wikipedia.getSite("en", "wiktionary"), eng)
        EP.process(Page)
        if not Page.exists():
            continue
        detected_entries = EP.getall()
        POS = ""
        for entry in detected_entries:
            if entry[2] != 'en':
                continue
            else:
                POS = entry[1]
                if not wdb.exists(Page.title(), 'en'):
                    if verbose: wikipedia.output(u"'%s' is not detected or non-existent"%Page.title())
                    wdb.append(Page.title(), mlg, POS, 'en')
                else:
                    if verbose: wikipedia.output(u"'%s' already exists in DB"%Page.title())



def loopaddition(**kwargs):
    while 1:
        try:
            print "Enter your entries with the following format : word / language ISO code / definition/translation / POS:"
            line = raw_input().decode(sys.stdout.encoding)
            line = line.encode('utf8')
            line = line.split('/')
            #entry, definition, pos, language

            if not wdb.exists(line[0].strip(), line[1].strip()):
                if verbose: print "not detected or non-existent"
                wdb.append(line[0].strip(),
                           line[2].strip(),
                           line[3].strip(),
                           line[1].strip())
            else:
                if verbose: print "Already exists in DB"
        except IndexError:
            if verbose: print "Sorry. Try again."
        except KeyboardInterrupt:
            if verbose: print "Bye!"
            break

if __name__=='__main__':
    import sys
    #Test()
    #===========================================================================
    # while 1:
    #     e = raw_input(":>")
    #     e = unicode(e, 'cp850')
    #     exists(e)
    #===========================================================================
    argsdict = {
        'loop-addition':loopaddition,
        'upload-batch':upload_batch,
    }
    print 'BJDBMODULE', sys.argv
    verbose = True
    if len(sys.argv) > 1:
        try:
            argsdict[sys.argv[1]]()
        except KeyError:
            print "Ireo avy ireo argiomenta azo ampiasaina:"
            for k in argsdict.keys():
                print k

