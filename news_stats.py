# coding: utf8

import math
import pickle
import time

import pywikibot
import requests

from api.decorator import retry_on_fail
from list_wikis import Wikilister

udata = "/opt/botjagwar/user_data/milestones"
cdata = "/opt/botjagwar/conf/list_wikis/langs"

possible_errors = [requests.exceptions.ConnectionError]
requests.get = retry_on_fail(possible_errors, retries=5, time_between_retries=0.4)(
    requests.get
)


def get_saved_state():
    try:
        with open(f"{udata}/news_stats", "rb") as f:
            r = pickle.load(f)
        return r
    except (Exception, IOError) as e:
        print(e)
        return []


def get_new_state():
    lister = Wikilister()
    new_state = []
    for site in ["wikipedia", "wiktionary"]:
        for lang in lister.getLangs(site):
            urlstr = f"https://{lang}.{site}.org/"
            urlstr += "w/api.php?action=query&meta=siteinfo&format=json&siprop=statistics&continue"
            try:
                stat_page = requests.get(urlstr).json()
            except Exception as exc:
                print("Error while trying to get URL", exc)
                continue

            for _ in range(5):
                stat_json = ""
                try:
                    stat_json = stat_page
                    p = stat_json["query"]["statistics"]
                    wiki_state = (lang, site, p)
                    print(wiki_state)
                    new_state.append(wiki_state)
                    break
                except Exception as e:
                    print(stat_json)
                    time.sleep(5)
                    raise e
    return new_state


def save_state(state):
    with open(f"{udata}/news_stats", "wb") as f:
        pickle.dump(state, f)


def translate_json_keyword(json_keyword):
    words = {
        "articles": "pejim-botoatiny",
        "pages": "pejy rehetra",
        "users": "mpikambana",
        "edits": "fiovana",
    }
    try:
        return words[json_keyword]
    except KeyError:
        print(f"Unknown keyword: {json_keyword}")
        return False


def get_milestones(old_state, new_state):
    def states_diff(state_1, state_2):
        if (state_1[0], state_1[1]) != (state_2[0], state_2[1]):
            return
        for column in list(state_2[2].keys()):
            old_figure = state_1[2].get(column, 0)
            new_figure = state_2[2].get(column, 0)
            # print(old_figure, new_figure)

            s1_pow10 = int(math.log(max(1, old_figure), 10))
            s2_pow10 = int(math.log(max(1, new_figure), 10))

            new_figure = max(new_figure, 0)
            s1_1st_digit = int(str(new_figure)[0])
            s2_1st_digit = int(str(new_figure)[0])

            ms_type = ""

            if s1_pow10 != s2_pow10:
                if s1_pow10 <= s2_pow10:  # milestone 1
                    ms_type = "over"
                elif s1_pow10 > s2_pow10:  # milestone 2
                    ms_type = "below"
            else:
                if s1_1st_digit > s2_1st_digit:  # milestone 3
                    ms_type = "below"
                elif s1_1st_digit < s2_1st_digit:  # milestone 4
                    ms_type = "over"

            if ms_type != "":
                yield state_1[0], state_1[
                    1
                ], ms_type, s2_1st_digit * 10**s2_pow10, column

    for s2 in new_state:
        if not old_state:
            s1 = (
                s2[0],
                s2[1],
                {
                    "articles": 0,
                    "jobs": 0,
                    "users": 0,
                    "admins": 0,
                    "edits": 0,
                    "activeusers": 0,
                    "images": 0,
                    "queued-massmessages": 0,
                    "pages": 0,
                },
            )
            yield from states_diff(s1, s2)
        else:
            for s1 in old_state:
                yield from states_diff(s1, s2)


def site_to_wiki(site):
    sites = {
        "wiktionary": "wikt",
        "wikipedia": "w",
        "wikibooks": "b",
        "wikisource": "s",
        "wikiquote": "q",
    }
    try:
        return sites[site]
    except KeyError:
        return site


def render_announce(milestone):
    if milestone is None:
        return ""
    link = f":{site_to_wiki(milestone[1])}:{milestone[0]}:"
    item_type = translate_json_keyword(milestone[-1])

    if not item_type:
        raise ValueError("Can't render that announcement.")

    if milestone[2] == "over":
        return (
            "* Ny isan'ny %s ao amin'i [[%s|%s.%s]] dia mihoatra ny {{formatnum:%s}}."
            % (item_type, link, milestone[0], milestone[1], milestone[3])
        )
    elif milestone[2] == "below":
        return (
            "* Ny isan'ny %s ao amin'i [[%s|%s.%s]] dia tafidina ho latsaka ny {{formatnum:%s}}."
            % (item_type, link, milestone[0], milestone[1], milestone[3])
        )


def main():
    months = [
        "",
        "Janoary",
        "Febroary",
        "Martsa",
        "Aprily",
        "Mey",
        "Jiona",
        "Jolay",
        "Aogositra",
        "Septambra",
        "Oktobra",
        "Novambra",
        "Desambra",
    ]
    old = get_saved_state()
    new = get_new_state()
    ms = get_milestones(old, new)
    retstr = ""
    for m in ms:
        try:
            if c := render_announce(m):
                retstr += render_announce(m) + "\n"
        except ValueError as e:
            print(e)

    ct_time = time.localtime()
    if not retstr:
        print("tsy misy vaovao ho ampitaina.")
        return

    ct_date = "%d %s %d" % (ct_time[2], months[ct_time[1]], ct_time[0])
    page = pywikibot.Page(
        pywikibot.Site("mg", "wikipedia"), "Wikipedia:Vaovao Wikimedia/%d" % ct_time[0]
    )
    news = "\n; %s\n%s" % (ct_date, retstr)
    with open(f"/tmp/{ct_date}", "w") as newsfile:
        if len(old) != 0:
            if page.exists():
                content = page.get()
                if content.find(ct_date) != -1:
                    print("efa nahitana daty ankehitriny")
                    return
                content = news + content
                page.put(content, f"+Vaovao androany {ct_date}")
            else:
                page.put(news, f"Vaovao androany {ct_date}")

        newsfile.write(news)
        save_state(new)


if __name__ == "__main__":
    main()
