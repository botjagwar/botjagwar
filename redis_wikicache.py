import bz2
import json
import os
import sys

import pika
import pywikibot
import redis
import requests

from api.config import BotjagwarConfig
from api.decorator import separate_process, retry_on_fail, run_once
from import_wiktionary import EnWiktionaryDumpImporter

config = BotjagwarConfig()


class RedisWikipageError(Exception):
    pass


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
        offline=False,
        download_dump_if_not_exists=True
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
        self.download_dump_if_not_exists = download_dump_if_not_exists

    def all_pages(self):
        for key in self.instance.scan_iter(match=f'{self.wiki}.{self.language}/*', count=1000):
            page_name = str(key, encoding='utf8').replace(f'{self.wiki}.{self.language}/', '')
            yield RedisPage(RedisSite(self.language, 'wiktionary'), page_name)

    @property
    def lang(self):
        return self.language

    @property
    @run_once
    def instance(self):
        return redis.Redis(
            self.host,
            self.port,
            password=self.password,
            socket_timeout=3)

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

    def download_dump(self):
        url = f'https://dumps.wikimedia.org/{self.language}wiktionary/latest' \
              f'/{self.language}wiktionary-latest-pages-articles.xml.bz2'
        dump_dir = 'user_data/dumps'
        dump_path = dump_dir + f'/{self.language}wikt.xml'

        if not os.path.isdir(dump_dir):
            os.mkdir(dump_dir)
        if not os.path.isfile(dump_path + '.bz2'):
            print('File is absent. Downloading from dumps.wikimedia.org. This may take a while...')
            with requests.get(url, stream=True) as request:
                request.raise_for_status()
                with open(dump_path + '.bz2', 'wb') as f:
                    for chunk in request.iter_content(chunk_size=8192):
                        f.write(chunk)
            print('Download complete.')

        print('Extracting dump file...')
        with open(dump_path, 'wb') as xml_file, bz2.BZ2File(dump_path + '.bz2', 'rb') as file:
            for data in iter(lambda: file.read(100 * 1024), b''):
                xml_file.write(data)

    @separate_process
    def load_xml_dump(self, download=False, dump_path='user_data/dumps/enwikt.xml'):
        if self.download_dump_if_not_exists or download:
            self.download_dump()

        importer = EnWiktionaryDumpImporter(dump_path)
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

        self._connection = None
        self._channel = None
        self._queue_name = None

    def initialize_rabbitmq(self):
        rabbitmq_host = config.get('host', 'rabbitmq')
        rabbitmq_queue = config.get('queue', 'rabbitmq')
        self._queue_name = rabbitmq_queue
        rabbitmq_username = config.get('username', 'rabbitmq')
        rabbitmq_password = config.get('password', 'rabbitmq')
        rabbitmq_virtual_host = config.get('virtual_host', 'rabbitmq')

        # Create credentials for RabbitMQ authentication
        credentials = pika.PlainCredentials(rabbitmq_username, rabbitmq_password)

        # Establish a connection to RabbitMQ with authentication and vhost
        parameters = pika.ConnectionParameters(
            host=rabbitmq_host,
            virtual_host=rabbitmq_virtual_host,
            credentials=credentials
        )
        self._connection = pika.BlockingConnection(parameters)
        self._channel = self._connection.channel()
        self._channel.queue_declare(queue=rabbitmq_queue)

    def __del__(self):
        # Close the connection
        self._connection.close()

    @property
    def message_broker_channel(self):
        if not self._channel:
            print("Initializing a connection to the message broker...")
            self.initialize_rabbitmq()

        return self._channel

    @property
    def queue_name(self):
        if not self._channel:
            print("Initializing a connection to the message broker...")
            self.initialize_rabbitmq()

        return self._queue_name

    def title(self, *args):
        return self._title

    def __repr__(self):
        return f'Page({self.site}/{self.title()})'

    def isEmpty(self):
        return self.get() == ''

    @retry_on_fail((redis.ConnectionError), retries=5, time_between_retries=.5)
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
            try:
                return getattr(wikipage, 'namespace')()
            except pywikibot.exceptions.InvalidTitleError:
                class Namespace(object):
                    content = self.get()

                return Namespace()

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

    def async_put(self, content, summary, minor):
        message = json.dumps({
            'page': self.title(),
            "content": content,
            'summary': summary
        })
        self.message_broker_channel.basic_publish(exchange='', routing_key=self._queue_name, body=message)


if __name__ == '__main__':
    print("""
    Download the en.wiktionary page dumps,
    split it into several chunks (e.g. using split) and run this script.
    All en.wiktionary pages will have their latest version uploaded in your Redis.
    Using RedisSite and RedisPage, you'll have a much faster read and offline access.
    """)
    language = sys.argv[1]
    site = RedisSite(language, 'wiktionary', download_dump_if_not_exists=True)
    site.load_xml_dump(dump_path=f'user_data/dumps/{language}wikt.xml')
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
