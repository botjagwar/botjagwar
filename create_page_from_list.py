import sys
import time
from typing import Any, Dict

import requests

server = "localhost"
service = 8000  # int(sys.argv[3])


def describe_translation_response(resp: requests.Response) -> Dict[str, Any]:
    """Return parsed translation response data, including fallback error details."""
    try:
        data = resp.json()
    except ValueError:
        return {
            "status": "error",
            "message": resp.text,
            "http_status": resp.status_code,
        }
    if isinstance(data, dict):
        data.setdefault("http_status", resp.status_code)
        return data
    return {
        "status": "unknown",
        "message": "Translation API returned a non-object response.",
        "response": data,
        "http_status": resp.status_code,
    }


def print_translation_response(resp: requests.Response) -> None:
    """Print a concise summary for old and structured translation responses."""
    data = describe_translation_response(resp)
    status = data.get("status")
    title = data.get("title", "")
    if resp.status_code >= 400 or status == "error":
        print(f"Translation failed for {title}: {data}")
        return
    if status:
        entries_count = data.get("entries_count", 0)
        print(f"Translation {status} for {title}: {entries_count} entries")
    else:
        print(data.get("message", "Translation request completed."))


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
            time.sleep(1)
            print(">>>", data, "<<<")
            while True:
                try:
                    response = requests.post(
                        f"http://{server}:{service}/wiktionary-pages/{sys.argv[1]}/translations",
                        json={"title": data},
                    )
                    print_translation_response(response)
                    break
                except KeyboardInterrupt:
                    print("Stopped.")
                    break
                except requests.exceptions.ConnectionError:
                    print("Error... retrying in 10s")
                    time.sleep(10)


def webservice_push_to_edit_queue():
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



def connector_push_to_edit_queue():
    from api.rabbitmq import RabbitMqProducer
    import json
    publisher = RabbitMqProducer("edit")
    with open(sys.argv[2], "r") as file:
        for data in file:
            # time.sleep(.2)
            print(">>>", data.strip("\n"), "<<<")
            message = json.dumps({
                    "language": "",
                    "page": "",
                    "content": "",
                    "summary": "",
                    "minor": "",
                    "site": sys.argv[1],
                    "title": data.strip("\n"),
                    "user": "Jagwar",
            })
            publisher.publish(message)
            # break

if __name__ == "__main__":
    connector_push_to_edit_queue()
