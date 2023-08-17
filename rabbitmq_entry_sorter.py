import time

from api.decorator import separate_process
from api.rabbitmq import RabbitMqProducer, RabbitMqConsumer


class SimpleEntryTranslatorSorter(object):
    def __init__(self):
        self.consumer = RabbitMqConsumer('temp_triage_2', callback_function=self.on_page_edit)
        # self.backup = RabbitMqProducer('translated_backlog_bkp')
        self.bot = None
        self.soamasina = None
        self.lohmasina = None
        self.ramarobesaina = None
        self.manaona = None

        def init_bot():
            self.bot = RabbitMqProducer('botjagwar')

        def init_soamasina():
            self.soamasina = RabbitMqProducer('soamasina')

        def init_lohmasina():
            self.lohmasina = RabbitMqProducer('lohmasina')

        def init_ramarobesaina():
            self.ramarobesaina = RabbitMqProducer('ramarobesaina')

        def init_manaona():
            self.manaona = RabbitMqProducer('manaona')

        init_bot()
        init_soamasina()
        init_lohmasina()
        init_ramarobesaina()
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

        # soamasina handles
        conditions = False
        for language in 'fr it de es pt de nl sv no'.split():
            conditions = conditions or '{{=' + language + '=}}' in content
        if conditions:
            print(f'{arguments["page"]} > soamasina')
            while self.soamasina is None:
                time.sleep(1)
            while not self.soamasina.is_ready:
                time.sleep(1)

            return self.soamasina.push_to_queue(arguments)

        # ramarobesaina handles
        conditions = False
        for language in 'et fi ar fa tr ml ta si el bg ru'.split():
            conditions = conditions or '{{=' + language + '=}}' in content
        if conditions:
            print(f'{arguments["page"]} > ramarobesaina')
            while self.ramarobesaina is None:
                time.sleep(1)
            while not self.ramarobesaina.is_ready:
                time.sleep(1)

            return self.ramarobesaina.push_to_queue(arguments)

        print(f'{arguments["page"]} > lohmasina')
        while self.lohmasina is None:
            time.sleep(1)

        return self.lohmasina.push_to_queue(arguments)


if __name__ == '__main__':
    @separate_process
    def runner():
        bot = SimpleEntryTranslatorSorter()
        bot.run()


    runner()
