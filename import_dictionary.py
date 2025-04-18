#!/usr/bin/python3

import asyncio
import csv
import json
import sys
from subprocess import Popen

from aiohttp import ClientSession

from api.decorator import threaded
from api.dictionary.exceptions.http import WordAlreadyExists

# for parts of speech
MONOLINGUAL_DICTIONARY = f"user_data/{sys.argv[1]}.csv"
# for parts of speech
BILINGUAL_DICTIONARY = f"user_data/{sys.argv[1]}_malagasy.csv"
POS_DICT = {"1": "ana", "2": "mat", "3": "mpam-ana", "4": "mpampiankina", "5": "tamb"}
LANGUAGE = sys.argv[2]
DEFINITION_LANGUAGE = "mg"
URL_HEAD = "http://localhost:8001"
service_process = None


@threaded
def launch_service():
    print("launch_service()")
    global service_process
    service_process = Popen(["python3", "dictionary_service.py"])
    print("end launch_service()")


async def upload_dictionary():
    print("read_file()")
    session = ClientSession()
    bilingual = {}
    monolingual = {}
    print("reading monolingual dictionary")
    with open(MONOLINGUAL_DICTIONARY, "r") as fd:
        reader = csv.DictReader(fd)
        for row in reader:
            monolingual[row["word_id"]] = (POS_DICT[row["pos_id"]], row["anglisy"])

    print("reading bilingual dictionary")
    with open(BILINGUAL_DICTIONARY, "r") as fd:
        reader = csv.DictReader(fd)
        for row in reader:
            if row["word_id"] in bilingual:
                bilingual[row["word_id"]].append(row["malagasy"])
            else:
                bilingual[row["word_id"]] = [row["malagasy"]]

    print("uploading dictionary")
    i = 0
    for word_id, malagasy_defs in bilingual.items():
        i += 1
        if not i % 250:
            await session.post(f"{URL_HEAD}/commit")
            print("--------------------------")
        for malagasy in malagasy_defs:
            malagasy = malagasy.strip()
            definition = {
                "definition": malagasy,
                "definition_language": str(DEFINITION_LANGUAGE),
            }
            entry = {
                "language": LANGUAGE,
                "definitions": [definition],
                "word": monolingual[word_id][1].strip(),
                "part_of_speech": monolingual[word_id][0].strip(),
            }
            resp = await session.post(
                f"{URL_HEAD}/entry/{LANGUAGE}/create", json=json.dumps(entry)
            )
            print(entry)
            if resp.status == WordAlreadyExists.status_code:
                print("Word already exists... appending definition")
                url = f"{URL_HEAD}/entry/{LANGUAGE}/{monolingual[word_id][1]}"
                resp = await session.get(url)
                jtext = json.loads(await resp.text())
                for m in jtext:
                    if m["part_of_speech"] == monolingual[word_id][0]:
                        definition_already_exists = any(
                            (
                                existing_definition["definition"]
                                == definition["definition"]
                            )
                            for existing_definition in m["definitions"]
                        )
                        if not definition_already_exists:
                            print("definition does not yet exist. Creating...")
                            m.definitions.append(definition)
                            url = f"{URL_HEAD}/entry/{m.id}/edit"
                            await session.put(url, text=json.dumps(m))
                        else:
                            print("definition already exists. Skipping...")
                        break

        await session.post(f"{URL_HEAD}/commit")


def main():
    loop = asyncio.get_event_loop()
    launch_service()
    loop.run_until_complete(upload_dictionary())


if __name__ == "__main__":
    try:
        main()
    finally:
        if service_process is not None:
            service_process.kill()
