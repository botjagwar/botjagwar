# -*- coding: utf-8  -*-
import json
import re
import time

import pywikibot
import random
import requests
from itertools import cycle


data_file = "/opt/botjagwar/conf/list_wikis/"
try:
    current_user = f'{pywikibot.config.usernames["wiktionary"]["mg"]}'
except KeyError:
    current_user = "test"


class Wikilister(object):
    def __init__(self, test=False):
        self.test = test

        # self.user_agent_list = [
        #     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
        #     "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:139.0) Gecko/20100101 Firefox/139.0",
        #     "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1",
        #     # ...,
        # ]
        self.user_agent_list = [
            "Bot-Jagwar/1.7 (Linux; x64) python-requests/2.32.3",
        ]


    def getLangs(self, site):
        dump = open(f"{data_file}listof{site}.txt", "r").read()
        print(f"{data_file}listof{site}.txt")

        wikiregex = re.findall(
            "([a-z|\\-]+).%s.org/wiki/Special:Recentchanges" % site, dump
        )
        if len(wikiregex) == 0:
            wikiregex = re.findall("\\{\\{fullurl:([a-z|\\-]+):Special", dump)
        print(wikiregex)
        yield from wikiregex

    def run(self, wiki, site):
        datas = []
        i = 0
        for lang in self.getLangs(site):
            # generate a single random User Agent from the pool
            random_user_agent = cycle(self.user_agent_list)
            user_agent = next(random_user_agent)

            # use the randomized User Agent
            headers = {"User-Agent": user_agent}

            # Getting and formatting statistics JSON
            urlstr = f"https://{lang}.{site}.org/w/api.php?action=query&meta=siteinfo&format=json&siprop=statistics&continue"
            resp = requests.get(urlstr, headers=headers)
            while True:
                if resp.status_code != 200:
                    print(
                        f"Hadisoana tamin'ny fangatahana ny statistika {lang} {site} : {resp.status_code}"
                    )
                    time.sleep(10)
                    continue
                try:
                    stats = resp.json()
                    break
                except json.decoder.JSONDecodeError:
                    print(
                        f"Hadisoana tamin'ny famakiana ny statistika {lang} {site} : {resp.text}"
                    )
                    time.sleep(10)
                    continue

            m = stats["query"]["statistics"]
            e = [
                int(m["articles"]),
                int(m["pages"]),
                int(m["edits"]),
                int(m["users"]),
                int(m["activeusers"]),
                int(m["admins"]),
                int(m["images"]),
                lang,
                site,
            ]
            articles, pages, edits, users, activeusers, admins, images, lang, site = e

            # words per page calculation
            if float(m["articles"]) != 0:
                words_p_article = float(m["cirrussearch-article-words"]) / float(
                    m["articles"]
                )
            else:
                words_p_article = 0

            e.append(words_p_article)

            # Depth calculation
            try:
                depth = (edits / pages) * ((float(pages) - articles) / articles) ** 2.0
                depth = "-" if depth > 300 and articles < 100000 else "%.2f" % depth
            except ZeroDivisionError:
                depth = "-"
            e.append(depth)
            datas.append(e)

            i += 1
            print(
                (
                    "%s >"
                    " lahatsoratra:%d;"
                    " pejy:%d;"
                    " fanovana:%d;"
                    " mpikambana:%d;"
                    " mavitrika:%d;"
                    " mpandrindra:%d;"
                    " sary:%d;"
                    " teny:%2.2f;"
                    " halalina:%s "
                    % (
                        lang,
                        articles,
                        pages,
                        edits,
                        users,
                        activeusers,
                        admins,
                        images,
                        words_p_article,
                        depth,
                    )
                )
            )

        # Sort
        datas.sort(reverse=True)
        self.wikitext(datas, wiki)

    def wikitext(self, e, wiki):
        total = {
            "pages": 0,
            "allpages": 0,
            "edits": 0,
            "admins": 0,
            "activeusers": 0,
            "users": 0,
            "files": 0,
        }
        content = """
<small><center>Lisitra nohavaozina ny {{subst:CURRENTDAY}} {{subst:CURRENTMONTHNAME}} {{subst:CURRENTYEAR}}, tamin'ny {{subst:#time: H:i}} UTC</center></small>
{|class="wikitable sortable" border="1" cellpadding="2" cellspacing="0" style="width:100%; background: #f9f9f9; border: 1px solid #aaaaaa; border-collapse: collapse; white-space: nowrap; text-align: center"
|-
! N°
! Fiteny
! Kaody
! Pejy
! Pejy rehetra
! Fanovàna
! Mpandrindra
! Mpikambana
! <small>Mpikambana<br>mavitrika</small>
! Sary
! Isan-jato
! Teny/pejy
! Halalim-pejy"""
        # total = (0,0,0,0,0,0)
        for wikistats_data in e:
            print(wikistats_data)
            (
                articles,
                pages,
                edits,
                users,
                activeusers,
                admins,
                images,
                lang,
                site,
                words_per_page,
                depth,
            ) = wikistats_data
            total["pages"] += articles
            total["allpages"] += pages
            total["edits"] += edits
            total["admins"] += admins
            total["users"] += users
            total["activeusers"] += activeusers
            total["files"] += images

        for i, wikistats_data in enumerate(e, start=1):
            (
                articles,
                pages,
                edits,
                users,
                activeusers,
                admins,
                images,
                lang,
                site,
                words_per_page,
                depth,
            ) = wikistats_data
            wikistats_data = {
                "articles": articles,
                "pages": pages,
                "edits": edits,
                "users": users,
                "activeusers": activeusers,
                "admins": admins,
                "images": images,
                "language": lang,
                "wiki": site,
                "words_per_page": "{{formatnum:%2.2f}}" % words_per_page,
                "depth": depth,
            }
            isanjato = float(float(100 * articles) / total["pages"])
            content += (
                """
|- style="text-align: right;"
| """
                + str(i)
                + """
| [[:w:Fiteny {{%(language)s}}|{{%(language)s}}]]
| [//%(language)s.%(wiki)s.org/wiki/ %(language)s]
| [//%(language)s.%(wiki)s.org/w/api.php?action=query&meta=siteinfo&format=xml&siprop=statistics '''{{formatnum:%(articles)d}}''']
| {{formatnum:%(pages)d}}
| [//%(language)s.%(wiki)s.org/wiki/Special:Recentchanges {{formatnum:%(edits)d}} ]
| [//%(language)s.%(wiki)s.org/wiki/Special:Listadmins {{formatnum:%(admins)d}}]
| [//%(language)s.%(wiki)s.org/wiki/Special:Listusers {{formatnum:%(users)d}}]
| [//%(language)s.%(wiki)s.org/wiki/Special:ActiveUsers {{formatnum:%(activeusers)d}}]
| [//%(language)s.%(wiki)s.org/wiki/Special:Imagelist {{formatnum:%(images)d}}]
| {{formatnum:"""
                % wikistats_data
                + """%2.2f""" % isanjato
                + """}}
| %(words_per_page)s
| %(depth)s
"""
                % wikistats_data
            )
        content += "\n\n|}\n\n"
        content += """
{|class="wikitable sortable" border="1" cellpadding="2" cellspacing="0" style="width:100%; background: #f9f9f9; border: 1px solid #aaaaaa; border-collapse: collapse; white-space: nowrap; text-align: center"""
        content += (
            """
|-
!
! Pejim-botoatiny
! Pejy rehetra
! Fanovàna
! Mpandrindra
! Mpikambana
! Mpikambana mavitrika
! Rakitra
|-
! Isa manontolo
| '''{{formatnum:%(pages)d}}'''
| '''{{formatnum:%(allpages)d}}'''
| '''{{formatnum:%(edits)d}}'''
| '''{{formatnum:%(admins)d}}'''
| '''{{formatnum:%(users)d}}'''
| '''{{formatnum:%(activeusers)d}}'''
| '''{{formatnum:%(files)d}}'''
"""
            % total
        )
        content += """
|}"""

        while not self.test:
            try:
                page = pywikibot.Page(
                    pywikibot.Site("mg", "wiktionary"),
                    f"Mpikambana:{current_user}/Lisitry ny {wiki}/tabilao",
                )
                page.put(content, "Rôbô : fanavaozana ny statistika")
                break
            except Exception:
                print("Hadisoana nitranga tampametrahana ilay pejy")


def main():
    timeshift = 3
    bot = Wikilister()

    while True:
        t = list(time.gmtime())
        cond = (not (t[3] + timeshift) % 6) and (t[4] == 0)
        if cond:
            bot.run("Wikibolana", "wiktionary")
            bot.run("pywikibot", "pywikibot")
            time.sleep(120)
        else:
            print("Fanavaozana isaky ny adin'ny 6")
            print(
                (
                    "Miandry ny fotoana tokony hamaozana ny pejy (ora %2d:%2d) (GMT+%d)"
                    % ((t[3] + timeshift), t[4], (timeshift))
                )
            )
            time.sleep(30)


if __name__ == "__main__":
    wikilisting = Wikilister()
    wikilisting.run("Wikibolana", "wiktionary")
    wikilisting.run("Wikipedia", "wikipedia")
    wikilisting.run("Wikiboky", "wikibooks")
    pywikibot.stopme()
