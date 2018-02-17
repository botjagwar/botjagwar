# coding: utf8

import os
import math
import json
import time
import urllib.request, urllib.parse, urllib.error
import pickle

from urllib.request import FancyURLopener
from list_wikis import Wikilister
import pywikibot


class MyOpener(FancyURLopener):
    version = 'Botjagwar/v1.1'


udata = os.getcwd() + "/user_data/milestones"
cdata = os.getcwd() + "/conf/list_wikis/langs"


def get_saved_state():

    try:
        f = open(udata + "/news_stats", 'r')
        r = pickle.load(f)
        f.close()
        return r
    except IOError as e:
        print(e)
        return []


def get_new_state():
    lister = Wikilister()
    new_state = []
    for site in ['wikipedia', 'wiktionary']:
        for lang in lister.getLangs(site):
            urlstr = 'https://%s.%s.org/' % (lang, site)
            urlstr += 'w/api.php?action=query&meta=siteinfo&format=json&siprop=statistics&continue'
            stat_page = urllib.request.urlopen(urlstr).read()
            for i in range(5):
                stat_json = ""
                try:
                    stat_json = json.loads(stat_page)
                    p = stat_json['query']['statistics']
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
    f = open(udata + "/news_stats", 'w')
    pickle.dump(state, f)
    f.close()


def translate_json_keyword(json_keyword):
    words = {
        "articles": 'pejim-botoatiny',
        "pages": 'pejy rehetra',
        'users': 'mpikambana',
        'edits': 'fiovana',
    }
    try:
        return words[json_keyword]
    except KeyError:
        print(("Unknown keyword: %s" % json_keyword))
        return False


def get_milestones(old_state, new_state):
    def states_diff(state_1, state_2):
        if (state_1[0], state_1[1]) == (state_2[0], state_2[1]):
            for column in list(state_2[2].keys()):
                old_figure = state_1[2][column]
                new_figure = state_2[2][column]
                # print(old_figure, new_figure)

                s1_pow10 = int(math.log(max(1, old_figure), 10))
                s2_pow10 = int(math.log(max(1, new_figure), 10))

                new_figure = max(new_figure, 0)
                s1_1st_digit = int(str(new_figure)[0])
                s2_1st_digit = int(str(new_figure)[0])

                ms_type = ""

                if s1_pow10 != s2_pow10:
                    if s1_pow10 <= s2_pow10:  # milestone 1
                        ms_type = 'over'
                    elif s1_pow10 > s2_pow10:  # milestone 2
                        ms_type = 'below'
                else:
                    if s1_1st_digit > s2_1st_digit:  # milestone 3
                        ms_type = 'below'
                    elif s1_1st_digit < s2_1st_digit:  # milestone 4
                        ms_type = 'over'

                if ms_type != '':
                    yield state_1[0], state_1[1], ms_type, s2_1st_digit * 10 ** s2_pow10, column

    for s2 in new_state:
        if not old_state:
            s1 = (s2[0], s2[1], {
                'articles': 0,
                'jobs': 0,
                'users': 0,
                'admins': 0,
                'edits': 0,
                'activeusers': 0,
                'images': 0,
                'queued-massmessages': 0,
                'pages': 0})
            for s_diff in states_diff(s1, s2):
                yield s_diff
        else:
            for s1 in old_state:
                for s_diff in states_diff(s1, s2):
                    yield s_diff


def site_to_wiki(site):
    sites = {
        'wiktionary': 'wikt',
        'wikipedia': 'w',
        'wikibooks': 'b',
        'wikisource': 's',
    }
    try:
        return sites[site]
    except KeyError:
        return site


def render_announce(milestone):
    if milestone is None:
        return ""
    link = ":%s:%s:" % (site_to_wiki(milestone[1]), milestone[0])
    item_type = translate_json_keyword(milestone[-1])

    if not item_type:
        raise ValueError("Can't render that announcement.")

    if milestone[2] == "over":
        return "* Ny isan'ny %s ao amin'i [[%s|%s.%s]] dia mihoatra ny {{formatnum:%s}}." % (
                item_type, link, milestone[0], milestone[1], milestone[3])
    elif milestone[2] == "below":
        return "* Ny isan'ny %s ao amin'i [[%s|%s.%s]] dia tafidina ho latsaka ny {{formatnum:%s}}." % (
            item_type, link, milestone[0], milestone[1], milestone[3])


def main():
    months = ["", "Janoary", "Febroary", "Martsa", "Aprily", "Mey", "Jiona",
              "Jolay", "Aogositra", "Septambra", "Oktobra", "Novambra", "Desambra"]
    old = get_saved_state()
    new = get_new_state()
    ms = get_milestones(old, new)
    retstr = ""
    for m in ms:
        try:
            c = render_announce(m)
            if c:
                retstr += render_announce(m) + "\n"
        except ValueError as e:
            print(e)

    ct_time = time.localtime()
    if not retstr:
        print ("tsy misy vaovao ho ampitaina.")
        return

    ct_date = "%d %s %d" % (ct_time[2], months[ct_time[1]], ct_time[0])
    page = pywikibot.Page(pywikibot.Site("mg", "wikipedia"), "Wikipedia:Vaovao Wikimedia/%d" % ct_time[0])
    news = "\n; %s\n%s" % (ct_date, retstr)
    newsfile = open("/tmp/%s" % ct_date, "w")
    if page.exists():
        content = page.get()
        if content.find(ct_date) != -1:
            print ("tsy nahitana daty ankehitriny")
            return
        content = news + content
        page.put(content, "+Vaovao androany" + ct_date)
        newsfile.write(content.encode('utf8'))
    else:
        page.put(news, "Vaovao androany" + ct_date)
        newsfile.write(news.encode('utf8'))

    save_state(new)
    newsfile.close()


if __name__ == '__main__':
    main()