import requests

from api.servicemanager.pgrest import StaticBackend, BackendError


class PostgrestTemplateTranslationHelper(object):
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


def translate_references(references: list, source='en', target='mg', use_postgrest: [bool, str] = 'automatic') -> list:
    """Translates reference templates"""
    translated_references = []
    postgrest = PostgrestTemplateTranslationHelper(use_postgrest)

    for ref in references:
        if ref.strip().startswith('{{'):
            if '|' in ref:
                title = ref[2:ref.find('|', 3)]
            else:
                title = ref[2:ref.find('}}', 3)]

            translated_title = postgrest.get_mapped_template_in_database(title, target_language=target)

            if translated_title is None:
                if 'R:' in title[:3]:
                    translated_title = title[:3].replace('R:', 'Tsiahy:') + title[3:]

            postgrest.add_translated_title(title, translated_title, source_language=source, target_language=target)
            translated_reference = ref.replace(title, translated_title)
        else:
            translated_reference = ref
        translated_references.append(translated_reference)

    return translated_references
