import time

import requests


def merge_entries():
    pass


def fix_part_of_speech():
    q = set()
    print("get words")
    with open("user_data/list_fr_Formes de verbes en français", "r") as f:
        for line in f:
            q.add(line.strip("\n"))

    print("get list in db")
    c = 0
    cd_every = 10
    print("getting page")
    rq1 = requests.get(
        "http://localhost:8100/word?part_of_speech=eq.e-mat&language=eq.fr"
    )
    rq2 = rq1.json()

    d = set()
    cc = 0
    while rq2:
        for word in rq2:
            if word["word"] not in q:
                c += 1
                d.add(word["word"])
                if c >= 100:
                    url = "http://localhost:8100/word?word=in.({})".format(",".join(d))
                    rq = requests.patch(url, {"part_of_speech": "mat"})
                    d = set()
                    c = 0

        print("getting page")
        rq1 = requests.get(
            "http://localhost:8100/word?part_of_speech=eq.e-mat&language=eq.fr"
        )
        cc += 1
        if cc >= cd_every:
            print("cooldown")
            time.sleep(20)
            cc = 0
        rq2 = rq1.json()
        if len(rq2) < 1:
            break
