from csv import writer

import pywikibot
import redis

from api.entryprocessor import WiktionaryProcessorFactory
from api.translation_v2.core import Translation
from page_lister import get_pages_from_category
from redis_wikicache import RedisSite

if __name__ == '__main__':
    # print(translate_using_postgrest_json_dictionary('mat', '[[mine|Mine]]', 'en', 'mg'))
    # print(translate_using_postgrest_json_dictionary('solo-ana', '[[mine|Mine]]', 'en', 'mg'))
    # print(translate_using_bridge_language('mat', 'castigar', 'es', 'mg'))
    # print(translate_using_bridge_language('ana', 'Schau', 'de', 'mg'))
    # print(translate_using_bridge_language('mat', 'schweben', 'de', 'mg'))
    # print(translate_using_convergent_definition('ana', 'hover', 'en', 'mg'))
    # print(translate_using_postgrest_json_dictionary('mat', 'flood', 'en', 'fr'))
    t = Translation()
    site = RedisSite('en', 'wiktionary')
    # wp = RedisPage(site, '')
    errored = []
    errors = 0
    k = 100
    entries = 0
    # for v in '잠자다,자다,앉다,睡眠,眠る,眠,寝る,眠,微睡む,座る,居,やすむ,睡目'.split(','):
    #     entries += t.process_wiktionary_wiki_page(RedisPage(RedisSite('en', 'wiktionary'), v))
    # for v in '平均‎'.split(','):
    #     entries += t.process_wiktionary_wiki_page(RedisPage(RedisSite('en', 'wiktionary'), v, offline=False))
    wiktionary_processor_class = WiktionaryProcessorFactory.create('en')
    category = 'Arabic verbs'
    with open(f'user_data/translations/{category}.csv', 'w') as output_file:
        csv_writer = writer(output_file)
        for wiki_page in get_pages_from_category('en', category):
            try:
                # t.process_wiktionary_wiki_page(RedisPage(RedisSite('en', 'wiktionary'), wp.title(), offline=True))
                # wiktionary_processor = wiktionary_processor_class()
                # wiktionary_processor.set_text(wiki_page.get())
                # wiktionary_processor.set_title(wiki_page.title())
                # entries = t.translate_wiktionary_page(wiktionary_processor)
                entries = t.process_wiktionary_wiki_page(wiki_page)
                # if not entries:
                #     continue
            except (pywikibot.Error, redis.exceptions.TimeoutError):
                continue
            else:
                # for entry in entries:
                #     row = [entry.entry, entry.part_of_speech, '', '', ', '.join(entry.definitions)]
                #     csv_writer.writerow(row)
                pass

    # for i in range(k):
    #     try:
    #         wp = site.random_page()
    #         entries += t.process_wiktionary_wiki_page(wp)
    #     except Exception as exception:
    #         errors += 1
    #         print(exception)
    #         errored.append((wp, exception))
    #     else:
    #         if not i % 200:
    #             print(i, 'entries', entries, '/ process error rate:', errors*100. / (i+1))

    print('process error rate:', errors * 100. / (k))
    print('entries created:', entries)
    print(errored)
