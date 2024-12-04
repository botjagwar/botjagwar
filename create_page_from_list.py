import sys
import time

import requests

server = "localhost"
service = 8000  # int(sys.argv[3])


def push_to_entry_translator():
    with open(sys.argv[2], "r") as file:
        for data in file:
            cool_down = True
            while cool_down:
                resp = requests.get(f"http://{server}:{service}/jobs")
                try:
                    resp_data = resp.json()
                except Exception:
                    time.sleep(0.5)
                    continue

                if resp_data["jobs"] < 10:
                    print(f'There are {resp_data["jobs"]} jobs currently in progress')
                    cool_down = False
                else:
                    print(
                        f'COOLING DOWN: sleeping for 15 seconds as there are {resp_data["jobs"]} jobs currently in progress'
                    )
                    time.sleep(15)
            data = data.strip("\n")
            time.sleep(5)
            print(">>>", data, "<<<")
            while True:
                try:
                    requests.post(
                        f"http://{server}:{service}/wiktionary_page/" + sys.argv[1],
                        json={"title": data},
                    )
                    break
                except KeyboardInterrupt:
                    print("Stopped.")
                    break
                except requests.exceptions.ConnectionError:
                    print("Error... retrying in 10s")
                    time.sleep(10)


def push_to_edit_queue():
    from api.rabbitmq import RabbitMqWebService

    publisher = RabbitMqWebService("edit")
    with open(sys.argv[2], "r") as file:
        for data in file:
            # time.sleep(.2)
            print(">>>", data.strip("\n"), "<<<")
            publisher.push_to_queue(
                {
                    "language": "",
                    "page": "",
                    "content": "",
                    "summary": "",
                    "minor": "",
                    "site": sys.argv[1],
                    "title": data.strip("\n"),
                    "user": "Jagwar",
                }
            )


if __name__ == "__main__":
    push_to_edit_queue()
