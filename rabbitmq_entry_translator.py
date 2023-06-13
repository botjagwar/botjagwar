import time

import requests

from api.decorator import separate_process
from api.rabbitmq import RabbitMqConsumer


class SimpleEntryTranslatorClientFeeder(object):
    def __init__(self):
        self.consumer = RabbitMqConsumer('edit', callback_function=self.on_page_edit)

    def run(self):
        self.consumer.run()

    def on_page_edit(self, **arguments):
        time.sleep(4.5)
        site = arguments.get('site', 'en')
        title = arguments.get('title', '')
        print(f'>>> {site} :: {title} <<<')

        resp = requests.post(f'http://localhost:8000/wiktionary_page_async/{site}', json={'title': title})
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
