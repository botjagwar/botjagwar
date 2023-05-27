import json

import pika

# RabbitMQ connection parameters
RABBITMQ_HOST = 'terakasorotany.com'
RABBITMQ_QUEUE = 'edit'
RABBITMQ_USERNAME = 'botjagwar'
RABBITMQ_PASSWORD = 'ASjwKEjiSAJ13J823'
RABBITMQ_VIRTUAL_HOST = 'botjagwar'


def push_to_edit_queue(message):
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

    # Declare the queue
    channel.queue_declare(queue=RABBITMQ_QUEUE)

    # Publish the message to the queue
    channel.basic_publish(exchange='', routing_key=RABBITMQ_QUEUE, body=message)

    # Close the connection
    connection.close()


data = {
    'page': 'Mpikambana:Jagwar/andrana',
    "content": 'andrana ihany ity',
    'summary': 'pejy vaovao'
}
# Example usage
message = json.dumps(data)
push_to_edit_queue(message)
