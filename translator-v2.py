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
    wp = RedisPage(RedisSite('en', 'wiktionary'), 'anak')
    t.process_wiktionary_wiki_page(wp)
