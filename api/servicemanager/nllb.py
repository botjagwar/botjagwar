import requests

from api.config import BotjagwarConfig

CONFIG = BotjagwarConfig()
NLLB_CODE = {
    "en": "eng_Latn",
    "fr": "fra_Latn",
    "mg": "plt_Latn",
    "de": "deu_Latn",
    "ru": "rus_Cyrl",
    "uk": "ukr_Cyrl",
    "nl": "nld_Latn",
    "no": "nob_Latn",
    "sv": "swe_Latn",
    "fi": "fin_Latn",
    "da": "dan_Latn",
    "zh": "zho_Hans",
    "cmn": "cmn_Hans",
    "vi": "vie_Latn",
    "id": "ind_Latn",
    "ms": "ind_Latn",
    "fil": "fil_Latn",
    "ko": "kor_Kore",
}


class DefinitionTranslationError(Exception):
    pass


class NllbDefinitionTranslation(object):
    def __init__(self, target_language, source_language="en"):
        """
        Translate using a NLLB service spun up on another server.
        :param target_language:
        :param source_language:
        """
        self.translation_server = CONFIG.get("backend_address", "nllb")
        self.postgrest_server = CONFIG.get("postgrest_backend_address", "global")

        # Translator parameters
        self.source_language = NLLB_CODE.get(source_language, NLLB_CODE["en"])
        self.target_language = NLLB_CODE.get(target_language, NLLB_CODE["mg"])

    def get_translation(self, sentence: str):
        if translation := self.get_translation_in_cache(sentence):
            return translation
        translation = self.get_nllb_translation(sentence)
        url = f"http://{self.postgrest_server}/nllb_translations"
        json = {
            "sentence": sentence,
            "translation": translation,
            "source_language": self.source_language,
            "target_language": self.target_language,
        }
        request = requests.post(url, json=json)
        if request.status_code == 201:
            return translation

        else:
            raise DefinitionTranslationError(f"Unknown error: {request.text}")

    def get_translation_in_cache(self, sentence: str):
        url = f"http://{self.postgrest_server}/nllb_translations?source_language=eq.{self.source_language}&target_language=eq.{self.target_language}&sentence=eq.{sentence}"
        request = requests.get(url)
        if request.status_code == 200 and request.json():
            return request.json()[0]["translation"]
        else:
            return None

    def get_nllb_translation(self, sentence: str):
        # fix weird behaviour where original text can be kept
        sentence = sentence.replace("’", "'")
        sentence = sentence.replace("]", "")
        sentence = sentence.replace("[", "")

        print(f"Translating sentence: {sentence}")
        url = (
            f"http://{self.translation_server}/translate/"
            f"{self.target_language}/{self.source_language}"
        )
        json = {"text": sentence}
        request = requests.get(url, params=json, timeout=3600)
        if request.status_code != 200:
            raise DefinitionTranslationError(f"Unknown error: {request.text}")
        translated = request.json()["translated"]
        if translated.startswith("(") and translated.endswith(")"):
            translated = translated[1:-1]
        translated = translated.replace(
            sentence, ""
        )  # fix weird behaviour where original text can be kept...
        print(f"TRANSLATED:::{translated}")
        return translated
