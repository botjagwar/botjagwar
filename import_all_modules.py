from redis_wikicache import RedisPage, RedisSite
from api.translation_v2.publishers import WiktionaryRabbitMqPublisher


publisher = WiktionaryRabbitMqPublisher(queue="terakasorotany")
counter = 0
desired = 0
with open('user_data/pron.txt', 'r') as file:
    modules = file.read().splitlines()

    for page in modules:
        counter += 1
        if counter < desired:
            continue
        print(f'COUNTER = {counter}')
        page = page.strip()
        pagename = f"Template:{page}"
        if page.strip():
            p = RedisPage(RedisSite("en", "wiktionary"), pagename)
            try:
                while p.isRedirectPage():
                    p = p.getRedirectTarget()
                original_content = p.get()
            except Exception as e:
                print(f"Error fetching {pagename} from English Wiktionary: {e}")
                continue
        print(f"Importing {pagename} from English Wiktionary")
        print(len(original_content))
        publisher.publish_wikipage(
            page_title=pagename,
            content=original_content,
            summary=f"Mampiditra [[:en:{pagename}|{pagename}]] avy amin'ny Wikibolana anglisy",
        )
        # break
