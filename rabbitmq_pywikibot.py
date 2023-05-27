import json

import pika
import pywikibot

from api.config import BotjagwarConfig

config = BotjagwarConfig()

# RabbitMQ connection parameters
RABBITMQ_HOST = config.get('host', 'rabbitmq')
RABBITMQ_QUEUE = config.get('queue', 'rabbitmq')
RABBITMQ_USERNAME = config.get('username', 'rabbitmq')
RABBITMQ_PASSWORD = config.get('password', 'rabbitmq')
RABBITMQ_VIRTUAL_HOST = config.get('virtual_host', 'rabbitmq')


def save_to_wiki(pagename, page_content, summary):
    print(f"Saving to wiki: Page name - {pagename}, Content - {page_content}, Summary - {summary}")
    page = pywikibot.Page(pywikibot.Site('mg', 'wiktionary'), pagename)
    if not summary.strip():
        if page.exists():
            summary = 'fanitsiana'
        else:
            summary = f"Pejy noforonina amin'ny « {page_content} »"
    page.put(page_content, summary)


def callback(ch, method, properties, body):
    # Extract the data from the message
    data = json.loads(body.decode('utf-8'))
    pagename = data['page']
    content = data['content']
    summary = data['summary']

    # Call the save_to_wiki function with the extracted data
    save_to_wiki(pagename, content, summary)

    # Acknowledge the message
    ch.basic_ack(delivery_tag=method.delivery_tag)


def consume_wiki_messages():
    # Create credentials for RabbitMQ authentication
    credentials = pika.PlainCredentials(RABBITMQ_USERNAME, RABBITMQ_PASSWORD)

    # Establish a connection to RabbitMQ with authentication and vhost
    parameters = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        virtual_host=RABBITMQ_VIRTUAL_HOST,
        credentials=credentials
    )
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()

    # Declare the queue from which messages will be consumed
    channel.queue_delete(queue=RABBITMQ_QUEUE)

    # Declare the new queue with the desired x-queue-type value
    channel.queue_declare(queue=RABBITMQ_QUEUE)

    # Set the maximum number of unacknowledged messages
    channel.basic_qos(prefetch_count=1)

    # Set the callback function to consume messages
    channel.basic_consume(queue=RABBITMQ_QUEUE, on_message_callback=callback)

    # Start consuming messages
    channel.start_consuming()


# Call the consume_wiki_messages function to start consuming messages from RabbitMQ
consume_wiki_messages()
