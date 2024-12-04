import logging
import os
import time
from signal import SIGTERM
from subprocess import Popen
from typing import List

import requests
from requests import Response

from api.decorator import threaded, retry_on_fail
from api.config import BotjagwarConfig

log = logging.getLogger(__name__)

config = BotjagwarConfig()


class ProcessManager:
    """
    ProcessManager provides an abstract API to spawn and kills processes.
    The process is spawned on a call to spawn_backend() method and is terminated
    upon object destruction.
    """

    interpreter_name = "python3"
    program_name = None
    spawned_backend_process = None
    kill_if_exists = False

    def __del__(self):
        if self.spawned_backend_process:
            self.spawned_backend_process.terminate()
            path = "/tmp/%s.pid" % self.program_name
            os.system("rm %s" % path)  # Process has died, pid file is irrelevant

    def get_specific_arguments(self) -> List[str]:
        """
        Override this method and return a list of strings if you want to give program-specific
        arguments. An empty list means that no specific arguments are needed.
        :return:
        """
        return []

    @threaded
    def spawn_backend(self, *args):
        pid = None
        path = "/tmp/%s.pid" % self.program_name
        try:
            with open(path, "r") as f:
                pid = int(f.read())
        except FileNotFoundError:
            pass

        if pid is not None:
            try:
                log.info("Checking the existence of the process %d" % pid)
                os.kill(pid, 0)
            except OSError:
                log.info("Process no longer exists... removing the pid file")
            else:
                log.info("A process exists...")
                if self.kill_if_exists:
                    log.info("Sending SIGTERM to the process...")
                    os.kill(pid, SIGTERM)

        os.system("rm %s" % path)  # Process has died, pid file is irrelevant
        time.sleep(0.5)
        # XXX: requires a list of str objects
        self.specific_args = self.get_specific_arguments()
        proc_params = (
            [self.interpreter_name, self.program_name] + self.specific_args + list(args)
        )

        self.spawned_backend_process = Popen(proc_params)
        with open(path, "w") as f2:
            f2.write(str(self.spawned_backend_process.pid))


class ServiceManager(ProcessManager):
    """
    ServiceManager provides a minimally abstract APIs to spawn and despawn aiohttp RESTful services.
    """

    service_name = "service_manager"
    port = 8888
    scheme = "http"

    def __init__(self):
        self._address = None

    @property
    def backend_address(self):
        if self._address:
            return self._address

        try:
            self._address = config.get("backend_address", self.service_name)
            print(
                f"Success getting backend address for {self.service_name}: {self._address}"
            )
            return self._address
        except Exception as unknown_error:
            print(
                f"Error {unknown_error.__class__.__name__} trying to get backend address from configuration."
                f" Using localhost."
            )
            return "localhost"

    def get_specific_arguments(self) -> List[str]:
        return ["-p", str(self.port)]

    def set_backend_address(self, addr):
        """
        Hit on the backend that is not on the local computer.
        :return:
        """
        self.backend_address = addr

    def get_url_head(self):
        return "%s://%s:%d" % (self.scheme, self.backend_address, self.port)

    # Low-level functions to use with high-level functions
    @retry_on_fail([Exception], 5, 0.5)
    def get(self, route, **kwargs):
        route = "%s://%s:%d/%s" % (self.scheme, self.backend_address, self.port, route)
        return requests.get(route, **kwargs)

    @retry_on_fail([Exception], 5, 0.5)
    def post(self, route, **kwargs):
        route = "%s://%s:%d/%s" % (self.scheme, self.backend_address, self.port, route)
        return requests.post(route, **kwargs)

    @retry_on_fail([Exception], 5, 0.5)
    def put(self, route, **kwargs):
        route = "%s://%s:%d/%s" % (self.scheme, self.backend_address, self.port, route)
        return requests.put(route, **kwargs)

    @retry_on_fail([Exception], 5, 0.5)
    def delete(self, route, **kwargs):
        route = "%s://%s:%d/%s" % (self.scheme, self.backend_address, self.port, route)
        return requests.delete(route, **kwargs)


class EntryTranslatorServiceManager(ServiceManager):
    port = 8000
    service_name = "entry_translator"
    program_name = "entry_translator.py"
    kill_if_exists = False


class DictionaryServiceManager(ServiceManager):
    port = 8001
    service_name = "dictionary_service"
    program_name = "dictionary_service.py"
    kill_if_exists = False

    def create_entry(self, language, entry):
        return self.post("entry/%s/create" % language, json=entry)


class LanguageServiceManager(ServiceManager):
    port = 8003
    program_name = "language_service.py"
    kill_if_exists = False

    # high-level function
    def get_language(self, language_code) -> Response:
        result = self.get("language/" + language_code)

        for i in range(10):
            if result is not None:
                return result

            print(result)
            time.sleep(0.5)
            result = self.get("language/" + language_code)

        raise Exception("Language not found: " + language_code)
