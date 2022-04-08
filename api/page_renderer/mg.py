import re

from api.model.word import Entry
from .base import PageRenderer


class MGWikiPageRenderer(PageRenderer):

    def link_if_exists(self, definition_words: list) -> list:
        ret = []
        if hasattr(self, 'pages_to_link'):
            assert isinstance(self.pages_to_link, set)
            for word in definition_words:
                if word in self.pages_to_link:
                    ret.append(f'[[{word}]]')
                elif word.lower() in self.pages_to_link:
                    ret.append(f'[[{word.lower()}|{word}]]')
                else:
                    ret.append(word)
            return ret
        else:
            return definition_words

    def render(self, info: Entry, link=True) -> str:
        additional_note = ""
        if (hasattr(info, 'origin_wiktionary_page_name')
                and hasattr(info, 'origin_wiktionary_edition')):
            additional_note = " {{dikantenin'ny dikanteny|" + f"{info.origin_wiktionary_page_name}" \
                                                              f"|{info.origin_wiktionary_edition}" + "}}\n"

        s = self.render_head_section(info)
        s += self.render_definitions(info, additional_note, link)
        s += self.render_pronunciation(info)
        s += self.render_synonyms(info)
        s += self.render_antonyms(info)
        s += self.render_related_terms(info)
        s += self.render_further_reading(info)
        s += self.render_references(info)

        return s + '\n'

    def render_head_section(self, info):
        # Language
        s = "=={{=" + f"{info.language}" + "=}}==\n"
        s += self.render_etymology(info)

        # Part of speech
        s += "\n{{-" + f'{info.part_of_speech}-|{info.language}' + "}}\n"

        # Pronunciation
        s += "'''{{subst:BASEPAGENAME}}''' "

        # transcription (if any)
        if hasattr(info, 'transcription'):
            transcriptions = ', '.join(getattr(info, 'transcription'))
            s += f"({transcriptions})"

        return s

    def render_etymology(self, info):
        s = ''
        if hasattr(info, 'etymology'):
            etymology = getattr(info, 'etymology')
            if etymology:
                s += '\n{{-etim-}}\n'
                s += ':' + etymology
            else:
                s += '\n{{-etim-}}\n'
                s += f': {{vang-etim|' + f'{info.language}' + '}}\n'

        return s

    def render_definitions(self, info, additional_note, link):
        s = ''
        trailing_characters_to_exclude_from_link = ',.;:'
        definitions = []
        defn_list = sorted(set(info.definitions))
        if link:
            for d in defn_list:
                if len(d.split()) == 1:
                    if d[-1] in trailing_characters_to_exclude_from_link:
                        for trailing_character_to_exclude_from_link in trailing_characters_to_exclude_from_link:
                            if d.endswith(trailing_character_to_exclude_from_link):
                                temp_d = d.strip('.')
                                definitions.append(f'[[{temp_d.lower()}|{temp_d}]].')
                                break
                    else:
                        definitions.append(f'[[{d}]]')
                elif '[[' in d or ']]' in d:
                    definitions.append(d)
                else:
                    multiword_definitions = self.link_if_exists(d.split())
                    definition = ' '.join(multiword_definitions)
                    definition = definition.replace(' - ', '-')
                    definitions.append(definition)

        else:
            definitions = [f'{d}' for d in defn_list]

        for idx, defn in enumerate(definitions):
            s += "\n# " + defn
            s += additional_note % info.properties
            # Examples:
            if hasattr(info, 'examples'):
                if len(info.examples) > idx:
                    if isinstance(info.examples, list):
                        if len(info.examples[idx]) > 0:
                            for example in info.examples[idx]:
                                s += "\n#* ''" + example + "''"
                    elif isinstance(info.examples, str):
                        s += "\n#* ''" + info.examples[idx] + "''"

        return s

    def render_pronunciation(self, info):
        s = ''
        # Pronunciation and/or Audio
        if hasattr(info, 'audio_pronunciations') or \
                hasattr(info, 'ipa'):
            s += '\n\n{{-fanononana-}}'

            if hasattr(info, 'audio_pronunciations'):
                for audio in info.audio_pronunciations:
                    s += "\n* " + \
                        '{{audio|' + f'{audio}' + '|' + f'{info.entry}' + '}}'

            if hasattr(info, 'ipa'):
                for ipa in info.ipa:
                    s += "\n* " + \
                        '{{fanononana|' + f'{ipa}' + '|' + f'{info.language}' + '}}'

        # Pronunciation section
        elif hasattr(info, 'pronunciation'):
            s += '\n\n{{-fanononana-}}'
            if isinstance(info.pronunciation, list):
                for pron in info.pronunciation:
                    s += "\n* " + pron.strip('*').strip()
            else:
                s += "\n* " + info.pronunciation.strip('*').strip()

        return s

    def render_synonyms(self, info):
        s = ''
        if hasattr(info, 'synonyms'):
            s += '\n\n{{-dika-mitovy-}}'
            for synonym in info.synonyms:
                s += "\n* [[" + synonym + ']]'

        return s

    def render_antonyms(self, info) -> str:
        s = ''
        if hasattr(info, 'antonyms'):
            s += '\n\n{{-dika-mifanohitra-}}'
            for antonym in info.antonyms:
                s += "\n* [[" + antonym + ']]'

        return s

    def render_related_terms(self, info) -> str:
        s = ''
        if hasattr(info, 'related_terms') or \
                hasattr(info, 'derived_terms'):
            s += '\n\n{{-teny mifandraika-}}'

            if hasattr(info, 'related_terms'):
                for d in info.related_terms:
                    s += f"\n* [[{d}]]"
            if hasattr(info, 'derived_terms'):
                for d in info.derived_terms:
                    s += f"\n* [[{d}]]"
        return s

    def render_section(self, info, section_header, attr_name):
        s = ""
        if hasattr(info, attr_name):
            if section_header not in s:
                s += '\n\n' + section_header
            section_data = getattr(info, attr_name)
            if isinstance(section_data, list):
                if len(section_data) > 1:
                    for ref in getattr(info, attr_name):
                        s += "\n* " + ref
                elif len(section_data) == 1:
                    s += "\n" + section_data[0]

        return s

    def render_further_reading(self, info):
        return self.render_section(info, '{{-famakiana fanampiny-}}', 'further_reading')

    def render_references(self, info) -> str:
        s = ''
        for attr_name in ['references', 'reference', ]:
            s += self.render_section(info, '{{-tsiahy-}}', attr_name)
        return s

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
        else:
            return wiki_page
