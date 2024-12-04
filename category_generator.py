#!/usr/bin/python3

import pywikibot

CATEGORIES = {
    "Mpamaritra anarana": ["Endri-pamaritra anarana", "Mpamaritra"],
    "Anarana iombonana": ["Endrik'anarana"],
    "Matoanteny": ["Endriky ny matoanteny"],
    "Tambinteny": ["Endrika tambinteny"],
    "Mpisolo anarana": ["Endrika mpisolo anarana"],
}


wiki = pywikibot.Site("mg", "wiktionary")
languages = pywikibot.Category(wiki, "fiteny")

for language in languages.subcategories():
    print(">>>>>", language, "<<<<<")
    language_name = language.title().split(":")[1]
    for root, subcat_titles in CATEGORIES.items():
        for subcat_element in subcat_titles:
            subcat_title = "%s amin'ny teny %s" % (subcat_element, language_name)
            subcat = pywikibot.Category(wiki, subcat_title)

            if not subcat.isEmptyCategory():
                print("sokajy misy zavatra")
                content = "{{abidy}}\n"
                content += "* [[:mg:w:%s|%s]] eo amin'i [[:mg:|Wikipedia]]\n" % (
                    subcat_element,
                    subcat_element,
                )
                content += (
                    "* [[:mg:w:fiteny %s|Fiteny %s]] eo amin'i [[:mg:|Wikipedia]]\n"
                    % (language_name, language_name)
                )
                content += "[[sokajy:%s|%s]]\n" % (subcat_element, language_name[0])
                content += "[[sokajy:%s]]\n" % language_name
                subcat.put(content, "Mamorona zanatsokajy ho an'ny karazanteny")
            else:
                print(subcat_title, ": sokajy babangoana")
