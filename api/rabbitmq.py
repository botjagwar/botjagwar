import configparser
import json
import os
import time

import pika
import requests
from pika.exceptions import ChannelWrongStateError

from api.config import BotjagwarConfig
from api.http_client import DEFAULT_HTTP_TIMEOUT
from api.services.rabbitmq_gateway_auth import (
    RabbitMqGatewayAuthError,
    rabbitmq_gateway_auth_headers,
)

config = BotjagwarConfig()
MAX_RABBITMQ_MESSAGE_BYTES = 16 * 1024 * 1024


def _optional_queue_config(key, default):
    """Read one optional queue role without hiding malformed configuration."""
    try:
        value = config.get(key, "rabbitmq")
    except (configparser.Error, KeyError, ValueError):
        return default
    return value.strip() or default


PROTECTED_CONSUMER_QUEUES = frozenset(
    {
        os.environ.get("BOTJAGWAR_PAGE_CHECK_REVIEW_QUEUE")
        or _optional_queue_config("page_check_review_queue", "page-check-review"),
    }
)


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
        rabbitmq_host = config.get("host", "rabbitmq")
        rabbitmq_username = config.get("username", "rabbitmq")
        rabbitmq_password = config.get("password", "rabbitmq")
        rabbitmq_virtual_host = config.get("virtual_host", "rabbitmq")

        # Create credentials for RabbitMQ authentication
        credentials = pika.PlainCredentials(rabbitmq_username, rabbitmq_password)

        # Establish a connection to RabbitMQ with authentication and vhost
        self.parameters = pika.ConnectionParameters(
            host=rabbitmq_host,
            virtual_host=rabbitmq_virtual_host,
            credentials=credentials,
            heartbeat=60,
            blocked_connection_timeout=20,
        )
        self._connection = pika.BlockingConnection(self.parameters)
        self._channel = self._connection.channel()
        self._channel.queue_declare(queue=self._queue_name, durable=True)
        self.is_ready = True


class RabbitMqWebService(object):
    def __init__(self, queue_name="default", gateway_hmac_secret=None):
        self._queue_name = queue_name

        if queue_name != "default":
            self.set_queue(queue_name)
        else:
            self.set_queue(config.get("queue", "rabbitmq"))

        self.service = self._optional_config("service", "rabbitmq") or config.get(
            "host", "rabbitmq"
        )
        self._gateway_hmac_secret = (
            gateway_hmac_secret
            or os.environ.get("BOTJAGWAR_RABBITMQ_GATEWAY_HMAC_SECRET")
            or self._optional_config("gateway_hmac_secret", "rabbitmq")
        )

    @staticmethod
    def _optional_config(key, section):
        """Read one optional gateway setting from application configuration."""
        try:
            value = config.get(key, section)
        except (configparser.Error, KeyError, ValueError):
            return None
        return value.strip() or None

    def set_queue(self, queue_name):
        self._queue_name = queue_name

    @property
    def queue_name(self):
        return self._queue_name

    def publish(self, message: dict):
        try:
            headers = rabbitmq_gateway_auth_headers(
                message,
                self._gateway_hmac_secret,
                expected_queue=self.queue_name,
            )
        except RabbitMqGatewayAuthError as exc:
            raise RabbitMqError(str(exc)) from exc
        response = requests.post(
            f"http://{self.service}:8443/{self.queue_name}",
            json=message,
            timeout=DEFAULT_HTTP_TIMEOUT,
            headers=headers,
        )
        if response.status_code != 204:
            if response.status_code == 400:
                raise RabbitMqError("Data error: " + str(response.json()["error"]))
            else:
                raise RabbitMqError(f"Unknown error: {response.text}")

    def push_to_queue(self, message: dict):
        self.publish(message)


class RabbitMqConsumer(RabbitMqConnector):
    def __init__(self, queue, callback_function):
        if queue in PROTECTED_CONSUMER_QUEUES:
            raise RabbitMqError(
                "Generic RabbitMQ consumers cannot use protected queue roles."
            )
        super(RabbitMqConsumer, self).__init__(queue)
        self.callback_function = callback_function

    def callback(self, ch, method, properties, arguments):
        try:
            if (
                not isinstance(arguments, bytes)
                or len(arguments) > MAX_RABBITMQ_MESSAGE_BYTES
            ):
                raise ValueError("RabbitMQ sorter message is too large.")
            decoded = json.loads(arguments.decode("utf-8"))
            if not isinstance(decoded, dict):
                raise ValueError("RabbitMQ sorter message must be an object.")
            self.callback_function(**decoded)
        except (
            json.JSONDecodeError,
            KeyError,
            RecursionError,
            TypeError,
            UnicodeDecodeError,
            ValueError,
        ):
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        except Exception:
            ch.basic_nack(
                delivery_tag=method.delivery_tag,
                requeue=not bool(getattr(method, "redelivered", False)),
            )
        else:
            ch.basic_ack(delivery_tag=method.delivery_tag)

    def consume_messages(self):
        self._channel.basic_qos(prefetch_count=1)
        print(f"Consuming {self._queue_name}")
        self._channel.basic_consume(
            queue=self._queue_name, on_message_callback=self.callback
        )
        self._channel.start_consuming()

    # @separate_process
    def run(self):
        self.consume_messages()


class RabbitMqWikipageProducer(RabbitMqWebService):
    def async_put(self, page, content, summary, minor=False):
        message = {
            "language": page.site.language,
            "site": page.site.wiki,
            "page": page.title(),
            "content": content,
            "summary": summary,
            "minor": minor,
        }
        self.publish(message)


class RabbitMqProducer(RabbitMqConnector):
    def __init__(self, queue_name="default"):
        print(f"Initializing queue {queue_name}")
        super(RabbitMqProducer, self).__init__(queue_name)
        self._channel.confirm_delivery()

        if queue_name != "default":
            self.set_queue(queue_name)
        else:
            self.set_queue(config.get("queue", "rabbitmq"))

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

    def reopen_channel(self):
        self.is_ready = False
        self._connection = pika.BlockingConnection(self.parameters)
        self._channel = self._connection.channel()
        self._channel.queue_declare(queue=self._queue_name, durable=True)
        self._channel.confirm_delivery()
        self.is_ready = True

    def ensure_connection_ready(self) -> None:
        """Service heartbeats and reconnect before a message can be sent."""
        try:
            if (
                self._connection is None
                or not self._connection.is_open
                or self._channel is None
                or not self._channel.is_open
            ):
                self.reopen_channel()
                return
            self._connection.process_data_events(time_limit=0)
            if not self._connection.is_open or not self._channel.is_open:
                self.reopen_channel()
        except (OSError, pika.exceptions.AMQPError):
            self.reopen_channel()

    def publish(self, message):
        self.ensure_connection_ready()
        try:
            self.message_broker_channel.basic_publish(
                exchange="",
                routing_key=self._queue_name,
                body=message,
                properties=pika.BasicProperties(delivery_mode=2),
                mandatory=True,
            )
        except ChannelWrongStateError:
            self.reopen_channel()
            self.message_broker_channel.basic_publish(
                exchange="",
                routing_key=self._queue_name,
                body=message,
                properties=pika.BasicProperties(delivery_mode=2),
                mandatory=True,
            )

    def push_to_queue(self, message: dict):
        while not self.is_ready:
            print(
                f"Waiting for {self.__class__.__name__} on {self._queue_name} to be ready..."
            )
            time.sleep(1)

        message = json.dumps(message)
        self.publish(message)
