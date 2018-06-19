import pywikibot

CATEGORIES = {
    "Mpamaritra anarana": ["Endri-pamaritra anarana"],
    "Anarana iombonana": ["Endrik'anarana"],
    "Matoanteny": ["Endriky ny matoanteny"],
}

languages = pywikibot.Category(pywikibot.Site('mg', 'wiktionary'), 'fiteny')
for language in languages.subcategories():
    print('>>>>>', language, '<<<<<')
    language_name = language.title().split(':')[1]
    for root, subcat_titles in CATEGORIES.items():
        for subcat_element in subcat_titles:
            subcat_title = "%s amin'ny teny %s" % (subcat_element, language_name)
            subcat = pywikibot.Category(pywikibot.Site('mg', 'wiktionary'), subcat_title)
            if not subcat.isEmptyCategory():
                print('sokajy misy zavatra')
                content = '[[sokajy:%s]]\n' % subcat_element
                content += '[[sokajy:%s]]' % language_name
                subcat.put(content, 'sokajy vaovao')
            else:
                print('sokajy babangoana')