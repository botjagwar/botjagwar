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


def save_to_wiki(pagename, page_content, summary, action):
    page = pywikibot.Page(pywikibot.Site('mg', 'wiktionary'), pagename)
    if not summary.strip():
        if page.exists():
            summary = 'fanitsiana'
        else:
            summary = f"Pejy noforonina amin'ny « {page_content} »"

    if action == 'edit':
        print(f"SAVING   page: {pagename}, Summary - {summary}")
        page.put(page_content, summary)
    elif action == 'delete':
        print(f"DELETING page: {pagename}, Summary - {summary}")
        page.delete("Hadisoana teo amim-pamoronana ilay pejy")


def callback(ch, method, properties, body):
    # Extract the data from the message
    data = json.loads(body.decode('utf-8'))
    pagename = data['page']
    content = data['content']
    action = data['action'] if 'action' in data else 'edit'
    summary = data['summary']

    # Call the save_to_wiki function with the extracted data
    save_to_wiki(pagename, content, summary, action)

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
    # channel.queue_delete(queue=RABBITMQ_QUEUE)
    print(f"Resetting current queue in use: {RABBITMQ_QUEUE}")
    channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)

    # Set the maximum number of unacknowledged messages
    channel.basic_qos(prefetch_count=1)

    # Set the callback function to consume messages
    print(f"Consuming {RABBITMQ_QUEUE}")
    channel.basic_consume(queue=RABBITMQ_QUEUE, on_message_callback=callback)

    # Start consuming messages
    channel.start_consuming()


# Call the consume_wiki_messages function to start consuming messages from RabbitMQ
consume_wiki_messages()
