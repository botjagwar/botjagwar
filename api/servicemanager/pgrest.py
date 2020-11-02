from random import randint


class StaticBackend(object):
    @property
    def backend(self):
        return 'http://10.0.0.10:8100'


class DynamicBackend(object):
    backends = ["http://10.0.0.10:81%s" % (f'{i}'.zfill(2)) for i in range(16)]

    @property
    def backend(self):
        return self.backends[randint(0, len(self.backends)-1)]
