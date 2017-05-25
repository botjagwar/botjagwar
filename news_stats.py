# coding: utf8

import math, json, time, urllib, pickle

from urllib import FancyURLopener
from list_wikis import Wikilister

import pywikibot

class MyOpener(FancyURLopener):
    version = 'Botjagwar/v1.1'

udata = u"user_data/milestones"
cdata = u"conf/list_wikis/langs"

def get_saved_state(name):
    try:
        return pickle.load(file(udata + u"/%s" % name, 'r'))
    except IOError as e:
        return []


def get_new_state():
    lister = Wikilister()
    new_state = []
    for site in ['wikipedia', 'wiktionary']:
        for lang in lister.getLangs(site):
            urlstr = 'https://%s.%s.org/' % (lang, site)
            print urlstr
            urlstr += 'w/api.php?action=query&meta=siteinfo&format=json&siprop=statistics&continue'
            stat_page = urllib.urlopen(urlstr).read()
            for i in range(5):
                stat_json = None
                try:
                    stat_json = json.loads(stat_page)
                    wiki_state = (lang, site, stat_json['query']['statistics']['articles'])
                    new_state.append(wiki_state)
                    break
                except Exception as e:
                    print stat_json
                    raise e
                    time.sleep(5)
    return new_state


def save_state(state, state_name):
    pickle.dump(state, file(udata + u"/%s" % state_name, 'w'))


def translate_json_keyword(json_keyword):
    words = {
        "articles": 'lahatsoratra',
        "page": 'pejy rehetra',
        'users': 'mpikambana'
    }
    try:
        return words[json_keyword]
    except KeyError:
        return json_keyword


def get_milestones(old_state, new_state):
    def states_diff(s1, s2):
        if (s1[0], s1[1]) == (s2[0], s2[1]):
            s1_pow10 = int(math.log(max(1, s1[2]), 10))
            s2_pow10 = int(math.log(max(1, s2[2]), 10))
            s1_1st_digit = int(str(s1[2])[0])
            s2_1st_digit = int(str(s2[2])[0])
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
                return s1[0], s1[1], ms_type, s2_1st_digit * 10 ** s2_pow10

    for s2 in new_state:
        if not old_state:
            s1 = (s2[0], s2[1], 0)
            yield states_diff(s1, s2)
        else:
            for s1 in old_state:
                yield states_diff(s1, s2)


def render_announce(milestone):
    if milestone is None:
        return u""
    if milestone[2] == "over":
        return u"* Ny isan'ny lahatsorata ao amin'i %s.%s dia mihoatra ny %s." % (
            milestone[0], milestone[1], milestone[3])
    elif milestone[2] == "below":
        return u"* Ny isan'ny lahatsorata ao amin'i %s.%s dia tafidina ho latsaka ny %s." % (
            milestone[0], milestone[1], milestone[3])


def test():
    old = []

    new = [('mg', 'wiktionary', 200),
           ('ku', 'wiktionary', 481),
           ('es', 'wiktionary', 10)]

    ms = get_milestones(old, new)
    for m in ms:
        print m


def main():
    months = [u"", u"Janoary", u"Febroary", u"Martsa", u"Aprily", u"Mey", u"Jiona",
              u"Jolay", u"Aogositra", u"Septambra", u"Oktobra", u"Novambra", u"Desambra"]
    old = get_saved_state(u"ct_state")
    new = get_new_state()
    ms = get_milestones(old, new)
    retstr = u""
    for m in ms:
        c = render_announce(m)
        if c:
            retstr += render_announce(m) + u"\n"

    ct_time = time.localtime()
    if not retstr:
        #save_state(u"ct_state", new)
        return

    ct_date = u"%d %s %d" % (ct_time[2], months[ct_time[1]], ct_time[0])
    page = pywikibot.Page(pywikibot.Site("mg", "wiktionary"), u"Wikipedia:Vaovao Wikimedia/%d" % ct_time[0])
    news = u"\n; %s\n%s" % (ct_date, retstr)
    if page.exists():
        content = page.get()
        if content.find(ct_date) != -1:
            #save_state(u"ct_state", new)
            return
        content = news + content
        page.put(content, u"+Vaovao androany" + ct_date)
    else:
        page.put(news, u"Vaovao androany" + ct_date)

    #save_state(new, u"ct_state")

if __name__ == '__main__':
    #test()
    print main()
