import json
import time

import requests

URL_HEAD = 'http://0.0.0.0:8001'

def create_entry(word, language, pos, definition, def_language):
    resp = requests.post(
        URL_HEAD + '/entry/%s/create' % language,
        json=json.dumps({
            'definitions': [{
                'definition': definition,
                'definition_language': def_language
            }],
            'word': word,
            'part_of_speech': pos,
        })
    )
    assert resp.status_code == 200, resp.status_code


if __name__ == '__main__':
    for i in range(1500):
        time.sleep(.05)
        create_entry('anoki%d' % i, 'kz', 'ana', 'fanandramana %d' % i, 'mg')