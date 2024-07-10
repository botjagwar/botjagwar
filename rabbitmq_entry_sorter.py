import time
from random import choice
from api.decorator import separate_process
from api.rabbitmq import RabbitMqProducer, RabbitMqConsumer


class SimpleEntryTranslatorSorter(object):
    def __init__(self):
        self.consumer = RabbitMqConsumer('translated', callback_function=self.on_page_edit)
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

        self.users = [self.lohataona, self.soavolana, self.ramaromiadana, self.manaona]


    def shuffle_queue(self, **arguments):
        pass

    def language_specialist(self, **arguments):
        # self.backup.push_to_queue(arguments)
        content = arguments['content']

        # bot handles
        conditions = '-e-mat-' in content or '-e-ana-' in content
        if conditions:
            print(f'{arguments["page"]} > botjagwar')
            while self.bot is None:
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

            return self.manaona.push_to_queue(arguments)

        # soavolana handles
        conditions = False
        for language in 'fr it de es pt de nl sv no'.split():
            conditions = conditions or '{{=' + language + '=}}' in content
        if conditions:
            print(f'{arguments["page"]} > soavolana')
            while self.soavolana is None:
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

            return self.ramaromiadana.push_to_queue(arguments)

        # lohataona handles
        conditions = False
        for language in 'sw zu af am sq oc ca tr bg ro pl cs sk da be lt lv he my'.split():
            conditions = conditions or '{{=' + language + '=}}' in content
        if conditions:
            print(f'{arguments["page"]} > ramaromiadana')
            while self.lohataona is None:
                time.sleep(1)

            return self.lohataona.push_to_queue(arguments)

        print(f'{arguments["page"]} > botjagwar')
        while self.bot is None:
            time.sleep(1)

        return choice(self.users).push_to_queue(arguments)

    def run(self):
        self.consumer.run()

    on_page_edit = language_specialist


if __name__ == '__main__':
    @separate_process
    def runner():
        bot = SimpleEntryTranslatorSorter()
        bot.run()


    runner()
