import requests

from api.config import BotjagwarConfig
from api.decorator import run_once
from conf.entryprocessor.languagecodes.en import LANGUAGE_CODES, LANGUAGE_NAMES
from ..servicemanager.pgrest import StaticBackend

backend = StaticBackend()
config = BotjagwarConfig()


class AdditionalDataImporterError(Exception):
    pass


class AdditionalDataImporter(object):
    def __init__(self, **parameters):
        self._languages = None
        self.iso_codes = None
        self.fetch_default_languages_mapper()
        self.word_id_cache = {}
        # self.fetch_word_ids()

        self.dry_run = parameters.get("dry_run", False)
        if "data" in parameters:
            self.data_type = parameters["data"]

        self.counter = 0
        self.batch = []

    def offline_fetch_default_languages_mapper(self):
        self._languages = LANGUAGE_NAMES
        self.iso_codes = LANGUAGE_CODES

    @run_once
    def online_fetch_default_languages_mapper(self):
        self._languages = {
            l["english_name"]: l["iso_code"]
            for l in requests.get(f"{backend.backend}/language").json()
        }
        self.iso_codes = {v: k for k, v in self.languages.items()}

    fetch_default_languages_mapper = offline_fetch_default_languages_mapper

    @property
    def languages(self):
        return self._languages

    def set_languages(self, languages):
        self._languages = languages
        self.iso_codes = {v: k for k, v in self.languages.items()}

    def additional_word_information_already_exists(self, word_id, information):
        assert word_id is not None
        assert information is not None
        assert bool(information)
        data = {
            "type": f"eq.{self.data_type}",
            "word_id": f"eq.{str(word_id)}",
            "information": f"eq.{information}",
        }
        response = requests.get(
            f"{backend.backend}/additional_word_information", params=data
        )
        if resp_data := response.json():
            if not isinstance(resp_data, list):
                return False

            if (
                "word_id" in resp_data[0]
                and "information" in resp_data[0]
                and "type" in resp_data[0]
            ):
                return True
        return False

    def get_data(self, template_title: str, wikipage: str, language: str) -> list:
        raise NotImplementedError()

    def is_data_type_already_defined(self, additional_data):
        return any(d["data_type"] == self.data_type for d in additional_data)

    def process_non_wikipage(self, title: str, content: str, language: str):
        if hasattr(self, "counter"):
            self.counter += 1
        else:
            self.counter = 0

        # print(f'>>> {title} [#{self.counter}] <<<')
        if (title, language) not in self.word_id_cache:
            rq_params = {"word": f"eq.{title}", "language": f"eq.{language}"}
            response = requests.get(f"{backend.backend}/word", rq_params)
            if query := response.json():
                self.word_id_cache[(title, language)] = query[0]["id"]

            else:
                return

        additional_data_filenames = self.get_data(self.data_type, content, language)

        assert isinstance(additional_data_filenames, list)
        # print(additional_data_filenames)
        for additional_data in additional_data_filenames:
            if (title, language) not in self.word_id_cache:
                raise AdditionalDataImporterError("the word is unknown (no id)")

            self.write_additional_data(
                self.word_id_cache[(title, language)], additional_data
            )

    def write_additional_data(self, word_id, additional_data):
        if not additional_data.strip():
            return

        print(additional_data)

        data = {
            "type": self.data_type,
            "word_id": word_id,
            "information": additional_data,
        }
        print(data)
        if self.additional_word_information_already_exists(
            data["word_id"], additional_data
        ):
            print("additional data already exists. Skipping...")
            return

        if not self.dry_run:
            response = requests.post(
                f"{backend.backend}/additional_word_information", data=data
            )
            if response.status_code != 201:
                print(response.status_code)
                print(response.text)
