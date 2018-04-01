from aiohttp import ClientSession
import json

from database.exceptions.http import WordAlreadyExistsException

verbose = False

USER_DATA = 'user_data/entry_translator'
URL_HEAD = 'http://localhost:8001'


class Output(object):
    def __init__(self):
        pass

    async def db(self, info):
        """updates database"""
        definitions = [{
            'definition': entry_definition,
            'definition_language': 'mg',
        } for entry_definition in info.entry_definition]
        entry = {
            'word': info.entry,
            'language': info.language,
            'part_of_speech': info.part_of_speech,
            'definitions': definitions
        }
        async with ClientSession() as client_session:
            async with client_session.post( URL_HEAD + '/entry/%s/create' % info.language, data=json.dumps(entry)) as resp:
                if resp.status == WordAlreadyExistsException.status_code:
                    resp = await client_session.get(
                        URL_HEAD + '/entry/%s/%s' % (info.language, info.entry)
                    )
                    jdata = await resp.json()
                    entry_json = [w for w in jdata
                                  if w['part_of_speech'] == info.part_of_speech][0]
                    entry_json['entry'] = entry
                    async with client_session.post(
                        URL_HEAD + '/entry/%s/edit' % entry_json['id'], data=json.dumps(entry_json)):
                        pass

            async with client_session.get(URL_HEAD + '/commit') as resp:
                pass

    def batchfile(self, info):
        "return batch format (see doc)"
        string = "%(entry)s -> %(entry_definition)s -> %(part_of_speech)s -> %(language)s\n" % info.properties
        return string

    def wikipage(self, info):
        "returns wikipage string"
        additional_note = ""
        if 'origin_wiktionary_page_name' in info.properties and 'origin_wiktionary_edition' in info.properties:
            additional_note = " {{dikantenin'ny dikanteny|%(origin_wiktionary_page_name)s|%(origin_wiktionary_edition)s}}\n" % info.properties

        s = """
=={{=%(language)s=}}==
{{-%(part_of_speech)s-|%(language)s}}
'''{{subst:BASEPAGENAME}}''' {{fanononana X-SAMPA||%(language)s}} {{fanononana||%(language)s}}""" % info.properties
        s += "\n# %s" % ', '.join(['[[%s]]' % (d) for d in info.entry_definition])
        s = s + additional_note % info.properties
        try:
            return s
        except UnicodeDecodeError:
            return s.decode('utf8')

