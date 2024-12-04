import json

import pika

from api.config import BotjagwarConfig
from api.output import Output
from redis_wikicache import RedisPage as Page, RedisSite as Site

config = BotjagwarConfig()
output = Output("mg")


class TeluguFixer(object):
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
            print("Initialization compete.")

        return self._queue_name

    def initialize_rabbitmq(self):
        rabbitmq_host = config.get("host", "rabbitmq")
        rabbitmq_queue = "botjagwar"
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

    def async_action(self, page, content="", summary="", action="edit", minor=False):
        print(
            f"Pushing '{action}' action on page {page.title()} to '{self.queue_name}' queue"
        )
        message = json.dumps(
            {
                "language": page.site.language,
                "site": page.site.wiki,
                "page": page.title(),
                "content": content,
                "summary": summary,
                "action": action,
                "minor": minor,
            }
        )
        self.message_broker_channel.basic_publish(
            exchange="",
            routing_key=self.queue_name,
            body=message,
            properties=pika.BasicProperties(delivery_mode=2),
        )


if __name__ == "__main__":
    bot = TeluguFixer()
    # bot.run()
    page = Page(Site("mg", "wiktionary"), "Mpikambana:Jagwar/andrana")
    bot.async_action(action="delete", page=page, summary="andrana")
