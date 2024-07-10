import json
import time

import pika
import requests
from pika.exceptions import ChannelWrongStateError

from api.config import BotjagwarConfig

config = BotjagwarConfig()


class RabbitMqError(Exception):
    pass


class RabbitMqConnector(object):
    def __init__(self, queue_name):
        self._queue_name = queue_name
        self._connection = None
        self._channel = None
        self.is_ready = False
        self.initialize_rabbitmq()

    @property
    def queue(self):
        return self._queue_name

    def initialize_rabbitmq(self):
        rabbitmq_host = config.get('host', 'rabbitmq')
        rabbitmq_username = config.get('username', 'rabbitmq')
        rabbitmq_password = config.get('password', 'rabbitmq')
        rabbitmq_virtual_host = config.get('virtual_host', 'rabbitmq')

        # Create credentials for RabbitMQ authentication
        credentials = pika.PlainCredentials(rabbitmq_username, rabbitmq_password)

        # Establish a connection to RabbitMQ with authentication and vhost
        self.parameters = pika.ConnectionParameters(
            host=rabbitmq_host,
            virtual_host=rabbitmq_virtual_host,
            credentials=credentials
        )
        self._connection = pika.BlockingConnection(self.parameters)
        self._channel = self._connection.channel()
        self._channel.queue_declare(queue=self._queue_name)
        self.is_ready = True


class RabbitMqWebService(object):
    def __init__(self, queue_name='default'):
        self._queue_name = queue_name

        if queue_name != 'default':
            self.set_queue(queue_name)
        else:
            self.set_queue(config.get('queue', 'rabbitmq'))

        self.service = config.get('host', 'rabbitmq')

    def set_queue(self, queue_name):
        self._queue_name = queue_name

    @property
    def queue_name(self):
        return self._queue_name

    def publish(self, message: dict):

        response = requests.post(f"http://{self.service}:8443/{self.queue_name}", json=message)
        if response.status_code != 204:
            if response.status_code == 400:
                raise RabbitMqError("Data error: " + str(response.json()['error']))
            else:
                raise RabbitMqError("Unknown error: " + str(response.text))

    def push_to_queue(self, message: dict):
        self.publish(message)


class RabbitMqConsumer(RabbitMqConnector):
    def __init__(self, queue, callback_function):
        super(RabbitMqConsumer, self).__init__(queue)
        self.callback_function = callback_function

    def callback(self, ch, method, properties, arguments):
        print(properties, arguments)
        # Extract the data from the message
        arguments = json.loads(arguments.decode('utf-8'))
        self.callback_function(**arguments)
        ch.basic_ack(delivery_tag=method.delivery_tag)

    def consume_messages(self):
        self._channel.basic_qos(prefetch_count=1)
        print(f"Consuming {self._queue_name}")
        self._channel.basic_consume(queue=self._queue_name, on_message_callback=self.callback)
        self._channel.start_consuming()

    # @separate_process
    def run(self):
        self.consume_messages()


class RabbitMqWikipageProducer(RabbitMqWebService):
    def async_put(self, page, content, summary, minor=False):
        message = {
            'language': page.site.language,
            'site': page.site.wiki,
            'page': page.title(),
            "content": content,
            'summary': summary,
            'minor': minor,
        }
        self.publish(message)


class RabbitMqProducer(RabbitMqConnector):
    def __init__(self, queue_name='default'):
        print(f'Initializing queue {queue_name}')
        super(RabbitMqProducer, self).__init__(queue_name)

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

    def reopen_channel(self):
        self.is_ready = False
        self._connection = pika.BlockingConnection(self.parameters)
        self._channel = self._connection.channel()
        self._channel.queue_declare(queue=self._queue_name)
        self.is_ready = True

    def publish(self, message):
        try:
            self.message_broker_channel.basic_publish(exchange='', routing_key=self._queue_name, body=message)
        except ChannelWrongStateError as error:
            self.reopen_channel()
            self.message_broker_channel.basic_publish(exchange='', routing_key=self._queue_name, body=message)

    def push_to_queue(self, message: dict):
        while not self.is_ready:
            print(f"Waiting for {self.__class__.__name__} on {self._queue_name} to be ready...")
            time.sleep(1)

        message = json.dumps(message)
        self.publish(message)
