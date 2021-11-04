import requests

from api.servicemanager.pgrest import StaticBackend, BackendError

backend = StaticBackend()


def get_mapped_template_in_database(title, target_language='mg'):
    print('get_mapped_template_in_database', title)
    response = requests.get(backend.backend + '/template_translations', params={
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


def add_translated_title(title, translated_title, source_language='en', target_language='mg'):
    print('add_translated_title', title, translated_title)
    response = requests.post(backend.backend + '/template_translations', json={
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

    for ref in references:
        if ref.strip().startswith('{{'):
            if '|' in ref:
                title = ref[2:ref.find('|', 3)]
            else:
                title = ref[2:ref.find('}}', 3)]

            if use_postgrest == 'automatic':
                try:
                    online = True if backend.backend else False
                except BackendError:
                    online = False
            else:
                assert isinstance(use_postgrest, bool)
                online = use_postgrest

            if online:
                translated_title = get_mapped_template_in_database(title, target_language=target)
            else:
                translated_title = None

            if translated_title is None:
                if 'R:' in title[:3]:
                    translated_title = title[:3].replace('R:', 'Tsiahy:') + title[3:]

            if online:
                add_translated_title(title, translated_title, source_language=source, target_language=target)

            translated_reference = ref.replace(title, translated_title)
        else:
            translated_reference = ref
        translated_references.append(translated_reference)

    return translated_references
