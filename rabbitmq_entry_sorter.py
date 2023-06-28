import time

from api.decorator import separate_process
from api.rabbitmq import RabbitMqProducer, RabbitMqConsumer


class SimpleEntryTranslatorSorter(object):
    def __init__(self):
        self.consumer = RabbitMqConsumer('temp_triage', callback_function=self.on_page_edit)
        # self.backup = RabbitMqProducer('translated_backlog_bkp')
        self.bot = None
        self.soavolana = None
        self.lohataona = None
        self.ramaromiadana = None
        self.manaona = None

        def init_bot():
            self.bot = RabbitMqProducer('botjagwar')

        def init_soavolana():
            self.soavolana = RabbitMqProducer('soavolana')

        def init_lohataona():
            self.lohataona = RabbitMqProducer('lohataona')

        def init_ramaromiadana():
            self.ramaromiadana = RabbitMqProducer('ramaromiadana')

        def init_manaona():
            self.manaona = RabbitMqProducer('manaona')

        init_bot()
        init_soavolana()
        init_lohataona()
        init_ramaromiadana()
        init_manaona()

    def run(self):
        self.consumer.run()

    def on_page_edit(self, **arguments):
        # self.backup.push_to_queue(arguments)
        content = arguments['content']

        # bot handles
        conditions = '-e-mat-' in content or '-e-ana-' in content
        if conditions:
            print(f'{arguments["page"]} > botjagwar')
            while self.bot is None:
                time.sleep(1)
            while not self.bot.is_ready:
                time.sleep(1)

            return self.bot.push_to_queue(arguments)

        # manaona handles
        conditions = False
        for language in 'ja zh ko cmn vi sw zu th mn tl bo ne kk'.split():
            conditions = conditions or '{{=' + language + '=}}' in content
        if conditions:
            print(f'{arguments["page"]} > manaona')
            while self.manaona is None:
                time.sleep(1)
            while not self.manaona.is_ready:
                time.sleep(1)

            return self.manaona.push_to_queue(arguments)

        # soavolana handles
        conditions = False
        for language in 'fr it de es pt de nl sv no'.split():
            conditions = conditions or '{{=' + language + '=}}' in content
        if conditions:
            print(f'{arguments["page"]} > soavolana')
            while self.soavolana is None:
                time.sleep(1)
            while not self.soavolana.is_ready:
                time.sleep(1)

            return self.soavolana.push_to_queue(arguments)

        # ramaromiadana handles
        conditions = False
        for language in 'et fi ar fa tr ml ta si el bg ru'.split():
            conditions = conditions or '{{=' + language + '=}}' in content
        if conditions:
            print(f'{arguments["page"]} > ramaromiadana')
            while self.ramaromiadana is None:
                time.sleep(1)
            while not self.ramaromiadana.is_ready:
                time.sleep(1)

            return self.ramaromiadana.push_to_queue(arguments)

        print(f'{arguments["page"]} > lohataona')
        while self.lohataona is None:
            time.sleep(1)

        return self.lohataona.push_to_queue(arguments)


if __name__ == '__main__':
    @separate_process
    def runner():
        bot = SimpleEntryTranslatorSorter()
        bot.run()


    runner()
