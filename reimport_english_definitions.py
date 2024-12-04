import time
from random import randint

import requests

from api.decorator import threaded
from api.entryprocessor.wiki.en import ENWiktionaryProcessor
from redis_wikicache import RedisSite

processor = ENWiktionaryProcessor()


class AlreadyExistsError(Exception):
    pass


class PgrestServer:
    """ """

    def __init__(self):
        self._words = {}
        self.fetch_all_words()

    @property
    def server(self):
        port = randint(8100, 8116)
        return f"http://localhost:{port}"

    def fetch_all_words(self):
        print(
            "Fetching word ids by part of speech and language from the database server"
        )
        for i in range(200):
            offset = 100000 * i
            print(f"Fetching from position {offset}...")
            dict_get_data = {
                "limit": 100000,
                "offset": offset,
            }

            resp = requests.get(f"{self.server}/word", params=dict_get_data)
            datas = resp.json()
            if not datas or 400 <= resp.status_code < 600:
                break

            for data in datas:
                if (
                    data["word"],
                    data["language"],
                    data["part_of_speech"],
                ) not in self._words:
                    self._words[
                        (data["word"], data["language"], data["part_of_speech"])
                    ] = data["id"]
        print(f"Fetching is done. {len(self._words)} words have been fetched")

    def fetch_word(self, word, language, part_of_speech, tries=0):
        if tries > 3:
            return {}

        part_of_speech = part_of_speech[:15]
        return (
            {
                "id": self._words[(word, language, part_of_speech)],
                "word": word,
                "language": language,
                "part_of_speech": part_of_speech,
            }
            if (word, language, part_of_speech) in self._words
            else self.fetch_and_create_if_not_exists(
                word, language, part_of_speech, 0
            )
        )

    def fetch_and_create_if_not_exists(self, word, language, part_of_speech, tries=0):
        dict_get_data = {
            "word": f"eq.{word}",
            "language": f"eq.{language}",
            "part_of_speech": f"eq.{part_of_speech}",
        }

        resp = requests.get(f"{self.server}/word", params=dict_get_data)
        data = resp.json()
        if not (400 <= resp.status_code < 600):
            if data:
                return data[0]
            dict_post_data = {
                "word": f"{word}",
                "language": f"{language}",
                "part_of_speech": f"{part_of_speech}",
            }
            response = requests.post(f"{self.server}/word", json=dict_post_data)
            if tries > 2:
                print(
                    f"tried {tries} times to create ({word}, {language}, {part_of_speech})"
                )

            try:
                return self.fetch_and_create_if_not_exists(
                    word, language, part_of_speech, tries + 1
                )
            except RecursionError:
                print(response.text)
                return {}


pg_rest = PgrestServer()


def create_definition_if_not_exists(definition, language):
    def fetch_definition(definition, language):
        # Fetch definition
        dict_get_data = {
            "definition": f"eq.{definition}",
            "definition_language": f"eq.{language}",
        }

        resp = requests.get(f"{pg_rest.server}/definitions", params=dict_get_data)
        returned_data = resp.json()
        return returned_data

    returned_data = fetch_definition(definition, language)
    # Add definition if not found
    if not returned_data:
        defn_post_data = {"definition": definition, "definition_language": language}
        resp = requests.post(f"{pg_rest.server}/definitions", json=defn_post_data)
        if resp.status_code == 409:
            raise AlreadyExistsError(f"Already exists! {resp.text}")

        return fetch_definition(definition, language)
    else:
        return returned_data


def reimport_english_definitions(page_nb=1):
    # definition_translation = NllbDefinitionTranslation()
    site = RedisSite("en", "wiktionary")
    ct_time = time.time()
    ct_time2 = time.time()

    # Count from which resume the processing. This is to speed up if the script crashed mid-way
    page_count = 0
    last_count = 0

    # Counters to allow for the action above
    page_no = 0
    counter = 0
    for page in site.all_pages():
        page_no += 1
        if not page_no % 500:
            dtime = abs(ct_time2 - time.time())
            ct_time2 = time.time()
            print(f"{page_no} pages processed (throughput: {500 / dtime} pages/second)")
        if page_no < page_count:
            continue

        content = page.get()
        title = page.title()
        processor.title = title
        processor.content = content
        entries = list(processor.get_all_entries())
        for entry in entries:
            word = pg_rest.fetch_word(entry.entry, entry.language, entry.part_of_speech)
            if not word:
                # print(f"{entry.entry} ({entry.part_of_speech}, {entry.language})"
                #       f" No yet referenced in dictionary! Import skipped...")
                continue

            for definition in entry.definitions:
                counter += 1
                if not counter % 500:
                    dtime = abs(ct_time - time.time())
                    ct_time = time.time()
                    print(
                        f"{counter} imported (throughput: {500 / dtime} entries/second)"
                    )

                # Skip to speed up error recovery
                if counter < last_count:
                    continue

                try:
                    _reimport_english_definition(word, definition)
                except requests.exceptions.ConnectionError:
                    continue


@threaded
def _reimport_english_definition(word, definition):
    definition_data = create_definition_if_not_exists(definition, "en")
    if not definition_data:
        return

    if "id" not in definition_data:
        return
    try:
        definition_data = definition_data[0]
    except KeyError:
        pass
    dict_post_data = {
        "definition": f'{definition_data["id"]}',
        "word": f'{word["id"]}',
    }

    resp = requests.post(f"{pg_rest.server}/dictionary", json=dict_post_data)


if __name__ == "__main__":
    reimport_english_definitions()
