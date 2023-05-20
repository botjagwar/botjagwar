import sys

import requests

with open(sys.argv[2], 'r') as file:
    for data in file:
        data = data.strip('\n')
        print('>>>', data, '<<<')
        requests.post("http://localhost:8000/wiktionary_page/" + sys.argv[1], json={"title": data})
