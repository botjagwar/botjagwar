import time
from subprocess import Popen, PIPE
from api.decorator import threaded
import requests


class ServiceManager:
    port = 8000
    scheme = 'http'
    spawned_backend_process = None
    backend_address = 'localhost'
    program_name = None

    def __del__(self):
        self.spawned_backend_process.terminate()

    def set_backend_address(self, addr):
        """
        Hit on the backend that is not on the local computer.
        :return:
        """
        self.backend_address = addr

    @threaded
    def spawn_backend(self, proc_name, *args):
        self.spawned_backend_process = Popen(['python3.6', self.program_name] + list(args), stdin=PIPE, stdout=PIPE)
        self.spawned_backend_process.communicate()

    # Low-level functions to use with high-level functions
    def get(self, route, **kwargs):
        time.sleep(1)
        route = '%s://%s:%d/%s' % (self.scheme, self.backend_address, self.port, route)
        req = requests.get(route, **kwargs)
        return req.json()

    def post(self, route, **kwargs):
        time.sleep(1)
        route = '%s://%s:%d/%s' % (self.scheme, self.backend_address, self.port, route)
        return requests.post(route, **kwargs).json()

    def put(self, route, **kwargs):
        time.sleep(1)
        route = '%s://%s:%d/%s' % (self.scheme, self.backend_address, self.port, route)
        return requests.put(route, **kwargs).json()

    def delete(self, route, **kwargs):
        time.sleep(1)
        route = '%s://%s:%d/%s' % (self.scheme, self.backend_address, self.port, route)
        return requests.delete(route, **kwargs).json()


class EntryTranslatorServiceManager(ServiceManager):
    port = 8000
    program_name = 'entry_translator.py'


class DictionaryServiceManager(ServiceManager):
    port = 8001
    program_name = 'dictionary_service.py'


class LanguageServiceManager(ServiceManager):
    port = 8003
    program_name = 'language_service.py'

    # high-level function
    def get_language(self, language_code):
        result = self.get('language/' + language_code)
        if result is not None:
            return result
        else:
            raise Exception("Language not found")