import re

import pywikibot as pwbot
from core import Translation

def testTranslate(val):
    test = Translation()
    verbose = True
    listpagestring = parseErrlog()
    for page in listpagestring:
        page = page.decode('utf8')
        for lang in ['en', 'fr']:
            print lang
            print "------------------"
            Page = pwbot.Page(pwbot.Site(lang, 'wiktionary'), page)
            test.process_wiktionary_page(lang, Page)


def parseErrlog():
    ret = []
    in_file = file(data_file + 'dikantenyvaovao.exceptions', 'r').readlines()
    for item in in_file:
        pwbot.output(item)
        item = item.strip('\n')

        regex = re.search("\[\[(.*)\]\]", item)
        if regex is None:
            continue

        string = regex.groups()[0]
        ret.append(string[3:-3])
    return ret