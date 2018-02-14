from aiohttp import ClientSession
import json

from database.http import (
    WordAlreadyExistsException
)

verbose = False


USER_DATA = 'user_data/entry_translator'
URL_HEAD = 'http://localhost:8001'


class Output(object):
    def __init__(self, output_batchfile=USER_DATA + "/translate_batch.txt"):
        self.output_batchfile = open(output_batchfile, 'a')
        self.client_session = ClientSession()

    async def db(self, info):
        """updates database"""
        definitions = {
            'definition': info.entry_definition,
            'definition_language': 'mg',
        }
        entry = {
            'word': info.entry,
            'language': info.language,
            'part_of_speech': info.part_of_speech,
            'definitions': [definitions]
        }
        resp = await self.client_session.post(
            URL_HEAD + '/entry/%s/create' % info.language,
            data=json.dumps(entry)
        )
        if resp.status == WordAlreadyExistsException.status_code:
            resp = await self.client_session.get(
                URL_HEAD + '/entry/%s/%s' % (info.language, info.entry)
            )
            entry_json = [w for w in json.loads(await resp.text())
                          if w['part_of_speech'] == info.part_of_speech][0]
            entry_json['entry'] = entry
            resp = await self.client_session.post(
                URL_HEAD + '/entry/%s/edit' % entry_json['id'],
                data=json.dumps(entry_json)
            )

        await self.client_session.get(URL_HEAD + '/commit')

    def batchfile(self, info):
        "return batch format (see doc)"
        string = "%(entry)s -> %(entry_definition)s -> %(part_of_speech)s -> %(language)s\n" % info.properties
        return string
        
    def wikipage(self, info):
        "returns wikipage string"
        additional_note = ""
        if 'origin_wiktionary_page_name' in info.properties and 'origin_wiktionary_edition' in info.properties:
            additional_note = "{{dikantenin'ny dikanteny|%(origin_wiktionary_page_name)s|%(origin_wiktionary_edition)s}}\n" % info.properties

        s = """
=={{=%(language)s=}}==
{{-%(part_of_speech)s-|%(language)s}}
'''{{subst:BASEPAGENAME}}''' {{fanononana X-SAMPA||%(language)s}} {{fanononana||%(language)s}}
# %(entry_definition)s"""%info.properties
        s = s + additional_note % info.properties
        try:
            return s
        except UnicodeDecodeError:
            return s.decode('utf8')

