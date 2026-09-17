# -*- coding: utf-8  -*-
import re
import time

import pywikibot
import requests
from typing import Dict, Iterable, List, Optional

data_file = "/opt/botjagwar/conf/list_wikis/"
WIKISTATS_DATA_URL = (
    "https://commons.wikimedia.org/w/index.php"
    "?title=Data:Wikipedia_statistics/data.tab&action=raw"
)
# Aggregate/non-language prefixes present in data.tab that are not wikis
NON_LANGUAGE_PREFIXES = {
    "total",
    "totalactive",
    "totalclosed",
    "www",
    "meta",
    "commons",
    "incubator",
    "foundation",
    "wikimania",
    "wikitech",
    "donate",
    "species",
    "beta",
}
try:
    current_user = f'{pywikibot.config.usernames["wiktionary"]["mg"]}'
except KeyError:
    current_user = "test"


class Wikilister(object):
    def __init__(self, test: bool = False) -> None:
        self.test = test
        self._wikistats_cache: Optional[Dict[str, Dict[str, int]]] = None

    def _fetch_wikistats_table(self) -> Dict[str, Dict[str, int]]:
        """Fetch all site statistics in one request from Commons data.tab.

        Returns a dict keyed by site name (e.g. "mg.wiktionary") whose values
        follow the pywikibot `statistics` dict layout ("files" is exposed as
        "images"). Returns an empty dict on failure so callers can fall back
        to the legacy per-wiki fetching.
        """
        if self._wikistats_cache is not None:
            return self._wikistats_cache

        table: Dict[str, Dict[str, int]] = {}
        try:
            response = requests.get(
                WIKISTATS_DATA_URL,
                timeout=60,
                # Wikimedia rejects requests with generic User-Agents
                headers={
                    "User-Agent": "Bot-Jagwar/1.7.2 "
                    "(https://github.com/botjagwar/botjagwar; radomd92@gmail.com)"
                },
            )
            response.raise_for_status()
            payload = response.json()
            field_names = [field["name"] for field in payload["schema"]["fields"]]
            for row in payload["data"]:
                stats = dict(zip(field_names, row))
                site_name = stats.pop("site")
                stats["images"] = stats.pop("files")
                table[site_name] = {key: int(value) for key, value in stats.items()}
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            print(f"Tsy azo ny angona avy amin'ny data.tab : {exc}")
            table = {}

        self._wikistats_cache = table
        return table

    def _fetch_statistics(self, lang: str, site: str) -> Dict[str, int]:
        """Fetch site statistics via pywikibot with retries to avoid HTTP 429 errors."""
        retries = 5
        backoff_seconds = 5
        last_exception: Optional[Exception] = None
        for attempt in range(1, retries + 1):
            try:
                wiki_site = pywikibot.Site(lang, site)
                wiki_site.throttle.wait(.1)
                stats = wiki_site.siteinfo.get("statistics")
                if not isinstance(stats, dict):
                    raise ValueError(
                        f"Invalid statistics payload for {lang}.{site}: {stats}"
                    )
                return stats
            except (
                pywikibot.exceptions.APIError,
                pywikibot.exceptions.ServerError,
                pywikibot.exceptions.TimeoutError,
                pywikibot.exceptions.Error,
                ValueError,
            ) as exc:
                last_exception = exc
                print(
                    "Hadisoana tamin'ny fangatahana ny statistika "
                    f"{lang} {site} : {exc}. Mamerina indray ({attempt}/{retries})."
                )
                time.sleep(backoff_seconds * attempt)
        raise RuntimeError(
            f"Tsy nahazo statistika ho an'ny {lang}.{site} rehefa naverina imbetsaka."
        ) from last_exception

    def get_wikistats(self, site: str) -> Dict[str, Dict[str, int]]:
        """Return data.tab statistics keyed by language for one wiki project."""
        wikistats = self._fetch_wikistats_table()
        return {
            prefix: stats
            for key, stats in wikistats.items()
            for prefix, separator, site_name in [key.partition(".")]
            if separator
            and site_name == site
            and prefix not in NON_LANGUAGE_PREFIXES
        }

    def getLangs(self, site: str) -> Iterable[str]:
        wikistats = self.get_wikistats(site)
        if wikistats:
            languages = list(wikistats)
            print(languages)
            yield from languages
            return

        # Legacy fallback: read the language list from a local dump file.
        dump = open(f"{data_file}listof{site}.txt", "r").read()
        print(f"{data_file}listof{site}.txt")

        wikiregex = re.findall(
            "([a-z|\\-]+).%s.org/wiki/Special:Recentchanges" % site, dump
        )
        if len(wikiregex) == 0:
            wikiregex = re.findall("\\{\\{fullurl:([a-z|\\-]+):Special", dump)
        print(wikiregex)
        yield from wikiregex

    def run(self, wiki: str, site: str) -> None:
        wikistats = self._fetch_wikistats_table()
        datas: List[List[object]] = []
        i = 0
        for lang in self.getLangs(site):
            m = wikistats.get(f"{lang}.{site}")
            if m is None:
                m = self._fetch_statistics(lang, site)
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
                        depth,
                    )
                )
            )

        # Sort
        datas.sort(reverse=True)
        self.wikitext(datas, wiki)

    def wikitext(self, e: List[List[object]], wiki: str) -> None:
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


def main() -> None:
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
