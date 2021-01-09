import logging
import re

import requests
from lxml import etree

from api.storage import SiteExtractorCacheEngine, CacheMissError
from object_model.word import Entry

log = logging.getLogger(__name__)

headers = {
    'User-Agent': "Mozilla/5.0 (X11; Linux x86_64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Ubuntu Chromium/69.0.3497.81 "
                  "Chrome/69.0.3497.81 Safari/537.36",
}


class SiteExtractorException(Exception):
    def __init__(self, http_response_context, *args, **kwargs):
        super(SiteExtractorException, self).__init__(*args, **kwargs)
        self.context = http_response_context
        log.exception(self)


class SiteExtractor(object):
    STRIP_TAGS_LIST = ['a', 'i', 'b', 'br', 'div',
                       'small', 'big', 'td', 'tr', 'span']
    lookup_pattern = None
    definition_xpath = None
    pos_xpath = None
    language = None
    definition_language = None
    cache_engine = None

    def __del__(self):
        if isinstance(self.cache_engine, SiteExtractorCacheEngine):
            self.cache_engine.write()

    def load_page(self, word) -> etree._Element:
        def check_if_defined(var):
            if getattr(self, var) is None:
                raise NotImplementedError('%s has to be defined' % var)

        def _get_html_page():
            response = requests.get(self.lookup_pattern % word, headers=headers)
            if response.status_code == 200:
                if 'tsy misy' in response.text:
                    raise SiteExtractorException(response, 'Empty content')
                return response.text
            elif 400 <= response.status_code < 600:
                raise SiteExtractorException(response, 'Non-OK')

        # variables check
        for var in ['lookup_pattern', 'definition_xpath']:
            check_if_defined(var)

        # cache check if page has already been retrieved, and handle known raised exception
        if isinstance(self.cache_engine, SiteExtractorCacheEngine):
            try:
                page = str(self.cache_engine.get(word))
                return etree.HTML(page)
            except CacheMissError:
                page = _get_html_page()
                self.cache_engine.add(word, page)
                return etree.HTML(page)
            except SiteExtractorException as e:
                raise e
        else:
            page = _get_html_page()

        return etree.HTML(page)

    def reprocess_definition(self, definition):
        """
        Definition post-processor. Override with your own function
        :param definition:
        :return:
        """
        return definition

    #@time_this('lookup')
    def lookup(self, word) -> Entry:
        content = self.load_page(word)
        definitions = [self.reprocess_definition(d)
                       for d in content.xpath(self.definition_xpath)]

        if self.pos_xpath is not None:
            pos = content.xpath(self.pos_xpath)[0].text.strip('\n')
        else:
            pos = 'ana'

        return Entry(
            entry=word,
            part_of_speech=pos,
            language=self.language,
            entry_definition=definitions,
        )


class TenyMalagasySiteExtractor(SiteExtractor):
    lookup_pattern = 'http://tenymalagasy.org/bins/teny2/%s'
    definition_xpath = "//table[2]/tr[3]/td[3]"
    pos_xpath = '//table[2]/tr[2]/td[3]'
    language = 'mg'
    definition_language = 'mg'
    cache_engine = SiteExtractorCacheEngine('tenymalagasy.org')

    part_of_speech_mapper = {
        'anarana': 'ana',
        "matoantenin' ny atao": 'mat',
        "matoantenin' ny mpanao": 'mat',
        'tambinteny': 'tamb',
        'mpamaritra': 'mpam'
    }

    def reprocess_definition(self, definition):
        etree.strip_tags(definition, self.STRIP_TAGS_LIST)
        definition = etree.tostring(definition, encoding='unicode')
        definition = definition.replace('<td class="main">', '')
        definition = definition.replace('</td>', '')
        definition = definition.replace('\n', '')
        return definition

    #@time_this('tenymalagasy.org lookup')
    def lookup(self, word):
        """
        Postprocessor function
        :param word:
        :return:
        """
        content = self.load_page(word)
        if content.find('Famaritana malagasy') == -1:
            print('skipping...')
            raise SiteExtractorException

        try:
            entry = super(TenyMalagasySiteExtractor, self).lookup(word)
        except Exception:
            raise SiteExtractorException(None)

        # ---- Our postprocessor below -----
        references_regex = r'([a-zA-Z]+ [0-9]+)'
        entry.part_of_speech = (
            self.part_of_speech_mapper[entry.part_of_speech]
            if entry.part_of_speech in self.part_of_speech_mapper
            else entry.part_of_speech
        )
        entry.references = []
        new_definitions = []
        examples = {}
        for definition_section in entry.entry_definition:
            for ref in re.findall(references_regex, str(definition_section)):
                entry.references.append(ref)
                definition_section = definition_section.replace('[%s]' % ref, '')
                definition_section = definition_section.replace('%s]' % ref, '')

            for i, d in enumerate(definition_section.split('¶\xa0')):
                split_definition = d.split(':')
                if len(split_definition) == 2:
                    definition, example = split_definition
                    new_definitions.append(definition)
                    examples[i] = example
                else:
                    sd = ' '.join(split_definition)
                    new_definitions.append(sd.strip())

        entry.entry_definition = new_definitions
        entry.examples = examples

        return entry


class RakibolanaSiteExtactor(SiteExtractor):
    lookup_pattern = 'http://www.rakibolana.org/rakibolana/teny/%s'
    definition_xpath = '//*[@id="rakibolana-result"]/div'
    language = 'mg'
    definition_language = 'mg'
    cache_engine = SiteExtractorCacheEngine('www.rakibolana.org')

    def __init__(self):
        self.STRIP_TAGS_LIST.append('div')

    def reprocess_definition(self, definition):
        etree.strip_tags(definition, self.STRIP_TAGS_LIST)
        definition = etree.tostring(definition, encoding='unicode')

        definition = definition.replace('<div class="rakibolana-definition">', '')
        definition = definition.replace('\n Ahitsio\n  </div>\n\n', '')
        definition = ''.join(definition.split(':')[1:]).strip()

        # Segment phrases
        for char in 'ABDEFGHIJKLMNOPRSTVZ':
            definition = definition.replace(' ' + char, '. ' + char)

        for char in '.;:?':
            definition = definition.replace(char, '##')

        # fix OCR errors as much as possible
        definition = definition.replace('u', 'v')
        definition = definition.replace('-', '')
        definition = definition.replace('Y ', 'y ')

        definition = definition.replace(char, '##')
        definition = '$$'.join(definition.split('##')).strip()

        return definition

    #@time_this('rakibolana.org lookup')
    def lookup(self, word):
        """
        Postprocessor function
        :param word:
        :return:
        """
        content = self.load_page(word)
        if content.find('Tsy hita ny teny') == -1:
            print('skipping...')
            raise SiteExtractorException

        entry = super(RakibolanaSiteExtactor, self).lookup(word)
        return entry

