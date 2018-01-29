
import MySQLdb as db
import pywikibot
from set_database_password import PasswordManager
verbose = True

class Database(object):
    def __init__(self, host='localhost', login='root', passwd=None, dbname=None, table='teny'):
        assert type(host) is str
        assert type(host) is str

        self.pw_manager = PasswordManager()
        if passwd is None:
            self.db_passwd = self.pw_manager.get_password()
        else:
            self.db_passwd = passwd

        self.infos = {
            'host': host,
            'login': login,
            'passwd': self.db_passwd,
            'table': db.escape_string(table)
        }
        self.tablename = 'teny'
        self.connect = db.connect(host, login, self.db_passwd, charset='utf8')
        self.cursor = self.connect.cursor()
        if dbname is None:
            dbname = "data_botjagwar"
        self.infos['DB'] = dbname

        self.querycount = 0
        self.autocommit = True

        self.words = []

    def __del__(self):
        self.cursor.close()

    def close(self):
        self.cursor.close()

    def load(self):
        sqlreq = "select * from `%(DB)s`.`%(table)s` WHERE 1" % self.infos
        return self.raw_query(sqlreq)

    def set_dbname(self, dbname):
        assert type(dbname) is str
        """Set the current database we're working on"""
        self.infos['DB'] = dbname

    def set_table(self, table):
        assert type(table) is str
        """Set the current table we're working on"""
        self.infos['table'] = table

    def insert(self, values_dict, dry_run=False):
        """Insert in database values in values_dict"""
        if dry_run:
            return
        if isinstance(values_dict, list):
            self._insert_many(values_dict)
        elif isinstance(values_dict, dict):
            self._insert_one(values_dict)

    def _do_insert(self, values_dict):
        print(values_dict)
        sql = "insert into `%(DB)s`.`%(table)s` (" % self.infos
        for i in values_dict:
            i = db.escape_string(i.encode('utf8'))
            i = i.decode('utf8')
            sql += "`%s`," % i
        sql = sql.strip(',')
        sql += ") values ("
        for key, value in list(values_dict.items()):
            if value is not None:
                value = db.escape_string(value.encode('utf8'))
                value = value.decode('utf8')
                sql += "'%s', " % value
            else:
                sql += "NULL,"
        sql = sql.strip(', ')
        sql += ")"
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

    def _insert_one(self, values_dict):
        self._do_insert(values_dict)
        if self.autocommit:
            self.connect.commit()

    def _insert_many(self, list_values_dict):
        for values_dict in list_values_dict:
            self._do_insert(values_dict)
        if self.autocommit:
            self.connect.commit()

    def _action(self, conditions={}, initstring=str(), operand='='):
        """action for SELECT or DELETE statements, specified by initstring"""
        sql = initstring
        if not conditions:
            sql += "from `%(DB)s`.`%(table)s` WHERE `fiteny`='mg'" % self.infos
        elif conditions == {'fiteny': 'REHETRA'}:
            sql += "from `%(DB)s`.`%(table)s`"
        else:
            sql += "from `%(DB)s`.`%(table)s` WHERE " % self.infos
            for key, value in list(conditions.items()):
                value = value.encode('utf8')     # Yay!
                value = db.escape_string(value)  # Python 2
                value = value.decode('utf8')     # for the win!
                sql += "`%s` %s '%s' AND " % (key, operand, value)

            sql = sql.strip('AND ')

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
                    pywikibot.output('\03{red}%s\03{default}' % sql)
                return tuple()
        except Exception as e:
            if verbose:
                pywikibot.output('HADISOANA ANATY: \03{red}%s\03{default}' % sql)
            raise e  # Unhandled Exception
        finally:
            return rep


    def read(self, conditions={}, select='*'):
        """Read data from the current DB"""
        return self._action(conditions, "select %s " % select, '=')

    def read_all(self):
        return self.raw_query("select * from `%(DB)s`.`%(table)s`" % self.infos)

    def update(self, conditions, newvalues_dict):
        "Update SQL line with new values following conditions in conditions"
        raise NotImplementedError()

    def delete(self, conditions=False):
        "Delete data from the DB"
        return self._action(conditions, "delete ")

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
