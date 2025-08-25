import json

import pika
import sys
import time

from redis_wikicache import RedisPage, RedisSite

from api.config import BotjagwarConfig

config = BotjagwarConfig()

if len(sys.argv) < 4:
    print("Usage: python add_to_edit_queue.py <en_file> <mg_file> <action>")
    print("Available actions: publish_to_rabbitmq_channel")
    sys.exit(1)

en_file = sys.argv[1]
mg_file = sys.argv[2]
action = sys.argv[3]

with open(en_file, "r") as f:
    en_entries = {k.strip("\n").strip().replace("_", " ") for k in f.readlines()}

with open(mg_file, "r") as f:
    mg_entries = {k.strip("\n").strip().replace("_", " ") for k in f.readlines()}

try:
    with open(en_file, "r") as f:
        to_create = {k.strip("\n").strip().replace("_", " ") for k in f.readlines()}
except FileNotFoundError:
    to_create = set()

if to_create:
    to_create = en_entries - mg_entries
else:
    to_create = en_entries - mg_entries - to_create

print(f"Golden source contains {len(en_entries)} entries")
print(f"Non-golden source contains {len(mg_entries)} entries")
print(f"{len(to_create)} entries will be created.")

# ---------------------------------------------------------------------------------------------------------------------

print("Connecting to RabbitMQ")

RABBITMQ_HOST = config.get("host", "rabbitmq")
RABBITMQ_QUEUE = "edit"
RABBITMQ_USERNAME = config.get("username", "rabbitmq")
RABBITMQ_PASSWORD = config.get("password", "rabbitmq")
RABBITMQ_VIRTUAL_HOST = config.get("virtual_host", "rabbitmq")

print(f"rabbitmq_host = {RABBITMQ_HOST}")
print(f"rabbitmq_queue = {RABBITMQ_QUEUE}")
print(f"rabbitmq_username = {RABBITMQ_USERNAME}")
print(f"rabbitmq_password = {RABBITMQ_PASSWORD}")
print(f"rabbitmq_virtual_host = {RABBITMQ_VIRTUAL_HOST}")

# Create credentials for RabbitMQ authentication
credentials = pika.PlainCredentials(RABBITMQ_USERNAME, RABBITMQ_PASSWORD)

# Establish a connection to RabbitMQ with authentication and vhost
parameters = pika.ConnectionParameters(
    host=RABBITMQ_HOST, virtual_host=RABBITMQ_VIRTUAL_HOST, credentials=credentials
)

print("Connection OK.")


def publish_to_rabbitmq_channel(channel=RABBITMQ_QUEUE):
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)

    def publish(page):
        message = json.dumps({"site": "en", "title": page, "user": "Jagwar"})
        channel.basic_publish(
            exchange="",
            routing_key=channel,
            body=bytes(message, encoding="utf8"),
            properties=pika.BasicProperties(
                delivery_mode=2  # Makes the message persistent
            ),
        )
        time.sleep(0.005)

    return publish


function = eval(action)

for page in to_create:
    function(page)
