import time
from subprocess import Popen

import requests

from api.decorator import threaded


class ServiceManager:
    backend_address = 'localhost'
    port = 8888
    program_name = None
    scheme = 'http'
    spawned_backend_process = None

    def __del__(self):
        self.spawned_backend_process.terminate()

    def set_backend_address(self, addr):
        """
        Hit on the backend that is not on the local computer.
        :return:
        """
        self.backend_address = addr

    @threaded
    def spawn_backend(self, *args):
        self.specific_args = ['-p', str(self.port)]  # XXX: requires a list of str objects
        proc_params = ['python3.6', self.program_name] + self.specific_args + list(args)
        print (proc_params)
        self.spawned_backend_process = Popen(proc_params)
        with open('/tmp/%s.pid' % self.program_name, 'w') as f:
            f.write(str(self.spawned_backend_process.pid))

    # Low-level functions to use with high-level functions
    def get(self, route, **kwargs):
        time.sleep(1)
        route = '%s://%s:%d/%s' % (self.scheme, self.backend_address, self.port, route)
        return requests.get(route, **kwargs)

    def post(self, route, **kwargs):
        time.sleep(1)
        route = '%s://%s:%d/%s' % (self.scheme, self.backend_address, self.port, route)
        return requests.post(route, **kwargs)

    def put(self, route, **kwargs):
        time.sleep(1)
        route = '%s://%s:%d/%s' % (self.scheme, self.backend_address, self.port, route)
        return requests.put(route, **kwargs)

    def delete(self, route, **kwargs):
        time.sleep(1)
        route = '%s://%s:%d/%s' % (self.scheme, self.backend_address, self.port, route)
        return requests.delete(route, **kwargs)


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