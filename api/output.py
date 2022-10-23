import logging

import requests

from api.dictionary.exceptions.http import WordAlreadyExists
from api.model.word import Entry
from api.page_renderer import WikiPageRendererFactory
from api.servicemanager import DictionaryServiceManager
from api.servicemanager.pgrest import StaticBackend

log = logging.getLogger(__name__)
verbose = False

dictionary_service = DictionaryServiceManager()
USER_DATA = 'user_data/entry_translator'
URL_HEAD = dictionary_service.get_url_head()


class Output(object):
    content_language = 'mg'

    def __init__(self, content_language='default'):
        if content_language != 'default':
            self.content_language = content_language

        self.wikipage_renderer = WikiPageRendererFactory(self.content_language)()  # pylint: disable=E1102

    # @retry_on_fail([Exception], 5, .5)
    def dictionary_service_update_database(self, info: Entry):
        """updates database"""
        # Adapt to expected format
        log.info(info.serialise())
        definitions = [{
            'definition': d,
            'definition_language': self.content_language
        } for d in info.definitions]
        data = {
            'definitions': definitions,
            'word': info.entry,
            'part_of_speech': info.part_of_speech,
            'translation_method': info.translation_method if hasattr(
                info,
                'translation_method') else None}
        response = dictionary_service.post(
            'entry/%s/create' %
            info.language, json=data)
        if response.status_code == WordAlreadyExists.status_code:
            word_response = dictionary_service.get(
                'entry/%s/%s' %
                (info.language, info.entry)).json()  # fetch its ID
            edit_response = dictionary_service.put(
                'entry/%d/edit' %
                word_response[0]['id'],
                json=data)  # edit using its ID
            if edit_response.status_code == WordAlreadyExists.status_code:
                log.debug(
                    '%s [%s] > Attempted to create an already-existing entry.' %
                    (info.entry, info.language))
            elif edit_response.status_code != 200:
                log.error(
                    '%s [%s] > Entry update failed (%d).' %
                    (info.entry, info.language, edit_response.status_code))

    def postgrest_update_database(self, info: Entry):
        raise NotImplementedError()

    @staticmethod
    def postgrest_add_translation_method(infos: Entry):
        backend = StaticBackend().backend
        data = {
            'word': 'eq.' + infos.entry,
            'language': 'eq.' + infos.language,
            'part_of_speech': 'eq.' + infos.part_of_speech,
            'limit': '1'

        }
        # log.debug('get /word', data)
        word_id = requests.get(backend + '/word', params=data).json()
        if len(word_id) > 0:
            if 'id' in word_id[0]:
                word_id = word_id[0]['id']
            else:
                raise TypeError(word_id)
        else:
            return
        if hasattr(infos, 'translation_methods'):
            for definition, methods in infos.translation_methods.items():
                data = {
                    'definition': 'eq.' + definition,
                    'definition_language': 'eq.mg',
                    'limit': '1'
                }
                defn_id = requests.get(
                    backend + '/definitions',
                    params=data).json()
                if len(defn_id) > 0 and 'id' in defn_id:
                    defn_id = defn_id[0]['id']
                else:
                    return

                for method in methods:
                    data = {
                        'word': word_id,
                        'definition': defn_id,
                        'translation_method': method,
                    }
                    log.debug('post /translation_method' + str(data))
                    requests.post(backend + '/translation_method', json=data)

    @staticmethod
    def sqlite_add_translation_method(infos: Entry):
        raise NotImplementedError()

    db = dictionary_service_update_database
    add_translation_method = postgrest_add_translation_method

    def batchfile(self, info: Entry):
        "return batch format (see doc)"
        string = "%(entry)s -> %(entry_definition)s -> %(part_of_speech)s -> %(language)s\n" % info.serialise()
        return string

    def wikipage(self, info: Entry, link=True):
        "returns wikipage string"
        return self.wikipage_renderer.render(info)

    def wikipages(self, infos: list, link=True):
        ret_page = ''

        # Consolidate by language
        entries_by_language = {}
        for entry in infos:
            if entry.language in entries_by_language:
                if entry not in entries_by_language[entry.language]:
                    entries_by_language[entry.language].append(entry)
            else:
                entries_by_language[entry.language] = [entry]

        # render
        log.debug(entries_by_language)
        for language, entries in entries_by_language.items():
            for entry in entries:
                rendered = self.wikipage_renderer.render(entry).strip()
                language_section = rendered.split('\n')[0]
                if ret_page.find(language_section) == -1:
                    if rendered:
                        ret_page += rendered + "\n"
                else:
                    ret_page = ret_page.replace(
                        language_section, rendered) + "\n"

        ret_page = ret_page.replace('\n\n\n', '\n\n')
        return ret_page.strip()

    def delete_section(self, section_name, wiki_page):
        return self.wikipage_renderer.delete_section(section_name, wiki_page)
