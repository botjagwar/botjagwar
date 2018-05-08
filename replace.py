import pywikibot

def replace():
    print('fetching fr_words')
    fr_words = [page.title() for page in pywikibot.Category(pywikibot.Site('fr', 'wiktionary'), "gaulois").articles()]
    print('done fetching fr_words')
    for page in pywikibot.Category(pywikibot.Site('mg', 'wiktionary'),
                                   "gadaba an'i Mudhili").articles():
        title = page.title()
        pywikibot.output('>>>> %s <<<<<' % title)
        if title not in fr_words:
            continue
        content = page.get()
        new_content = content
        new_content = new_content.replace("=gau=", '=xtg=')
        new_content = new_content.replace("|gau}}", '|xtg}}')
        pywikibot.showDiff(content, new_content)
        page.put(new_content, "manitsy kaody ho an'ny teny gôloà (gau --> xtg)")

if __name__ == '__main__':
    replace()