import sys
from csv import writer

import pywikibot
import redis

from api.entryprocessor import WiktionaryProcessorFactory
from api.page_lister import redis_get_pages_from_category as get_pages_from_category
from api.translation_v2.core import Translation
from redis_wikicache import RedisSite

if __name__ == '__main__':
    t = Translation(use_configured_postprocessors=True)
    # t.post_processors = postprocessors
    site = RedisSite('en', 'wiktionary', offline=False)
    errored = []
    errors = 0
    k = 100
    entries = 0
    wiktionary_processor_class = WiktionaryProcessorFactory.create('en')
    category = sys.argv[1]
    with open(f'user_data/translations/{category}.csv', 'w') as output_file:
        csv_writer = writer(output_file)
        for wiki_page in get_pages_from_category('en', category):
            print(wiki_page)
            try:
                entries = t.process_wiktionary_wiki_page(wiki_page)
            except (pywikibot.Error, redis.exceptions.TimeoutError):
                continue

    print('process error rate:', errors * 100. / (k))
    print('entries created:', entries)
    print(errored)
