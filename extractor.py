import logging
import re

import requests
from lxml import etree

from api.decorator import time_this
from api.storage import SiteExtractorCacheEngine, CacheMissError
from object_model.word import Entry
from page_lister import get_pages_from_category

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
        for var in ['lookup_pattern', 'definition_xpath', 'pos_xpath']:
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

    @time_this('lookup')
    def lookup(self, word) -> Entry:
        content = self.load_page(word)
        definitions = [self.reprocess_definition(d)
                       for d in content.xpath(self.definition_xpath)]

        word = word
        print('>>>>>', word, '<<<<<')
        pos = content.xpath(self.pos_xpath)[0].text.strip('\n')

        return Entry(
            entry=word,
            part_of_speech=pos,
            language=self.language,
            entry_definition=definitions,
        )


class TenyMalagasySiteExtractor(SiteExtractor):
    lookup_pattern = 'http://tenymalagasy.org/bins/teny2/%s'
    definition_xpath = '//table[2]/tr[3]/td[3]'
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

    def lookup(self, word):
        """
        Postprocessor function
        :param word:
        :return:
        """
        entry = super(TenyMalagasySiteExtractor, self).lookup(word)

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

        entry.entry_definition = new_definitions
        entry.examples = examples

        return entry


def main():
    import random
    import time
    import pickle
    extractor = TenyMalagasySiteExtractor()
    counter = 0
    new_pagelist = []
    pagelist = [p for p in get_pages_from_category('mg', 'Famaritana tsy ampy')]
    random.shuffle(pagelist)
    for page in pagelist:
        print('>>>>', page.title(), '<<<<')
        counter += 1
        content = page.get()
        if '=mg=' not in content:
            continue
        try:
            time.sleep(random.randint(1, 4))
            entry = extractor.lookup(page.title())
            print(entry)
        except SiteExtractorException as e:
            print(e)
            continue
        new_pagelist.append(page.title())

    with open('user_data/existingpages-list.pkl', 'wb') as f:
        pickle.dump(new_pagelist, f)

def test():
    extractor = TenyMalagasySiteExtractor()
    for word in [
        'fandraisana', 'fantsika',
        'filazana', 'anao',
        'laza', 'izaho',
        'manisy', 'maizina',
        'mandray', 'tany',
        'etoana', 'volo',
        'etona', 'fahasoavana',
        'tontolo',
        'sdlfksldkfdf' # non-existent page
    ]:
        try:
            print(word, extractor.lookup(word))
        except SiteExtractorException as e:
            print(e)
            continue


if __name__ == '__main__':
    main()