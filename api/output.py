import json
import logging

from aiohttp import ClientSession
from aiohttp.web_exceptions import HTTPOk

from api.decorator import retry_on_fail
from api.servicemanager import DictionaryServiceManager
from database.exceptions.http import WordAlreadyExistsException
from object_model.word import Entry

log = logging.getLogger(__name__)
verbose = False

dictionary_service = DictionaryServiceManager()
USER_DATA = 'user_data/entry_translator'
URL_HEAD = dictionary_service.get_url_head()


class Output(object):
    def __init__(self):
        pass

    @retry_on_fail([Exception], 5, .5)
    async def db(self, info: Entry):
        """updates database"""
        async with ClientSession() as client_session:
            # Attempt creation
            log.debug('Attempting entry creation')
            async with client_session.post(
                    URL_HEAD + '/entry/%s/create' % info.language,
                    data=json.dumps(info.to_dict())) as creation_response:
                # Update if word already exists
                if creation_response.status == WordAlreadyExistsException.status_code:
                    read_response = await client_session.get(
                        URL_HEAD + '/entry/%s/%s' % (info.language, info.entry)
                    )
                    jdata = await read_response.json()
                    entry_json = [
                        w for w in jdata
                        if w['part_of_speech'] == info.part_of_speech][0]
                    entry_json['entry'] = info
                    await client_session.put(
                        URL_HEAD + '/entry/%s/edit' % entry_json['id'],
                        data=json.dumps(entry_json))

        log.debug('Attempting commit')
        async with ClientSession() as client_session:
            # Commit the whole thing
            async with client_session.post(URL_HEAD + '/commit') as commit_response:
                if commit_response.status_code != HTTPOk.status_code:
                    log.debug("Database commit failed: %d" % commit_response.status_code)

    def batchfile(self, info: Entry):
        "return batch format (see doc)"
        string = "%(entry)s -> %(entry_definition)s -> %(part_of_speech)s -> %(language)s\n" % info.properties
        return string

    def wikipage(self, info: Entry, link=True):
        "returns wikipage string"
        additional_note = ""
        data = info.to_dict()
        if 'origin_wiktionary_page_name' in data and 'origin_wiktionary_edition' in data:
            additional_note = " {{dikantenin'ny dikanteny|%(origin_wiktionary_page_name)s|%(origin_wiktionary_edition)s}}\n" % data

        s = """
=={{=%(language)s=}}==
{{-%(part_of_speech)s-|%(language)s}}
'''{{subst:BASEPAGENAME}}''' {{fanononana X-SAMPA||%(language)s}} {{fanononana||%(language)s}}""" % data
        if link:
            s += "\n# %s" % ', '.join(['[[%s]]' % (d) for d in info.entry_definition])
        else:
            s += "\n# %s" % ', '.join(['%s' % (d) for d in info.entry_definition])

        s = s + additional_note % info.properties
        try:
            return s
        except UnicodeDecodeError:
            return s.decode('utf8')
