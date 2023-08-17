import json

import pika
from flask import Flask
from flask import send_file, Response

from api.config import BotjagwarConfig

PORT = 8443
config = BotjagwarConfig()
app = Flask(__name__)
folder = '/tmp'
# folder = '/root/soamasina_queue'


# RabbitMQ connection parameters
RABBITMQ_HOST = config.get('host', 'rabbitmq')
RABBITMQ_QUEUE = 'lohmasina'
RABBITMQ_USERNAME = config.get('username', 'rabbitmq')
RABBITMQ_PASSWORD = config.get('password', 'rabbitmq')
RABBITMQ_VIRTUAL_HOST = config.get('virtual_host', 'rabbitmq')


def fetch():
    credentials = pika.PlainCredentials(RABBITMQ_USERNAME, RABBITMQ_PASSWORD)
    parameters = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        virtual_host=RABBITMQ_VIRTUAL_HOST,
        credentials=credentials
    )
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()

    method_frame, _, body = channel.basic_get(queue=RABBITMQ_QUEUE, auto_ack=True)
    if method_frame:
        print("Message fetched:", body.decode())
    return json.loads(body.decode())


@app.route('/title.txt', methods=['GET'])
def title():
    """Renders the contact page."""
    return send_file(f'{folder}/title.txt', )


@app.route('/text.txt', methods=['GET'])
def text():
    """Renders the contact page."""
    return send_file(f'{folder}/text.txt', )


@app.route('/next', methods=['GET'])
def next_edit():
    """Renders the contact page."""
    data = fetch()
    with open(f'{folder}/title.txt', 'w') as f:
        f.write(data['page'])

    with open(f'{folder}/text.txt', 'w') as f:
        f.write(data['content'])

    return Response('New title and text updated.', status=200)


if __name__ == '__main__':
    HOST = '0.0.0.0'
    app.run(HOST, PORT)
