import sys
import time

import requests

with open(sys.argv[2], 'r') as file:
    for data in file:
        data = data.strip('\n')
        time.sleep(.2)
        print('>>>', data, '<<<')
        while True:
            try:
                requests.post("http://localhost:8000/wiktionary_page/" + sys.argv[1], json={"title": data})
                break
            except KeyboardInterrupt:
                print("Stopped.")
                break
            except requests.exceptions.ConnectionError:
                print("Error... retrying in 10s")
                time.sleep(10)
