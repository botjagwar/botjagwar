from random import randint


class StaticBackend(object):
    @property
    def backend(self):
        return 'http://localhost:8100'


class DynamicBackend(object):
    backends = ["http://localhost:81%s" % (f'{i}'.zfill(2)) for i in range(16)]

    @property
    def backend(self):
        bkd = self.backends[randint(0, len(self.backends)-1)]
        return bkd
