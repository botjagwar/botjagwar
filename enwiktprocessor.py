from api.entryprocessor.wiki.en import ENWiktionaryProcessor as ENWiktionaryProcessor
from redis_wikicache import RedisPage, RedisSite

enwikt = RedisSite('en', 'wiktionary')

def main():
    page = RedisPage(enwikt, 'strip')
    processor = ENWiktionaryProcessor()
    processor.set_title(page.title())
    processor.set_text(page.get())
    for k in processor.getall():
        print(k)

    print()
    for k in processor.retrieve_translations():
        print(k)

if __name__ == '__main__':
    main()
