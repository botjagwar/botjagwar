import json

import pika
from flask import Flask, request
from flask import send_file, Response

from api.config import BotjagwarConfig

PORT = 8443
config = BotjagwarConfig()
app = Flask(__name__)
folder = '/tmp'
# folder = '/root/user_queue'


# RabbitMQ connection parameters
RABBITMQ_HOST = config.get('host', 'rabbitmq')
RABBITMQ_QUEUE = 'lohataona'
RABBITMQ_USERNAME = config.get('username', 'rabbitmq')
RABBITMQ_PASSWORD = config.get('password', 'rabbitmq')
RABBITMQ_VIRTUAL_HOST = config.get('virtual_host', 'rabbitmq')

#
MANDATORY_FIELDS = {
    'detault': [
        'language',
        'site',
        'page',
        'content',
        "summary",
        "minor"
    ],
    'edit': [
        'site',
        'title',
        'user',
    ]
}


def make_channel():
    credentials = pika.PlainCredentials(RABBITMQ_USERNAME, RABBITMQ_PASSWORD)
    parameters = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        virtual_host=RABBITMQ_VIRTUAL_HOST,
        credentials=credentials
    )
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    return channel


def push(queue_name, message):
    channel = make_channel()
    channel.basic_publish(exchange='', routing_key=queue_name, body=message)


def fetch(queue_name='user'):
    channel = make_channel()
    method_frame, _, body = channel.basic_get(queue=queue_name, auto_ack=True)
    if method_frame:
        print("Message fetched:", body.decode())
    return json.loads(body.decode())


@app.route('/<user>', methods=['POST'])
def send(user):
    data = request.json
    mandatory_fields = MANDATORY_FIELDS[user] \
        if user in MANDATORY_FIELDS \
        else MANDATORY_FIELDS['default']

    for mandatory_field in mandatory_fields:
        if mandatory_field not in data:
            return {"error": f"[{mandatory_field}] field is mandatory."}, 400

    push(user, json.dumps(data))
    return {"message": 'message sent.'}, 204


@app.route('/<user>/title.txt', methods=['GET'])
def title(user='user'):
    """Renders the contact page."""
    return send_file(f'{folder}/{user}_title.txt', )


@app.route('/<user>/text.txt', methods=['GET'])
def text(user='user'):
    """Renders the contact page."""
    return send_file(f'{folder}/{user}_text.txt', )


@app.route('/<user>/next', methods=['GET'])
def next_edit(user='user'):
    """Renders the contact page."""
    data = fetch(user)
    with open(f'{folder}/{user}_title.txt', 'w') as f:
        f.write(data['page'])

    with open(f'{folder}/{user}_text.txt', 'w') as f:
        f.write(data['content'])

    return Response('New title and text updated.', status=200)


if __name__ == '__main__':
    HOST = '0.0.0.0'
    app.run(HOST, PORT)
