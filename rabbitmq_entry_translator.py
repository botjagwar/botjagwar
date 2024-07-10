import random
import sys
import time
import requests
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
                print(f'COOLING DOWN: sleeping for 15 seconds as there are {data["jobs"]} '
                      f'jobs currently in progress')
                time.sleep(15)

        site = arguments.get('site', 'en')
        title = arguments.get('title', '')
        print(f'>>> {site} :: {title} <<<')
        route = 'wiktionary_page_async'

        url = f'http://localhost:{service_port}/{route}/{site}'
        print(url)
        resp = requests.post(url, json={'title': title})
        print(resp.status_code)
        if resp.status_code != 200:
            print('Error! ', resp.status_code)
        if 400 <= resp.status_code < 600:
            print('Error! ', resp.status_code, resp.json())
        time.sleep(5)


if __name__ == '__main__':
    bot = SimpleEntryTranslatorClientFeeder()
    bot.run()