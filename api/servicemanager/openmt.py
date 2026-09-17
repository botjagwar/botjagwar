import requests

from api.config import BotjagwarConfig
from api.http_client import DEFAULT_HTTP_TIMEOUT


class OpenMtTranslation(object):
    endpoint = "/translate"
    backend = BotjagwarConfig().get("backend_address", "openmt")

    def __init__(self, source="en", target="mg"):
        self.source = source
        self.target = target

    def get_translation(self, sentence: str):
        data = {"text": sentence}
        response = requests.post(
            f"{self.backend}/translate/{self.source}/{self.target}",
            json=data,
            timeout=DEFAULT_HTTP_TIMEOUT,
        )
        return response.json()["text"]
