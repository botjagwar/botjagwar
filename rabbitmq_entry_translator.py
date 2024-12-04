import sys
import asyncio
import aiohttp
from aiohttp import ClientTimeout
import time
from api.rabbitmq import RabbitMqConsumer


class SimpleEntryTranslatorClientFeeder:
    cooldown = 5

    def __init__(self, host="localhost", port=None):
        self.host = host
        self.port = int(port) if port is not None else 8000
        self.route = "wiktionary_page_async"
        self.consumer = RabbitMqConsumer("edit", callback_function=self.on_page_edit)

    def run(self):
        self.consumer.run()

    def on_page_edit(self, **arguments):
        time.sleep(1.0)
        additional_args = {"context": self}
        arguments.update(additional_args)
        try:
            asyncio.run(self.on_page_edit_async(**arguments))
        except Exception:
            return

    @staticmethod
    async def on_page_edit_async(**arguments):
        context = arguments.get("context")
        async with aiohttp.ClientSession(timeout=ClientTimeout(total=600)) as session:
            cool_down = True
            while cool_down:
                await asyncio.sleep(0.25)
                async with session.get(
                    f"http://{context.host}:{context.port}/jobs"
                ) as resp:
                    data = await resp.json()
                    if data["jobs"] < 10:
                        print(f'There are {data["jobs"]} jobs currently in progress')
                        cool_down = False
                    else:
                        print(
                            f'COOLING DOWN: sleeping for {context.cooldown} seconds as there are {data["jobs"]} '
                            f"jobs currently in progress"
                        )
                        await asyncio.sleep(context.cooldown)
                        context.cooldown *= 1.5

            context.cooldown /= 1.2
            site = arguments.get("site", "en")
            title = arguments.get("title", "")
            print(f">>> {site} :: {title} <<<")
            await asyncio.sleep(0.8)
            url = f"http://{context.host}:{context.port}/{context.route}/{site}"
            print(url)
            async with session.post(url, json={"title": title}) as resp:
                print(resp.status)
                if resp.status != 200:
                    print("Error! ", resp.status)
                if 400 <= resp.status < 600:
                    print("Error! ", resp.status, await resp.json())
            await asyncio.sleep(1)
            await asyncio.sleep(context.cooldown)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        service_port = 8000
    else:
        service_port = int(sys.argv[1])

    bot = SimpleEntryTranslatorClientFeeder(host="192.168.1.197", port=service_port)
    bot.run()
