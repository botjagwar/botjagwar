from random import randint

import requests

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


class PostgrestBackend(object):
    backend = StaticBackend()


class PostgrestTemplateTranslationHelper(PostgrestBackend):
    """
    Controller to fetch already-defined template name mappings
    from the Postgres database through PostgREST.
    """
    backend = StaticBackend()

    def __init__(self, use_postgrest):
        """
        Translate templates
        :param use_postgrest: True or False to fetch on template_translations table.
        Set this argument to 'automatic' to use `postgrest_backend_address` only if it's filled
        """
        if use_postgrest == 'automatic':
            try:
                self.online = True if self.backend.backend else False
            except BackendError:
                self.online = False
        else:
            assert isinstance(use_postgrest, bool)
            self.online = use_postgrest

    def get_mapped_template_in_database(self, title, target_language='mg'):
        if self.online:
            return self.postgrest_get_mapped_template_in_database(title, target_language)

    def add_translated_title(self, title, translated_title, source_language='en', target_language='mg'):
        if self.online:
            return self.postgrest_add_translated_title(
                title, translated_title, source_language, target_language)

    def postgrest_get_mapped_template_in_database(self, title, target_language='mg'):
        response = requests.get(self.backend.backend + '/template_translations', params={
            'source_template': title,
            'target_language': target_language
        })
        data = response.json()
        if response.status_code == 200: # HTTP OK
            if 'target_template' in data:
                return data['target_template']

        if response.status_code == 404: # HTTP Not found
            return None
        if response.status_code == 500: # HTTP server error:
            raise BackendError(f'Unexpected error: HTTP {response.status_code}; ' + response.text)

    def postgrest_add_translated_title(self, title, translated_title, source_language='en', target_language='mg'):
        response = requests.post(self.backend.backend + '/template_translations', json={
            'source_template': title,
            'target_template': translated_title,
            'source_language': source_language,
            'target_language': target_language
        })
        print(response.text)
        if response.status_code in (400, 500): # HTTP Bad request or HTTP server error:
            raise BackendError(f'Unexpected error: HTTP {response.status_code}; ' + response.text)

        return None


class JsonDictionary(PostgrestBackend):
    @staticmethod
    def get_word(self, word):
        pass

    @staticmethod
    def get_definition(self):
        pass

    @staticmethod
    def get_additional_data(self):
        pass
