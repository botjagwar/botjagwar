import json

import pika

from api import entryprocessor
from api.config import BotjagwarConfig
from api.model.word import Entry
from api.output import Output
from redis_wikicache import RedisPage as Page, RedisSite as Site

config = BotjagwarConfig()
output = Output('mg')


class VerbFormGenerator():
    def __init__(self, root):
        self.root = root
        self.voices = {
            '': 'fiendrika manano',
            'p': 'fiendrika anoina',
        }
        self.tenses = {
            '': 'ankehitriny',
            'ä': 'lasa tsy efa',
            'e': 'ankehitriny efa',
            'i': 'lasa efa',
            'o': 'ho avy',
            'ö': "ho avin'ny lasa",
            'u': 'ho avy efa',
            'ü': "hoavin'ny lasa efa",
        }
        self.persons = {
            'ob': 'Mpandray anjara voalohany',
            'ol': 'Mpandray anjara faharoa',
            'on': 'Mpandray anjara fahatelo',
            # 'obs': 'Mpandray anjara voalohany ploraly',
            # 'ols': 'Mpandray anjara faharoa ploraly',
            # 'ons': 'Mpandray anjara fahatelo ploraly',
            # 'os': "Endrika tsy manonona mpandray anjara",
            # 'oy': "Mpandray anjara tsy voalaaza",
            # 'ods': "Mpandray anjara mifanao",
        }

    @property
    def forms(self):
        ret = []
        for tense in self.tenses:
            for voice in self.voices:
                for person in self.persons:
                    if voice == 'p' and tense == '':
                        prefix_tense = 'a'
                    else:
                        prefix_tense = tense
                    word = f"{voice}{prefix_tense}{self.root}{person}"
                    definition = f"{self.persons[person]} ny filazam-potoana {self.tenses[tense]} amin'ny {self.voices[voice]} "
                    definition += f'ny matoanteny [[{self.root}ön]].'
                    entry = Entry(
                        entry=word,
                        part_of_speech='e-mat',
                        definitions=[definition],
                        language='vo',
                    )
                    ret.append(entry)
        return ret


class VolapukImporter(object):
    def __init__(self):
        self._connection = None
        self._channel = None
        self._queue_name = None

    def set_queue(self, queue_name):

        self._queue_name = queue_name
        self._channel.queue_declare(queue=queue_name)

    def __del__(self):
        # Close the connection
        if self._connection:
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

    def initialize_rabbitmq(self):
        rabbitmq_host = config.get('host', 'rabbitmq')
        rabbitmq_queue = 'ikotobaity'
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
        self._channel.queue_declare(queue=self._queue_name)

    def publish(self, entry):
        print(entry)
        target_page = Page(Site('mg', 'wiktionary'), entry.entry, offline=False)

        if target_page.namespace().id != 0:
            raise Exception(
                f'Attempted to push translated page to {target_page.namespace().custom_name} '
                f'namespace (ns:{target_page.namespace().id}). '
                f'Can only push to ns:0 (main namespace)')
        elif target_page.isRedirectPage():
            content = output.wikipages([entry])
            print(">>> " + entry.entry + ' <<<')
            print(content)
            self.async_put(target_page, content, "/* {{=vo=}} */")
        else:
            # Get entries to aggregate
            original_content = ''
            if target_page.exists():
                wiktionary_processor_class = entryprocessor.WiktionaryProcessorFactory.create('mg')
                wiktionary_processor = wiktionary_processor_class()
                wiktionary_processor.set_text(target_page.get())
                wiktionary_processor.set_title(entry)
                original_content = content = target_page.get()
                summary = "/* {{=vo=}} */"
                content = output.delete_section(entry.language, content)
                content += '\n'
                content += output.wikipages([entry]).strip()
            else:
                content = ""
                content += '\n'
                content += output.wikipages([entry]).strip()
                s = content.replace('\n', ' ')
                # summary = f"Pejy noforonina tamin'ny « {s} »"
                summary = f"endri-teny volapoka vaovao avy"

            # Push aggregated content
            print(">>> " + entry.entry + ' <<<')
            # print(content)
            if len(content) > len(original_content):
                self.async_put(target_page, content.strip('\n'), summary)

    def run(self):
        with open("user_data/list_mg_Matoanteny amin'ny teny volapoky") as pages:
            pages = [k.strip('\n') for k in pages.readlines()]
        count = 0
        for page in pages:
            main_form = VerbFormGenerator(page[:-2])
            for entry in main_form.forms:
                print(count)
                count += 1
                # print(entry)
                print(entry, entry.language, entry.definitions)
                self.publish(entry)

        print(count)

    def async_put(self, page, content, summary, minor=False):
        message = json.dumps({
            'language': page.site.language,
            'site': page.site.wiki,
            'page': page.title(),
            "content": content,
            'summary': summary,
            'minor': minor,
        })
        self.message_broker_channel.basic_publish(exchange='', routing_key=self._queue_name, body=message)


if __name__ == '__main__':
    bot = VolapukImporter()
    bot.run()
