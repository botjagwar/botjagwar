import pywikibot
import redis

from api.config import BotjagwarConfig
from api.decorator import separate_process
from import_wiktionary import EnWiktionaryDumpImporter

config = BotjagwarConfig()


class NoPage(Exception):
    pass


class RedisSite(object):
    def __init__(
            self,
            language: str,
            wiki: str,
            host='default',
            port=6379,
            password='default',
            offline=False
    ):
        self.offline = offline
        self.language = language
        self.wiki = wiki
        if host == 'default':
            self.host = config.get('host', 'redis')
        else:
            self.host = host

        if password == 'default':
            self.password = config.get('password', 'redis')
            if not self.password:
                self.password = None
        else:
            self.password = None

        self.port = port
        self.instance = redis.Redis(
            self.host,
            self.port,
            password=self.password,
            socket_timeout=3)

    @property
    def lang(self):
        return self.language

    def random_page(self):
        rkey = self.instance.randomkey()
        while not rkey.startswith(
            bytes(
                f'{self.wiki}.{self.language}/',
                'utf8')):
            rkey = self.instance.randomkey()

        page_name = str(
            rkey, encoding='utf8').replace(
            f'{self.wiki}.{self.language}/', '')
        return RedisPage(self, page_name)

    @separate_process
    def load_xml_dump(self, dump='user_data/dumps/enwikt.xml'):
        importer = EnWiktionaryDumpImporter(dump)
        for xml_page in importer.load():
            try:
                title, content = importer.get_page_from_xml(xml_page)
                self.push_page(title, content)
            except redis.ConnectionError as error:
                print(error)
            except Exception as error:
                print('Unknown error ', error)

    def push_page(self, title: str, content: str):
        if title is not None and content is not None:
            self.instance.set(f'{self.wiki}.{self.language}/{title}', content)

    def __str__(self):
        return f'{self.wiki}.{self.language}'


class RedisPage(object):
    max_redirection_depth = 10  # number of redirection link following until we consider the page as non-existent

    def __init__(self, site: RedisSite, title: str, offline='automatic'):
        if offline == 'automatic':
            self.offline = site.offline
        else:
            assert isinstance(offline, bool)
            self.offline = offline

        self.site = site
        self._title = title

    def title(self, *args):
        return self._title

    def __repr__(self):
        return f'Page({self.site}/{self.title()})'

    def isEmpty(self):
        return self.get() == ''

    def get(self):
        if self._title is None:
            return ''

        cache_contents = self.site.instance.get(
            f'{self.site.wiki}.{self.site.language}/{self._title}')
        if not cache_contents:
            if not self.offline:
                wikisite = pywikibot.Site(self.site.language, self.site.wiki)
                wikipage = pywikibot.Page(wikisite, self._title)
                if wikipage.exists():
                    content = wikipage.get()
                    self.site.push_page(self._title, content)
                    return content
                else:
                    raise NoPage(
                        f'Page {self._title} at {self.site} not found '
                        f'neither in-redis nor on-wiki')
            else:
                raise NoPage(
                    f'Page  {self._title} at {self.site} not found in redis. '
                    f'Offline mode is OFF so no on-wiki fetching.')
        else:
            cache_contents = str(cache_contents, encoding='utf8')
            return cache_contents

    def exists(self):
        cache_contents = self.site.instance.get(
            f'{self.site.wiki}.{self.site.language}/{self._title}')
        if not cache_contents:
            if self.offline:
                return False
            else:
                wikisite = pywikibot.Site(self.site.language, self.site.wiki)
                wikipage = pywikibot.Page(wikisite, self._title)
                if wikipage.exists():
                    redirection_depth = 0
                    while wikipage.isRedirectPage():
                        redirection_depth += 1
                        if redirection_depth == self.max_redirection_depth:
                            break
                        else:
                            wikipage = wikipage.getRedirectTarget()

                    if redirection_depth == self.max_redirection_depth:
                        return False

                return wikipage.exists()
        else:
            return True

    def namespace(self):
        if self.offline:
            class Namespace(object):
                content = self.get()

            return Namespace()
        else:
            wikisite = pywikibot.Site(self.site.language, self.site.wiki)
            wikipage = pywikibot.Page(wikisite, self._title)
            return getattr(wikipage, 'namespace')()

    def isRedirectPage(self):
        if self.exists():
            try:
                content = self.get()
            except pywikibot.exceptions.IsRedirectPageError:
                return True
            else:
                return '#REDIRECT [[' in content
        else:
            if not self.offline:
                wikisite = pywikibot.Site(self.site.language, self.site.wiki)
                wikipage = pywikibot.Page(wikisite, self._title)
                return wikipage.isRedirectPage()
            return False

    def __getattr__(self, item):
        if hasattr(RedisPage, item):
            return getattr(self, item)
        else:
            wikisite = pywikibot.Site(self.site.language, self.site.wiki)
            wikipage = pywikibot.Page(wikisite, self._title)
            return getattr(wikipage, item)


if __name__ == '__main__':
    print("""
    Download the en.wiktionary page dumps,
    split it into several chunks (e.g. using split) and run this script.
    All en.wiktionary pages will have their latest version uploaded in your Redis.
    Using RedisSite and RedisPage, you'll have a much faster read and offline access.
    """)
    site = RedisSite('mg', 'wiktionary')
    site.load_xml_dump('user_data/dumps/mgwikt.xml')
    # site.load_xml_dump('user_data/dumps/enwikt_2.xml')
    # site.load_xml_dump('user_data/dumps/enwikt_3.xml')
    # site.load_xml_dump('user_data/dumps/enwikt_4.xml')
    # site.load_xml_dump('user_data/dumps/enwikt_5.xml')
    # site.load_xml_dump('user_data/dumps/enwikt_6.xml')
    # site.load_xml_dump('user_data/dumps/enwikt_7.xml')
    # site.load_xml_dump('user_data/dumps/enwikt_8.xml')
    # site.load_xml_dump('user_data/dumps/enwikt_9.xml')
    # site.load_xml_dump('user_data/dumps/enwikt_10.xml')
    # site.load_xml_dump('user_data/dumps/enwikt_11.xml')
    # site.load_xml_dump('user_data/dumps/enwikt_13.xml')
    # site.load_xml_dump('user_data/dumps/enwikt_14.xml')
    # site.load_xml_dump('user_data/dumps/enwikt_15.xml')
    # site.load_xml_dump('user_data/dumps/enwikt_16.xml')
    # site.load_xml_dump('user_data/dumps/enwikt_17.xml')
