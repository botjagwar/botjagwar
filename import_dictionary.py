import sys
import asyncio
from aiohttp import ClientSession
import csv
import json
from modules.decorator import threaded
from subprocess import Popen
from database.http import WordAlreadyExistsException


MONOLINGUAL_DICTIONARY = 'user_data/%s.csv' % sys.argv[1]  # for parts of speech
BILINGUAL_DICTIONARY = 'user_data/%s_malagasy.csv' % sys.argv[1]  # for parts of speech
POS_DICT = {
    '1': 'ana',
    '2': 'mat',
    '3': 'mpam-ana',
    '4': 'mpampiankina',
    '5': 'tamb'
}
LANGUAGE = sys.argv[2]
DEFINITION_LANGUAGE = 'mg'
URL_HEAD = 'http://localhost:8001'
service_process = None


@threaded
def launch_service():
    print('launch_service()')
    global service_process
    service_process = Popen(["python3.6", "dictionary_service.py"])
    print('end launch_service()')


async def upload_dictionary():
    print('read_file()')
    session = ClientSession()
    bilingual = {}
    monolingual = {}
    print('reading bilingual dictionary')
    with open(MONOLINGUAL_DICTIONARY, 'r') as fd:
        reader = csv.DictReader(fd)
        for row in reader:
            monolingual[row['word_id']] = (POS_DICT[row['pos_id']], row['anglisy'])

    print('reading monolingual dictionary')
    with open(BILINGUAL_DICTIONARY, 'r') as fd:
        reader = csv.DictReader(fd)
        for row in reader:
            bilingual[row['word_id']] = row['malagasy']

    print('uploading dictionary')
    i = 0
    for word_id, malagasy in bilingual.items():
        i += 1
        if not i % 250:
            await session.post(URL_HEAD + '/commit')
            print('--------------------------')
        malagasy = malagasy.strip()
        definition = {
            'definition': malagasy,
            'definition_language': str(DEFINITION_LANGUAGE)
        }
        entry = {
            'language': LANGUAGE,
            'definitions': [definition],
            'word': monolingual[word_id][1].strip(),
            'part_of_speech': monolingual[word_id][0].strip(),
        }
        resp = await session.post(
            URL_HEAD + '/entry/%s/create' % LANGUAGE,
            json=json.dumps(entry)
        )
        print(entry)
        if resp.status == WordAlreadyExistsException.status_code:
            print('Word already exists... appending definition')
            url = URL_HEAD + '/entry/%s/%s' % (LANGUAGE, monolingual[word_id][1])
            resp = await session.get(url)
            jtext = json.loads(await resp.text())
            for m in jtext:
                if m['part_of_speech'] == monolingual[word_id][0]:
                    definition_already_exists = False
                    for existing_definition in m['definitions']:
                        if existing_definition['definition'] == definition['definition']:
                            definition_already_exists = True
                    if not definition_already_exists:
                        print('definition does not yet exist. Creating...')
                        m.definitions.append(definition)
                        url = URL_HEAD + '/entry/%s/edit' % m.id
                        await session.post(url, text=json.dumps(m))
                    else:
                        print('definition already exists. Skipping...')
                    break

    await session.get(URL_HEAD + '/commit')


def main():
    loop = asyncio.get_event_loop()
    launch_service()
    loop.run_until_complete(upload_dictionary())


if __name__ == '__main__':
    try:
        main()
    finally:
        if service_process is not None:
            service_process.kill()