import pywikibot
import redis

from api.translation_v2.core import Translation
from page_lister import get_pages_from_category
from redis_wikicache import RedisPage, RedisSite

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
    for wp in get_pages_from_category('en', 'Chinese verbs'):
        try:
            t.process_wiktionary_wiki_page(RedisPage(RedisSite('en', 'wiktionary'), wp.title(), offline=False))
        except (pywikibot.Error, redis.exceptions.TimeoutError):
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

    print('process error rate:', errors*100. / (k))
    print('entries created:', entries)
    print(errored)
