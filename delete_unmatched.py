import json

import pika
import sys

from api.config import BotjagwarConfig

config = BotjagwarConfig()

golden_file = sys.argv[1]
non_golden_file = sys.argv[2]

with open(golden_file, 'r') as f:
    golden_source = set([k.strip('\n').strip() for k in f.readlines()])

with open(non_golden_file, 'r') as f:
    non_golden_source = set([k.strip('\n').strip() for k in f.readlines()])

try:
    with open(non_golden_file, 'r') as f:
        already_deleted_entries = set([k.strip('\n').strip() for k in f.readlines()])
except FileNotFoundError:
    already_deleted_entries = set()

if already_deleted_entries:
    to_delete = non_golden_source - golden_source
else:
    to_delete = non_golden_source - golden_source - already_deleted_entries

print(f'Golden source contains {len(golden_source)} entries')
print(f'Non-golden source contains {len(non_golden_source)} entries')
print(f'{len(to_delete)} entries will be deleted.')

# ---------------------------------------------------------------------------------------------------------------------

print("Connecting to RabbitMQ")

RABBITMQ_HOST = config.get('host', 'rabbitmq')
RABBITMQ_QUEUE = 'jagwar'
RABBITMQ_USERNAME = config.get('username', 'rabbitmq')
RABBITMQ_PASSWORD = config.get('password', 'rabbitmq')
RABBITMQ_VIRTUAL_HOST = config.get('virtual_host', 'rabbitmq')

print(f"rabbitmq_host = {RABBITMQ_HOST}")
print(f"rabbitmq_queue = {RABBITMQ_QUEUE}")
print(f"rabbitmq_username = {RABBITMQ_USERNAME}")
print(f"rabbitmq_password = {RABBITMQ_PASSWORD}")
print(f"rabbitmq_virtual_host = {RABBITMQ_VIRTUAL_HOST}")

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
channel.queue_declare(queue=RABBITMQ_QUEUE)

print('Connection OK.')

for page in to_delete:
    print(f"To delete: {page}")
    message = json.dumps({
        'language': 'mg',
        'site': 'wiktionary',
        'page': page,
        "content": '',
        'summary': '',
        'action': 'delete',
        'minor': True,
    })
    channel.basic_publish(exchange='', routing_key=RABBITMQ_QUEUE, body=bytes(message, encoding='utf8'))
