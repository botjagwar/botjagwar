from random import randint

from api.config import BotjagwarConfig

config = BotjagwarConfig()

ADDR = config.get('postgrest_backend_address')


class StaticBackend(object):
    @property
    def backend(self):
        return 'http://' + ADDR + ':8113'


class DynamicBackend(object):
    backends = ["http://" + ADDR + ":81%s" % (f'{i}'.zfill(2)) for i in range(16)]

    @property
    def backend(self):
        bkd = self.backends[randint(0, len(self.backends)-1)]
        return bkd


