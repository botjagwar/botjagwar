import logging

from api.extractors.site_extractor import RakibolanaSiteExtactor, TenyMalagasySiteExtractor
from api.extractors.site_extractor import SiteExtractorException
from page_lister import get_pages_from_category

log = logging.getLogger(__name__)


def main0(classname):
    import random
    import time
    import pickle
    extractor = classname()
    counter = 0
    new_pagelist = []
    pagelist = [p for p in get_pages_from_category('mg', 'Famaritana tsy ampy')
                if p not in extractor.cache_engine.page_dump.keys()]
    random.shuffle(pagelist)
    for page in pagelist:
        print('>>>> [', classname.__name__, ']: ', page.title(), '<<<<')
        counter += 1
        content = page.get()
        if '=mg=' not in content:
            print('skipping...')
            continue
        try:
            time.sleep(random.randint(1, 4))
            entry = extractor.lookup(page.title())
            print(entry)
        except SiteExtractorException as e:
            print(e)
            continue
        except Exception:
            continue
        else:
            new_pagelist.append(page.title())

    with open('user_data/existingpages-list.pkl', 'wb') as f:
        pickle.dump(new_pagelist, f)


def entry_generator():
    from api.output import Output
    output = Output()
    for extractor_class in [RakibolanaSiteExtactor, TenyMalagasySiteExtractor]:
        extractor = extractor_class()
        print(extractor.lookup('voambolana'))
        for word in iter(extractor.cache_engine.list()):
            entry = extractor.lookup(word)
            if entry.definitions:
                s = output.batchfile(entry)
                print(s[:-1])
                yield (word, entry.definitions)
                #s = json.dumps(entry.to_dict())


def main():
    c = 0
    import pywikibot
    for pagename, definitions in entry_generator():
        page = pywikibot.Page(pywikibot.Site('mg', 'wiktionary'), pagename)
        if not page.exists():
            continue
        old_content = content = page.get()
        formatted_definitions = [
            "# %s<ref>''Rakibolana Malagasy'' (1985) nosoratan'i Rajemisa-Raolison</ref>" %
            definition for definition in definitions]
        content = content.replace(
            '# {{...|mg}}',
            '\n'.join(formatted_definitions))
        pywikibot.showDiff(old_content, content)
        # page.put(content, '+famaritana')


if __name__ == '__main__':
    for pagename, definitions in entry_generator():
        print(pagename, definitions)
