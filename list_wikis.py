# -*- coding: utf-8  -*-
import re, urllib, time
import pywikibot
from urllib import FancyURLopener

data_file = 'conf/list_wikis/'


class MyOpener(FancyURLopener):
    version = 'Botjagwar/v1.1'


class Wikilister(object):
    def __init__(self, test=False):
        self.test = test

    def getLangs(self, site):
        dump = file(data_file + 'listof%s.txt' % site, 'r').read()
        print data_file + 'listof%s.txt' % site

        wikiregex = re.findall('([a-z|\-]+).%s.org/wiki/Special:Recentchanges' % site, dump)
        if len(wikiregex) == 0:
            wikiregex = re.findall('\{\{fullurl:([a-z|\-]+):Special', dump)
        print wikiregex
        for lang in wikiregex:
            yield lang

    def run(self, wiki, site):
        datas = []
        i = 0
        for lang in self.getLangs(site):
            ierr = 0
            # if i>=5:break
            while ierr < 10:
                try:
                    urlstr = 'https://%s.%s.org/w/api.php?action=query&meta=siteinfo&format=json&siprop=statistics&continue' % (
                    lang, site)
                    statpage = urllib.urlopen(urlstr).read()
                    print statpage
                    pywikibot.output(urlstr)
                    break
                except Exception as e:
                    print e.message
                    time.sleep(5)

                except IOError as e:
                    print e.message
                    print "Hadisoana mitranga amin'i %s" % lang
                    time.sleep(5)
                    ierr += 1
            del ierr
            try:
                stats = eval(statpage)
            except Exception:
                print 'Nitrangana hadisoana: %s' % statpage
                continue
            m = stats['query']['statistics']
            e = (int(m['articles']),
                 {'articles': int(m['articles']),
                  'pages': int(m['pages']),
                  'edits': int(m['edits']),
                  'users': int(m['users']),
                  'activeusers': int(m['activeusers']),
                  'admins': int(m['admins']),
                  'images': int(m['images']),
                  'language': lang,
                  'wiki': site})
            try:
                e[1]['depth'] = float(e[1]['edits']) / float(e[1]['pages']) * (float(
                    e[1]['pages'] - e[1]['articles']) / float(e[1]['articles'])) ** 2.

                if e[1]['depth'] > 300 and e[1]['articles'] < 100000:
                    e[1]['depth'] = '-'

                if e[1]['depth'] != '-':
                    e[1]['depth'] = "%.2f" % e[1]['depth']
            except ZeroDivisionError:
                e[1]['depth'] = '-'

            datas.append(e)
            i += 1
            print '%(language)s > lahatsoratra:%(articles)d; pejy:%(pages)d; fanovana:%(edits)d; mpikambana:%(users)d; mavitrika:%(activeusers)d; mpandrindra:%(admins)d; sary:%(images)d; halalina:%(depth)s ' % (
            e[1])

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
        content = (u"""
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
        for wd in e:
            total['pages'] += wd[1]['articles']
            total['allpages'] += wd[1]['pages']
            total['edits'] += wd[1]['edits']
            total['admins'] += wd[1]['admins']
            total['users'] += wd[1]['users']
            total['activeusers'] += wd[1]['activeusers']
            total['files'] += wd[1]['images']
        for wd in e:
            i += 1
            isanjato = float(float(100 * wd[1]['articles']) / total['pages'])
            content += (u"""
|- style="text-align: right;"
| """ + str(i) + u"""
| [[:w:Fiteny {{%(language)s}}|{{%(language)s}}]]
| [//%(language)s.%(wiki)s.org/wiki/ %(language)s]
| [//%(language)s.%(wiki)s.org/w/api.php?action=query&meta=siteinfo&format=xml&siprop=statistics '''{{formatnum:%(articles)d}}''']
| {{formatnum:%(pages)d}}
| [//%(language)s.%(wiki)s.org/wiki/Special:Recentchanges {{formatnum:%(edits)d}} ]
| [//%(language)s.%(wiki)s.org/wiki/Special:Listadmins {{formatnum:%(admins)d}}]
| [//%(language)s.%(wiki)s.org/wiki/Special:Listusers {{formatnum:%(users)d}}]
| [//%(language)s.%(wiki)s.org/wiki/Special:ActiveUsers {{formatnum:%(activeusers)d}}]
| [//%(language)s.%(wiki)s.org/wiki/Special:Imagelist {{formatnum:%(images)d}}]
| {{formatnum:""" % wd[1] + u"""%2.2f""" % isanjato + u"""}}
| %(depth)s
""" % wd[1])
        content += u"\n\n|}\n\n"
        content += u"""
{|class="wikitable sortable" border="1" cellpadding="2" cellspacing="0" style="width:100%; background: #f9f9f9; border: 1px solid #aaaaaa; border-collapse: collapse; white-space: nowrap; text-align: center"""
        content += u"""
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
        content += u"""
|}"""

        while 1:
            if self.test == True: break
            try:
                page = pywikibot.Page(pywikibot.Site('mg', 'wiktionary'),
                                      'Mpikambana:Bot-Jagwar/Lisitry ny %s/tabilao' % wiki)
                page.put(content, u'Rôbô : fanavaozana ny statistika')
                break
            except Exception:
                print 'Hadisoana nitranga tampametrahana ilay pejy'


def main():
    pywikibot.stopme()
    (pywikibot.config).put_throttle = int(1)
    timeshift = 3
    bot = Wikilister()

    while (1):
        t = list(time.gmtime())
        cond = (not (t[3] + timeshift) % 6) and (t[4] == 0)
        if cond:
            bot.run('Wikibolana', 'wiktionary')
            bot.run('pywikibot', 'pywikibot')
            time.sleep(120)
        else:
            print "Fanavaozana isaky ny adin'ny 6"
            print "Miandry ny fotoana tokony hamaozana ny pejy (ora %2d:%2d) (GMT+%d)" % (
            (t[3] + timeshift), t[4], (timeshift))
            time.sleep(30)


if __name__ == '__main__':
    wikilisting = Wikilister()
    wikilisting.run('Wikibolana', 'wiktionary')
    wikilisting.run('Wikipedia', 'wikipedia')
    wikilisting.run('Wikiboky', 'wikibooks')
    pywikibot.stopme()
