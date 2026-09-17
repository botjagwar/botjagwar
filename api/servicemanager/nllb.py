import logging

import requests

from api.config import BotjagwarConfig
from api.http_client import DEFAULT_HTTP_TIMEOUT, NLLB_HTTP_TIMEOUT

log = logging.getLogger(__name__)

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

    @staticmethod
    def _normalise(text: str) -> str:
        """Normalise a sentence for verbatim-copy comparison."""
        return " ".join(text.lower().replace("’", "'").split()).strip(" .,;:()")

    def get_translation(
        self,
        sentence: str,
        roundtrip_validation_enabled: bool | None = None,
    ) -> str | None:
        if translation := self.get_translation_in_cache(sentence):
            if self._normalise(translation) != self._normalise(sentence):
                return translation
            log.warning(
                "Ignoring cached NLLB translation that copies the source: %r",
                translation,
            )

        translation = self.get_nllb_translation(
            sentence,
            roundtrip_validation_enabled=roundtrip_validation_enabled,
        )
        if (
            translation
            and self._normalise(translation) != self._normalise(sentence)
            and roundtrip_validation_enabled is not False
        ):
            url = f"http://{self.postgrest_server}/nllb_translations"
            json = {
                "sentence": sentence,
                "translation": translation,
                "source_language": self.source_language,
                "target_language": self.target_language,
            }

            try:
                requests.post(url, json=json, timeout=DEFAULT_HTTP_TIMEOUT)
            except requests.RequestException as exc:
                log.warning("Unable to store NLLB translation in cache: %s", exc)

        return translation


    def get_translation_in_cache(self, sentence: str):
        url = f"http://{self.postgrest_server}/nllb_translations?source_language=eq.{self.source_language}&target_language=eq.{self.target_language}&sentence=eq.{sentence}"
        try:
            request = requests.get(url, timeout=DEFAULT_HTTP_TIMEOUT)
            cached_translations = request.json() if request.status_code == 200 else []
        except (requests.RequestException, ValueError) as exc:
            log.warning("Unable to read NLLB translation cache: %s", exc)
            return None
        return cached_translations[0]["translation"] if cached_translations else None

    def get_nllb_translation(
        self,
        sentence: str,
        roundtrip_validation_enabled: bool | None = None,
    ) -> str | None:
        # fix weird behaviour where original text can be kept
        sentence = sentence.replace("’", "'")
        sentence = sentence.replace("]", "")
        sentence = sentence.replace("[", "")

        print(f"Translating sentence: {sentence}")
        # Translation servers expose /translate/<source>/<target>: the source
        # language must come first or the request direction is reversed.
        url = (
            f"http://{self.translation_server}/translate/"
            f"{self.source_language}/{self.target_language}"
        )
        params = {"text": sentence}
        if roundtrip_validation_enabled is not None:
            if not isinstance(roundtrip_validation_enabled, bool):
                raise TypeError("roundtrip_validation_enabled must be a boolean")
            params["roundtrip_validation"] = str(
                roundtrip_validation_enabled
            ).lower()
        request = requests.get(url, params=params, timeout=NLLB_HTTP_TIMEOUT)
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
