import time
from subprocess import Popen

import requests

from api.decorator import threaded


class ProcessManager:
    """
    ProcessManager provides an abstract API to spawn and kills processes.
    The process is spawned on a call to spawn_backend() method and is terminated
    upon object destruction.
    """
    program_name = None
    spawned_backend_process = None

    def __del__(self):
        self.spawned_backend_process.terminate()

    def get_specific_arguments(self):
        """
        Override this method and return a list of strings if you want to give program-specific
        arguments. An empty list means that no specific arguments are needed.
        :return:
        """
        return []

    @threaded
    def spawn_backend(self, *args):
        self.specific_args = self.get_specific_arguments() # XXX: requires a list of str objects
        proc_params = ['python3.6', self.program_name] + self.specific_args + list(args)
        self.spawned_backend_process = Popen(proc_params)
        with open('/tmp/%s.pid' % self.program_name, 'w') as f:
            f.write(str(self.spawned_backend_process.pid))


class ServiceManager(ProcessManager):
    """
    ServiceManager provides a minimally abstract APIs to spawn and despawn aiohttp RESTful services.
    """
    backend_address = 'localhost'
    port = 8888
    scheme = 'http'


    def get_specific_arguments(self):
        return ['-p', str(self.port)]

    def set_backend_address(self, addr):
        """
        Hit on the backend that is not on the local computer.
        :return:
        """
        self.backend_address = addr


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