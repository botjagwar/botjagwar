import json

import pika

from api import entryprocessor
from api.config import BotjagwarConfig
from api.model.word import Entry
from api.output import Output
from api.translation_v2.functions.definitions.language_model_based import (
    translate_using_nllb,
)
from redis_wikicache import RedisPage as Page, RedisSite as Site

config = BotjagwarConfig()
output = Output("mg")
translated = {
    "subsat": "ana",
    "värb": "mat",
    "ladvärb": "tamb",
    "ladyek": "mpam",
    "lintelek": "mp.ank-teny",
    "konyun": "mpampitohy",
}


class VolapukImporter(object):
    def __init__(self):
        self._connection = None
        self._channel = None
        self._queue_name = None

    def set_queue(self, queue_name):

        self._queue_name = queue_name
        self._channel.queue_declare(queue=queue_name, durable=True)

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
        rabbitmq_host = config.get("host", "rabbitmq")
        rabbitmq_queue = config.get("queue", "rabbitmq")
        self._queue_name = rabbitmq_queue
        rabbitmq_username = config.get("username", "rabbitmq")
        rabbitmq_password = config.get("password", "rabbitmq")
        rabbitmq_virtual_host = config.get("virtual_host", "rabbitmq")

        # Create credentials for RabbitMQ authentication
        credentials = pika.PlainCredentials(rabbitmq_username, rabbitmq_password)

        # Establish a connection to RabbitMQ with authentication and vhost
        parameters = pika.ConnectionParameters(
            host=rabbitmq_host,
            virtual_host=rabbitmq_virtual_host,
            credentials=credentials,
        )
        self._connection = pika.BlockingConnection(parameters)
        self._channel = self._connection.channel()
        self._channel.queue_declare(queue=self._queue_name, durable=True)

    def publish(self, entry):
        print(entry)
        target_page = Page(Site("mg", "wiktionary"), entry.entry, offline=False)

        if target_page.namespace().id != 0:
            raise Exception(
                f"Attempted to push translated page to {target_page.namespace().custom_name} "
                f"namespace (ns:{target_page.namespace().id}). "
                f"Can only push to ns:0 (main namespace)"
            )
        elif target_page.isRedirectPage():
            content = output.wikipages([entry])
            print(">>> " + entry.entry + " <<<")
            print(content)
            self.async_put(target_page, content, "/* {{=vo=}} */")
        else:
            # Get entries to aggregate
            original_content = ""
            if target_page.exists():
                wiktionary_processor_class = (
                    entryprocessor.WiktionaryProcessorFactory.create("mg")
                )
                wiktionary_processor = wiktionary_processor_class()
                wiktionary_processor.set_text(target_page.get())
                wiktionary_processor.set_title(entry)
                original_content = content = target_page.get()
                summary = "/* {{=vo=}} */"
                content = output.delete_section(entry.language, content)
                content += "\n"
                content += output.wikipages([entry]).strip()
            else:
                content = ""
                content += "\n"
                content += output.wikipages([entry]).strip()
                s = content.replace("\n", " ")
                # summary = f"Pejy noforonina tamin'ny « {s} »"
                summary = f"teny volapoka vaovao avy amin'i vo.wiktionary"

            # Push aggregated content
            print(">>> " + entry.entry + " <<<")
            print(content)
            if len(content) > len(original_content):
                self.async_put(target_page, content.strip("\n"), summary)

    def parse_content(self, content):
        part_of_speech = None
        german_definition = None
        word = None
        for line in content.split("\n"):
            if line.startswith("|klad="):
                part_of_speech = line[6:]
            if line.startswith("|WW="):
                german_definition = line[4:]
                german_definition = "; ".join(german_definition.split("<br>"))
            if line.startswith("|vöd="):
                word = line[5:]

        if part_of_speech in translated:
            if german_definition == "N.D":
                german_definition = ""
            return word, translated[part_of_speech], german_definition
        else:
            return word, "...", german_definition

    def run(self):
        with open("user_data/list_vo_Wörterbuch_der_Weltsprache") as pages:
            pages = [k.strip("\n") for k in pages.readlines()]

        for page in pages:
            wikipage = Page(Site("vo", "wiktionary"), page)
            content = wikipage.get()
            word = page
            root, part_of_speech, german_definition = self.parse_content(content)
            if part_of_speech == "..." or not german_definition:
                continue
            mg_translation = translate_using_nllb(
                part_of_speech, german_definition, "de", "mg"
            )
            if not mg_translation:
                continue
            print(f'{word},{part_of_speech},"{mg_translation}"')
            entry = Entry(
                entry=word,
                language="vo",
                part_of_speech=part_of_speech,
                definitions=[mg_translation],
                additional_data={
                    "reference": [
                        "Arie de Jong, Michael Everson: ''Wörterbuch der Weltsprache für Deutschsprechende: "
                        "Vödabuk Volapüka Pro Deutänapükans''"
                    ],
                    "etym/mg": [f"Avy amin'ny teny ''[[{word}]]''"],
                },
            )
            self.publish(entry)
            # time.sleep(36)

    def async_put(self, page, content, summary, minor=False):
        message = json.dumps(
            {
                "language": page.site.language,
                "site": page.site.wiki,
                "page": page.title(),
                "content": content,
                "summary": summary,
                "minor": minor,
            }
        )
        self.message_broker_channel.basic_publish(
            exchange="",
            routing_key=self._queue_name,
            body=message,
            properties=pika.BasicProperties(delivery_mode=2),
        )


if __name__ == "__main__":
    bot = VolapukImporter()
    bot.run()
