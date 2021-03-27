from api.entryprocessor.wiki.en import ENWiktionaryProcessor as ENWiktionaryProcessor
from redis_wikicache import RedisPage, RedisSite

"""
Requires RedisSite and RedisPage wrappers.
All data must have been imported there.
see redis_wikicache.py for more details.
"""

enwikt = RedisSite('en', 'wiktionary')

def test_one():
    page = RedisPage(enwikt, 'пересиливающий')
    processor = ENWiktionaryProcessor()
    processor.set_title(page.title())
    processor.set_text(page.get())
    print(page)
    for k in processor.getall():
        print(k)

    print()
    for k in processor.retrieve_translations():
        print(k)


def test_random():
    errors = 0
    sample_size = 1000
    for i in range(sample_size):
        page = enwikt.random_page()
        processor = ENWiktionaryProcessor()
        processor.set_title(page.title())
        if ":" in page.title():
            sample_size -= 1
            continue

        processor.set_text(page.get())
        try:
            for k in processor.getall():
                pass
                # print(k)

            for k in processor.retrieve_translations():
                pass
                # print(k)
        except Exception as e:
            print(page)
            print(e.__class__, e)
            errors += 1

    rate = (1 - (errors/sample_size))
    assert rate >= .993


if __name__ == '__main__':
    test_random()
