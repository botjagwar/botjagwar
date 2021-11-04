from random import randint

from api.config import BotjagwarConfig

config = BotjagwarConfig()


class BackendError(Exception):
    pass


class Backend(object):
    postgrest = config.get('postgrest_backend_address')

    def check_postgrest_backend(self):
        if not self.postgrest:
            raise BackendError(
                'No Postgrest defined. '
                'set "postgrest_backend_address" to use this. '
                'Expected service port is 8100'
            )


class StaticBackend(Backend):
    @property
    def backend(self):
        self.check_postgrest_backend()
        return 'http://' + self.postgrest + ':8100'


class DynamicBackend(Backend):
    backends = ["http://" + Backend.postgrest + ":81%s" %
                (f'{i}'.zfill(2)) for i in range(16)]

    @property
    def backend(self):
        self.check_postgrest_backend()
        bkd = self.backends[randint(0, len(self.backends) - 1)]
        return bkd
