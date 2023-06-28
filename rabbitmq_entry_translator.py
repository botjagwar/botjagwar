import random
import sys
import time

import requests

from api.decorator import separate_process
from api.rabbitmq import RabbitMqConsumer

service_port = int(sys.argv[1])

class SimpleEntryTranslatorClientFeeder(object):
    def __init__(self):
        self.consumer = RabbitMqConsumer('edit', callback_function=self.on_page_edit)

    def run(self):
        self.consumer.run()

    def on_page_edit(self, **arguments):
        cool_down = True
        while cool_down:
            resp = requests.get(f'http://localhost:{service_port}/jobs')
            data = resp.json()
            if data['jobs'] < 10:
                print(f'There are {data["jobs"]} jobs currently in progress')
                cool_down = False
            else:
                print(f'COOLING DOWN: sleeping for 5 seconds as there are {data["jobs"]} jobs currently in progress')
                time.sleep(5)

        site = arguments.get('site', 'en')
        title = arguments.get('title', '')
        print(f'>>> {site} :: {title} <<<')
        roll = random.randint(0, 100)
        if roll < 101:
            route = 'wiktionary_page_async'
        else:
            route = 'wiktionary_page'

        resp = requests.post(f'http://localhost:{service_port}/{route}/{site}', json={'title': title})
        print(resp.status_code)
        if resp.status_code != 200:
            print('Error! ', resp.status_code)
        if 400 <= resp.status_code < 600:
            print('Error! ', resp.status_code, resp.json())


if __name__ == '__main__':
    @separate_process
    def runner():
        bot = SimpleEntryTranslatorClientFeeder()
        bot.run()


    for i in range(2):
        runner()
        time.sleep(1.5)
