import inspect
import sys
import warnings
from typing import Type

from object_model.word import Entry


class PageRenderer(object):
    def render(self, info: Entry) -> str:
        raise NotImplementedError()


class FAWikiPageRenderer(PageRenderer):
    def render(self, info: Entry, link=True) -> str:
        data = info.to_dict()
        s = """
{{-%(language)s-}}
'''{{subst:BASEPAGENAME}}'''""" % data
        if link:
            s += "\n# %s" % ', '.join(['[[%s]]' % (d) for d in info.entry_definition])
        else:
            s += "\n# %s" % ', '.join(['%s' % (d) for d in info.entry_definition])
        additional_note = '\n{{bot-made translation|%s}}' % info.origin_wiktionary_page_name
        s = s + additional_note
        try:
            return s
        except UnicodeDecodeError:
            return s.decode('utf8')


class FJWikiPageRenderer(PageRenderer):
    def render(self, info: Entry, link=True) -> str:
        data = info.to_dict()
        s = """
{{-%(language)s-}}
'''{{subst:BASEPAGENAME}}'''""" % data
        if link:
            s += "\n# %s" % ', '.join(['[[%s]]' % (d) for d in info.entry_definition])
        else:
            s += "\n# %s" % ', '.join(['%s' % (d) for d in info.entry_definition])
        additional_note = '\n{{bot-made entry|%s}}' % info.origin_wiktionary_page_name
        s = s + additional_note
        try:
            return s
        except UnicodeDecodeError:
            return s.decode('utf8')


class CHRWikiPageRenderer(PageRenderer):
    def render(self, info: Entry, link=True) -> str:
        data = info.to_dict()
        s = """
{{-%(language)s-}}
'''{{subst:BASEPAGENAME}}'''""" % data
        if link:
            s += "\n# %s" % ', '.join(['[[%s]]' % (d) for d in info.entry_definition])
        else:
            s += "\n# %s" % ', '.join(['%s' % (d) for d in info.entry_definition])
        additional_note = '\n{{bot-made translation|%s}}' % info.origin_wiktionary_page_name
        s = s + additional_note
        try:
            return s
        except UnicodeDecodeError:
            return s.decode('utf8')


class MGWikiPageRenderer(PageRenderer):

    def link_if_exists(self, definition_words: list) -> list:
        ret = []
        if hasattr(self, 'pages_to_link'):
            assert isinstance(self.pages_to_link, set)
            for word in definition_words:
                if word in self.pages_to_link:
                    ret.append('[[' + word + ']]')
                else:
                    ret.append(word)
            return ret
        else:
            return definition_words

    def render(self, info: Entry, link=True) -> str:
        additional_note = ""

        if (hasattr(info, 'origin_wiktionary_page_name') and hasattr(info, 'origin_wiktionary_edition')):
            additional_note = " {{dikantenin'ny dikanteny|" + f"{info.origin_wiktionary_page_name}" \
                                                              f"|{info.origin_wiktionary_edition}" + "}}\n"

        # Language
        s = "=={{=" + f"{info.language}" + "=}}==\n"

        # Etymology
        if hasattr(info, 'etymology'):
            etymology = getattr(info, 'etymology')
            if etymology:
                s += '\n{{-etim-}}\n'
                s += ':' + etymology
            else:
                s += '\n{{-etim-}}\n'
                s += f': {{vang-etim|' + f'{info.language}' + '}}\n'
        # else:
        #     s += '\n{{-etim-}}\n'
        #     s += ': {{vang-etim|' + f'{info.language}' + '}}\n'

        # Part of speech
        s += "\n{{-" + f'{info.part_of_speech}-|{info.language}' + "}}\n"

        # Pronunciation
        s += "'''{{subst:BASEPAGENAME}}''' "
        # if hasattr(info, 'pronunciation'):
        #     s += "{{fanononana|" + f'{info.pronunciation}' + "|" + f'{info.language}' + "}}"
        # else:
        #     s += "{{fanononana||" + f'{info.language}' + "}}"

        # Definition
        definitions = []
        defn_list = list(set(info.entry_definition))
        defn_list.sort()
        if link:
            for d in defn_list:
                if len(d.split()) == 1:
                    definitions.append(f'[[{d.lower()}|{d}]]')
                elif '[[' in d or ']]' in d:
                    definitions.append(d)
                else:
                    multiword_definitions = self.link_if_exists(d.split())
                    definitions.append(' '.join(multiword_definitions))
        else:
            definitions = [f'{d}' for d in defn_list]

        for idx, defn in enumerate(definitions):
            s += "\n# " + defn
            s += additional_note % info.properties
            ## Examples:
            if hasattr(info, 'examples'):
                if len(info.examples) > idx:
                    if isinstance(info.examples, list):
                        if len(info.examples[idx]) > 0:
                            for example in info.examples[idx]:
                                s += "\n#* ''" + example + "''"
                    elif isinstance(info.examples, str):
                        s += "\n#* ''" + info.examples[idx] + "''"

        # Audio
        if hasattr(info, 'audio_pronunciations') or \
            hasattr(info, 'ipa'):
            s += '\n\n{{-fanononana-}}'

            if hasattr(info, 'audio_pronunciations'):
                for audio in info.audio_pronunciations:
                    s += "\n* " + '{{audio|' + f'{audio}' + '|' + f'{info.entry}' + '}}'

            if hasattr(info, 'ipa'):
                for ipa in info.ipa:
                    s += "\n* " + '{{fanononana|' + f'{ipa}' + '|' + f'{info.language}' + '}}'

        # Synonyms
        if hasattr(info, 'synonyms'):
            s += '\n\n{{-dika-mitovy-}}'
            for synonym in info.synonyms:
                s += "\n* [[" + synonym + ']]'

        # Antonyms
        if hasattr(info, 'antonyms'):
            s += '\n\n{{-dika-mifanohitra-}}'
            for antonym in info.antonyms:
                s += "\n* [[" + antonym + ']]'

        # Related/derived terms
        if hasattr(info, 'related_terms') or \
            hasattr(info, 'derived_terms'):
            s += '\n\n{{-teny mifandraika-}}'

            if hasattr(info, 'related_terms'):
                for d in info.related_terms:
                    s += f"\n* [[{d}]]"
            if hasattr(info, 'derived_terms'):
                for d in info.derived_terms:
                    s += f"\n* [[{d}]]"

        # References
        if hasattr(info, 'references'):
            s += '\n\n{{-tsiahy-}}'
            for ref in info.references:
                if ref.startswith('*'):
                    s += '\n' + ref
                else:
                    s += "\n* " + ref

        return s


class WikiPageRendererFactory(object):
    def __new__(cls, wiki) -> Type[PageRenderer]:
        assert type(wiki) == str
        ct_module = sys.modules[__name__]
        classes = inspect.getmembers(ct_module, inspect.isclass)
        processors = [x for x in classes if x[0].endswith('WikiPageRenderer')]
        language_class_name = "%sWikiPageRenderer" % wiki.upper()

        for current_class_name, processor_class in processors:
            if current_class_name == language_class_name:
                return processor_class

        warnings.warn("Tsy nahitana praosesera: '%s'" % language_class_name, Warning)
        return PageRenderer
