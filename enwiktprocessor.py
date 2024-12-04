import logging

from api.entryprocessor.wiki.en import ENWiktionaryProcessor as ENWiktionaryProcessor
from redis_wikicache import RedisPage, RedisSite

"""
Requires RedisSite and RedisPage wrappers.
All data must have been imported there.
see redis_wikicache.py for more details.
"""

logger = logging.getLogger("processor")
enwikt = RedisSite("en", "wiktionary")


def test_one():
    page = RedisPage(enwikt, "ˤ3pp")
    processor = ENWiktionaryProcessor()
    processor.set_title(page.title())
    processor.set_text(page.get())
    print(page)
    for k in processor.get_all_entries(get_additional_data=True):
        print(k)

    # print(k)
    for _ in processor.retrieve_translations():
        pass


def test_random():
    errors = 0
    sample_size = 50
    for _ in range(sample_size):
        print()
        page = enwikt.random_page()
        processor = ENWiktionaryProcessor()
        processor.set_title(page.title())
        if ":" in page.title():
            sample_size -= 1
            continue

        processor.set_text(page.get())
        try:
            for k in processor.get_all_entries(
                cleanup_definitions=True,
                get_additional_data=True,
                translate_definitions_to_malagasy=True,
            ):
                print(k)

            for _ in processor.retrieve_translations():
                pass
        except Exception as e:
            print(page.title())
            logger.exception(e)
            print(e.__class__, e)
            errors += 1

    rate = 1 - (errors / sample_size)
    print(rate * 100, "% of pages could be processed")
    assert rate >= 0.995


if __name__ == "__main__":
    test_random()
    # test_one()
