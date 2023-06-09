import json

import pika

from api.config import BotjagwarConfig

config = BotjagwarConfig()


class RabbitMqPublisher(object):
    def __init__(self, queue_name='default'):
        self._connection = None
        self._channel = None
        self._queue_name = None
        self.initialize_rabbitmq()

        if queue_name != 'default':
            self.set_queue(queue_name)
        else:
            self.set_queue(config.get('queue', 'rabbitmq'))

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

    def push_to_queue(self, message):
        message = json.dumps(message)
        self.message_broker_channel.basic_publish(exchange='', routing_key=self._queue_name, body=message)

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
