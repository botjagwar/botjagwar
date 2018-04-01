import time
from api.decorator import threaded


class Monitoring:
    def check(self):
        raise NotImplementedError()

    def on_fail(self):
        pass

    def on_ok(self):
        pass

    def on_clean(self):
        pass


class WiktionaryIrcMonitoring(Monitoring):
    def check(self):
        print('monitor_wiktionary_irc')
        time.sleep(1)


class NetworkMonitoring(Monitoring):
    def check(self):
        print('diagnose_network_status')
        time.sleep(1)


class MonitoringApplication:
    def __init__(self):
        self.enable_monitoring = True
        self.functions = []

    def add_component(self, classe: Monitoring):
        self.functions.append(classe)

    @threaded
    def run(self):
        while self.enable_monitoring:
            print('---')
            for Classe in self.functions:
                objekt = Classe()
                try:
                    objekt.check()
                except Exception:
                    objekt.on_fail()
                else:
                    objekt.on_ok()
                finally:
                    objekt.on_clean()
