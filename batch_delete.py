import sys

import pywikibot

reason = "[[:m:Requests for comment/Large-scale errors at Malagasy Wiktionary/mg|Famafana ambongadiny vokatry ny fanadihadiana momba ny Wikibolana malagasy]]"
count = 1

site = pywikibot.Site('mg', 'wiktionary')
bots = set([i['name'] for i in s.botusers()])

def is_edited_by_bot_only(page: pywikibot.Page) -> bool:
    contributors = set(page.contributingUsers())
    for contributor in contributors:
        if contributor not in bots:
            return False
    return True

with open(sys.argv[1], 'r') as f:
    for line in f:
        count += 1
        if count <= 1016314:
            continue
        page = pywikibot.Page(pywikibot.Site('mg', 'wiktionary'), line)
        if page.exists() and not page.isRedirectPage():
            content = page.get()
            if '{{=mg=}}' not in content:
                print(count, line[:-1])
                try:
                    if is_edited_by_bot_only(page):
                        page.delete(reason)
                except Exception:
                    pass


