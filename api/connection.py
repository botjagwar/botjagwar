from api.metaclass import SingletonMeta as Singleton


class SQLConnection(object):
    instance = None
    server = None
    user = None
    password = None


class SQLConnectionError(Exception):
    pass


class MicrosoftSQLConnection(SQLConnection):
    __metaclass__ = Singleton

    def __init__(self):
        try:
            import pymssql
        except ImportError as exception:
            raise SQLConnectionError(
                "No pymssql found. Please install it"
            ) from exception

        params = {
            "database": self.instance,
            "host": self.server,
            "user": self.user,
            "password": self.password,
        }

        self.connection = pymssql.connect(**params)

    @classmethod
    def connect(
        cls,
        instance=None,
        server=None,
        user="default_user",
        password="default_password",
    ):
        cls.instance = instance
        cls.server = server
        cls.password = password
        cls.user = user
        return cls()


class PostgreSQLConnection(SQLConnection):
    __metaclass__ = Singleton

    def __init__(self):
        import psycopg2

        params = {
            "database": self.instance,
            "user": self.user,
            "password": self.password,
            "host": self.server,
            "port": 5432,
        }
        self.connection = psycopg2.connect(**params)

    def __del__(self):
        self.connection.close()

    @classmethod
    def connect(cls, instance=None, server=None, user="botjagwar", password="isa"):
        cls.instance = instance
        cls.server = server
        cls.password = password
        cls.user = user
        return cls()
