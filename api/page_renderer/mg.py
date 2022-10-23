import re

import requests

from api.config import BotjagwarConfig
from api.model.word import Entry
from .base import PageRenderer


class MGWikiPageRendererError(Exception):
    pass


class MGWikiPageRenderer(PageRenderer):

    def __init__(self):
        super(MGWikiPageRenderer, self).__init__()
        self.config = BotjagwarConfig()
        self._words_to_link = set()

    @property
    def pages_to_link(self):
        if self._words_to_link:
            return self._words_to_link

        try:
            self.fetch_pages_to_link()
        finally:
            return self._words_to_link

    def fetch_pages_to_link(self):
        postgrest_url = self.config.get('postgrest_backend_address')
        url = f'http://{postgrest_url}:8100/word'
        print(url)

        pages = requests.get(url, params={
            'language': f'eq.mg',
            'part_of_speech': f'in.(ana,mat,mpam)',
            'select': f'word',
        })
        print(pages.status_code)
        if pages.status_code != 200:
            raise MGWikiPageRendererError(pages.status_code)
        else:
            self._words_to_link = {p['word'] for p in pages.json() if len(p['word']) > 4}
            print(f'Loading complete! {len(self._words_to_link)} words loaded')
            return self._words_to_link

    def link_if_exists(self, definition_words: list) -> list:
        ret = []
        print(len(self.pages_to_link), definition_words)
        if hasattr(self, 'pages_to_link'):
            assert isinstance(self.pages_to_link, set)
            for word in definition_words:
                word_to_link = word.strip(',')
                if word_to_link in self.pages_to_link:
                    word = word.replace(word_to_link, f'[[{word_to_link}]]')
                    ret.append(word)
                elif word.lower() in self.pages_to_link:
                    word = word.replace(word_to_link, f'[[{word_to_link.lower()}|{word_to_link}]]')
                    ret.append(word)
                else:
                    ret.append(word)
            return ret

        return definition_words

    def render(self, info: Entry, link=True) -> str:
        additional_note = ""
        if info.additional_data is not None:
            if 'origin_wiktionary_page_name' in info.additional_data and 'origin_wiktionary_edition' in info:
                additional_note = " {{dikantenin'ny dikanteny|" + \
                                  f"{info.additional_data['origin_wiktionary_page_name']}" \
                                  f"|{info.additional_data['origin_wiktionary_edition']}" + "}}\n"

        returned_string = self.render_head_section(info)
        returned_string += self.render_definitions(info, link) + additional_note
        returned_string += self.render_pronunciation(info)
        returned_string += self.render_synonyms(info)
        returned_string += self.render_antonyms(info)
        returned_string += self.render_related_terms(info)
        returned_string += self.render_further_reading(info)
        returned_string += self.render_references(info)

        return returned_string + '\n'

    def render_head_section(self, info):
        # Language
        returned_string = "\n=={{=" + f"{info.language}" + "=}}==\n"
        returned_string += self.render_etymology(info)

        # Part of speech
        returned_string += "\n{{-" + f'{info.part_of_speech}-|{info.language}' + "}}\n"

        # Pronunciation
        returned_string += "'''{{subst:BASEPAGENAME}}''' "

        # transcription (if any)
        if info.additional_data is not None:
            if 'transcription' in info.additional_data:
                transcriptions = ', '.join(info.additional_data['transcription'])
                returned_string += f"({transcriptions})"

        return returned_string

    def render_etymology(self, info):
        returned_string = ''
        if info.additional_data is not None and 'etymology' in info.additional_data:
            etymology = info.additional_data['etymology']
            if etymology:
                returned_string += '\n{{-etim-}}\n'
                returned_string += ':' + etymology
            else:
                returned_string += '\n{{-etim-}}\n'
                returned_string += f': {{vang-etim|' + f'{info.language}' + '}}\n'

        return returned_string

    def render_definitions(self, info, link: list):
        returned_string = ''
        trailing_characters_to_exclude_from_link = ',.;:'
        definitions = []
        defn_list = sorted(set(info.definitions))
        if link:
            for d in defn_list:
                if '[[' in d or ']]' in d:
                    definitions.append(d)
                elif len(d.split()) == 1:
                    if d[-1] in trailing_characters_to_exclude_from_link:
                        for trailing_character_to_exclude_from_link in trailing_characters_to_exclude_from_link:
                            if d.endswith(trailing_character_to_exclude_from_link):
                                temp_d = d.strip('.')
                                definitions.append(f'[[{temp_d.lower()}|{temp_d}]].')
                                break
                    else:
                        definitions.append(f'[[{d}]]')
                else:
                    multiword_definitions = self.link_if_exists(d.split())
                    definition = ' '.join(multiword_definitions)
                    definition = definition.replace(' - ', '-')
                    definitions.append(definition)

        else:
            definitions = [f'{d}' for d in defn_list]

        for idx, defn in enumerate(definitions):
            returned_string += "\n# " + defn
            # Examples:
            if info.additional_data and 'examples' in info.additional_data:
                if len(info.additional_data['examples']) > idx:
                    if isinstance(info.additional_data['examples'], list):
                        if len(info.additional_data['examples'][idx]) > 0:
                            for example in info.additional_data['examples'][idx]:
                                returned_string += "\n#* ''" + example + "''"
                    elif isinstance(info.additional_data['examples'], str):
                        returned_string += "\n#* ''" + info.additional_data['examples'][idx] + "''"

        return returned_string

    def render_pronunciation(self, info):
        returned_string = ''
        header_added = False

        # Generic pronunciation section
        if 'pronunciation' in info.additional_data:
            if not header_added:
                returned_string += '\n\n{{-fanononana-}}'
                header_added = True
            if isinstance(info.additional_data['pronunciation'], list):
                for pron in info.additional_data['pronunciation']:
                    returned_string += "\n* " + pron.strip('*').strip()
            else:
                returned_string += "\n* " + info.additional_data['pronunciation'].strip('*').strip()

        # Pronunciation and/or Audio
        if 'audio_pronunciations' in info.additional_data:
            if not header_added:
                returned_string += '\n\n{{-fanononana-}}'
                header_added = True
            for audio in info.additional_data['audio_pronunciations']:
                returned_string += "\n* " + \
                                   '{{audio|' + f'{audio}' + '|' + f'{info.entry}' + '}}'

        # IPA
        if 'ipa' in info.additional_data:
            if not header_added:
                returned_string += '\n\n{{-fanononana-}}'
            for ipa in info.additional_data['ipa']:
                returned_string += "\n* " + \
                                   '{{fanononana|' + f'{ipa}' + '|' + f'{info.language}' + '}}'

        return returned_string

    def render_synonyms(self, info):
        returned_string = ''
        if 'synonyms' in info.additional_data:
            returned_string += '\n\n{{-dika-mitovy-}}'
            for synonym in info.additional_data['synonyms']:
                returned_string += "\n* [[" + synonym + ']]'

        return returned_string

    def render_antonyms(self, info) -> str:
        returned_string = ''
        if 'antonyms' in info.additional_data:
            returned_string += '\n\n{{-dika-mifanohitra-}}'
            for antonym in info.additional_data['antonyms']:
                returned_string += "\n* [[" + antonym + ']]'

        return returned_string

    def render_related_terms(self, info) -> str:
        returned_string = ''
        if 'related_terms' in info.additional_data or 'derived_terms' in info.additional_data:
            returned_string += '\n\n{{-teny mifandraika-}}'
            if 'related_terms' in info.additional_data:
                for d in info.additional_data['related_terms']:
                    returned_string += f"\n* [[{d}]]"

            if 'derived_terms' in info.additional_data:
                for d in info.additional_data['derived_terms']:
                    returned_string += f"\n* [[{d}]]"

        return returned_string

    def render_section(self, info, section_header, attr_name):
        returned_string = ""
        if attr_name in info.additional_data:
            if section_header not in returned_string:
                returned_string += '\n\n' + section_header
            section_data = info.additional_data[attr_name]
            if isinstance(section_data, list):
                if len(section_data) > 1:
                    for ref in info.additional_data[attr_name]:
                        returned_string += "\n* " + ref
                elif len(section_data) == 1:
                    returned_string += "\n" + section_data[0]

        return returned_string

    def render_further_reading(self, info):
        return self.render_section(info, '{{-famakiana fanampiny-}}', 'further_reading')

    def render_references(self, info) -> str:
        returned_string = ''
        for attr_name in ['references', 'reference', ]:
            returned_string += self.render_section(info, '{{-tsiahy-}}', attr_name)
        return returned_string

    def delete_section(self, language_section, wiki_page):
        section_name = "{{=" + language_section + "=}}"
        if section_name in wiki_page:
            lines = wiki_page.split('\n')
            section_begin = None
            section_end = None
            for line_no, line in enumerate(lines):
                section_rgx = re.search('==[ ]?' + section_name + '[ ]?==', line)
                if section_rgx is not None and section_begin is None:
                    section_begin = line_no
                    continue

                if section_begin is not None:
                    section_end_rgx = re.search('==[ ]?{{=', line)
                    if section_end_rgx is not None:
                        section_end = line_no
                        break

            assert section_begin is not None
            if section_end is not None:
                to_delete = '\n'.join(lines[section_begin:section_end])
            else:
                to_delete = '\n'.join(lines[section_begin:])

            new_text = wiki_page.replace(to_delete, '')
            return new_text

        return wiki_page
