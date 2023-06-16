import json

import pika

from api.config import BotjagwarConfig

config = BotjagwarConfig()


class RabbitMqError(Exception):
    pass


class RabbitMq(object):
    def __init__(self, queue_name):
        self._queue_name = queue_name
        self._connection = None
        self._channel = None
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
        parameters = pika.ConnectionParameters(
            host=rabbitmq_host,
            virtual_host=rabbitmq_virtual_host,
            credentials=credentials
        )
        self._connection = pika.BlockingConnection(parameters)
        self._channel = self._connection.channel()
        self._channel.queue_declare(queue=self._queue_name)


class RabbitMqConsumer(RabbitMq):
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


class RabbitMqProducer(RabbitMq):
    def __init__(self, queue_name='default'):
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

    def push_to_queue(self, message):
        message = json.dumps(message)
        self.message_broker_channel.basic_publish(exchange='', routing_key=self._queue_name, body=message)


class RabbitMqWikipageProducer(RabbitMqProducer):
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
