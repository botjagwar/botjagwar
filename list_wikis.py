# -*- coding: utf-8  -*-
import json
import re
import time

import pywikibot
import requests

data_file = '/opt/botjagwar/conf/list_wikis/'
try:
    current_user = "%s" % pywikibot.config.usernames['wiktionary']['mg']
except KeyError:
    current_user = "test"


class Wikilister(object):
    def __init__(self, test=False):
        self.test = test

    def getLangs(self, site):
        dump = open(data_file + 'listof%s.txt' % site, 'r').read()
        print((data_file + 'listof%s.txt' % site))

        wikiregex = re.findall(
            '([a-z|\\-]+).%s.org/wiki/Special:Recentchanges' %
            site, dump)
        if len(wikiregex) == 0:
            wikiregex = re.findall('\\{\\{fullurl:([a-z|\\-]+):Special', dump)
        print(wikiregex)
        for lang in wikiregex:
            yield lang

    def run(self, wiki, site):
        datas = []
        i = 0
        for lang in self.getLangs(site):
            # Getting and formatting statistics JSON
            urlstr = 'https://%s.%s.org/w/api.php?action=query&meta=siteinfo&format=json&siprop=statistics&continue' % (
                lang, site)
            resp = requests.get(urlstr)
            if resp.status_code != 200:
                continue
            try:
                stats = resp.json()
            except json.decoder.JSONDecodeError:
                continue

            m = stats['query']['statistics']
            e = [int(m['articles']),
                 int(m['pages']),
                 int(m['edits']),
                 int(m['users']),
                 int(m['activeusers']),
                 int(m['admins']),
                 int(m['images']),
                 lang,
                 site]
            articles, pages, edits, users, activeusers, admins, images, lang, site = e

            # Depth calculation
            try:
                depth = (edits / pages) * \
                    ((float(pages) - articles) / articles) ** 2.
                if depth > 300 and articles < 100000:
                    depth = '-'
                else:
                    depth = "%.2f" % depth
            except ZeroDivisionError:
                depth = '-'
            e.append(depth)
            datas.append(e)
            i += 1
            print(('%s >'
                   ' lahatsoratra:%d;'
                   ' pejy:%d;'
                   ' fanovana:%d;'
                   ' mpikambana:%d;'
                   ' mavitrika:%d;'
                   ' mpandrindra:%d;'
                   ' sary:%d;'
                   ' halalina:%s ' % (
                       lang, articles, pages, edits, users,
                       activeusers, admins, images, depth
                   )))

        # Sort
        datas.sort(reverse=True)
        self.wikitext(datas, wiki)

    def wikitext(self, e, wiki):
        total = {
            'pages': 0,
            'allpages': 0,
            'edits': 0,
            'admins': 0,
            'activeusers': 0,
            'users': 0,
            'files': 0,
        }
        content = ("""
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
! Halalim-pejy""")
        i = 0
        # total = (0,0,0,0,0,0)
        for wikistats_data in e:
            print(wikistats_data)
            articles, pages, edits, users, activeusers, admins, images, lang, site, depth = wikistats_data
            total['pages'] += articles
            total['allpages'] += pages
            total['edits'] += edits
            total['admins'] += admins
            total['users'] += users
            total['activeusers'] += activeusers
            total['files'] += images

        for wikistats_data in e:
            articles, pages, edits, users, activeusers, admins, images, lang, site, depth = wikistats_data
            wikistats_data = {
                'articles': articles,
                'pages': pages,
                'edits': edits,
                'users': users,
                'activeusers': activeusers,
                'admins': admins,
                'images': images,
                'language': lang,
                'wiki': site,
                'depth': depth
            }
            i += 1
            isanjato = float(float(100 * articles) / total['pages'])
            content += ("""
|- style="text-align: right;"
| """ + str(i) + """
| [[:w:Fiteny {{%(language)s}}|{{%(language)s}}]]
| [//%(language)s.%(wiki)s.org/wiki/ %(language)s]
| [//%(language)s.%(wiki)s.org/w/api.php?action=query&meta=siteinfo&format=xml&siprop=statistics '''{{formatnum:%(articles)d}}''']
| {{formatnum:%(pages)d}}
| [//%(language)s.%(wiki)s.org/wiki/Special:Recentchanges {{formatnum:%(edits)d}} ]
| [//%(language)s.%(wiki)s.org/wiki/Special:Listadmins {{formatnum:%(admins)d}}]
| [//%(language)s.%(wiki)s.org/wiki/Special:Listusers {{formatnum:%(users)d}}]
| [//%(language)s.%(wiki)s.org/wiki/Special:ActiveUsers {{formatnum:%(activeusers)d}}]
| [//%(language)s.%(wiki)s.org/wiki/Special:Imagelist {{formatnum:%(images)d}}]
| {{formatnum:""" % wikistats_data + """%2.2f""" % isanjato + """}}
| %(depth)s
""" % wikistats_data)
        content += "\n\n|}\n\n"
        content += """
{|class="wikitable sortable" border="1" cellpadding="2" cellspacing="0" style="width:100%; background: #f9f9f9; border: 1px solid #aaaaaa; border-collapse: collapse; white-space: nowrap; text-align: center"""
        content += """
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
""" % total
        content += """
|}"""

        while True:
            if self.test:
                break
            try:
                page = pywikibot.Page(
                    pywikibot.Site(
                        'mg', 'wiktionary'), 'Mpikambana:%s/Lisitry ny %s/tabilao' %
                    (current_user, wiki))
                page.put(content, 'Rôbô : fanavaozana ny statistika')
                break
            except Exception:
                print('Hadisoana nitranga tampametrahana ilay pejy')


def main():
    timeshift = 3
    bot = Wikilister()

    while True:
        t = list(time.gmtime())
        cond = (not (t[3] + timeshift) % 6) and (t[4] == 0)
        if cond:
            bot.run('Wikibolana', 'wiktionary')
            bot.run('pywikibot', 'pywikibot')
            time.sleep(120)
        else:
            print("Fanavaozana isaky ny adin'ny 6")
            print(("Miandry ny fotoana tokony hamaozana ny pejy (ora %2d:%2d) (GMT+%d)" %
                  ((t[3] + timeshift), t[4], (timeshift))))
            time.sleep(30)


if __name__ == '__main__':
    wikilisting = Wikilister()
    wikilisting.run('Wikibolana', 'wiktionary')
    wikilisting.run('Wikipedia', 'wikipedia')
    wikilisting.run('Wikiboky', 'wikibooks')
    pywikibot.stopme()
