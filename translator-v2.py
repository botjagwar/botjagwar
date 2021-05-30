from api.translation_v2.core import Translation
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
    for v in 'sanaturae,excripserant,apponendas,addubitassemus,veterescentes,inanituras,declamitaturos,clavigerorum'.split(','):
        entries += t.process_wiktionary_wiki_page(RedisPage(RedisSite('en', 'wiktionary'), v))
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