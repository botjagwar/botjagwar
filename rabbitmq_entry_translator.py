import sys
import asyncio
import aiohttp
from api.config import BotjagwarConfig

from aiohttp import ClientTimeout
import time
from api.rabbitmq import RabbitMqConsumer

entry_translator_clients = 32
frontend_port = int(BotjagwarConfig().get("backend_port", 'translator'))
backend_port = frontend_port + 10000
current_port = backend_port


class SimpleEntryTranslatorClientFeeder:
    cooldown = 5


    def __init__(self, host="localhost", port=None):
        self.host = host
        self.port = int(port) if port is not None else frontend_port
        self.route = "wiktionary_page_async"
        self.consumer = RabbitMqConsumer("edit", callback_function=self.on_page_edit)

    def run(self):
        self.consumer.run()

    def on_page_edit(self, **arguments):
        additional_args = {"context": self}
        arguments |= additional_args
        try:
            asyncio.run(self.on_page_edit_async(**arguments))
        except Exception as error:
            print(error)
            return

    @staticmethod
    async def on_page_edit_async(**arguments):
        global current_port
        context = arguments.get("context")
        async with aiohttp.ClientSession(timeout=ClientTimeout(total=10)) as session:
            while True:
                if current_port >= backend_port + entry_translator_clients:
                    current_port = backend_port + 1
                else:
                    current_port += 1

                async with session.get(f"http://{context.host}:{current_port}/jobs") as resp:
                    data = await resp.json()
                    print(data["jobs"], f'jobs in queue for {current_port}')

                if data["jobs"] < 30:
                    break
                else:
                    print("Sleeping for 1 seconds")
                    await asyncio.sleep(.5)


            site = arguments.get("site", "en")
            title = arguments.get("title", "")
            print(f">>> {site} :: {title} <<<")
            url = f"http://{context.host}:{current_port}/{context.route}/{site}"
            print(url)
            async with session.post(url, json={"title": title}) as resp:
                print(resp.status)
                if resp.status != 200:
                    print("Error! ", resp.status)
                if 400 <= resp.status < 600:
                    print("Error! ", resp.status, await resp.json())



if __name__ == "__main__":
    service_port = 8000 if len(sys.argv) < 2 else int(sys.argv[1])
    bot = SimpleEntryTranslatorClientFeeder(host="localhost", port=service_port)
    bot.run()
