import logging

from api.decorator import retry_on_fail
from api.page_renderer import WikiPageRendererFactory
from api.servicemanager import DictionaryServiceManager
from database.exceptions.http import WordAlreadyExistsException
from object_model.word import Entry

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

    @retry_on_fail([Exception], 5, .5)
    def db(self, info: Entry):
        """updates database"""
        # Adapt to expected format
        log.info(info.to_dict())
        definitions = [{
                'definition': d,
                'definition_language': self.content_language
        } for d in info.entry_definition]
        data = {
            'definitions': definitions,
            'word': info.entry,
            'part_of_speech': info.part_of_speech,
            'translation_method': info.translation_method if hasattr(info, 'translation_method') else None
        }
        response = dictionary_service.post('entry/%s/create' % info.language, json=data)
        if response.status_code == WordAlreadyExistsException.status_code:
            word_response = dictionary_service.get('entry/%s/%s' % (info.language, info.entry)).json()  # fetch its ID
            edit_response = dictionary_service.put('entry/%d/edit' % word_response[0]['id'], json=data)  # edit using its ID
            if edit_response.status_code == WordAlreadyExistsException.status_code:
                log.debug('%s [%s] > Attempted to create an already-existing entry.' % (info.entry, info.language))
            elif edit_response.status_code != 200:
                log.error('%s [%s] > Entry update failed (%d).' % (info.entry, info.language, edit_response.status_code))

    def batchfile(self, info: Entry):
        "return batch format (see doc)"
        string = "%(entry)s -> %(entry_definition)s -> %(part_of_speech)s -> %(language)s\n" % info.to_dict()
        return string

    def wikipage(self, info: Entry, link=True):
        "returns wikipage string"
        self.wikipage_renderer = WikiPageRendererFactory(self.content_language)()
        return self.wikipage_renderer.render(info, link=link)
