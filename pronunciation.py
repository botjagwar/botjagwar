import re
import sys

import pywikibot

from api.page_lister import get_pages_from_category


def replace_pronunciation_template(language, language_name):
    for mg_page in get_pages_from_category("mg", language_name):
        old_content = mg_content = mg_page.get()
        print(">>>>", mg_page.title(), "<<<<")
        if "{{fanononana||%s}}" % language in mg_content:
            mg_content = mg_content.replace(
                "{{fanononana| |%s}}" % language, "{{fanononana-%s}}" % language
            )
            mg_content = mg_content.replace(
                "{{fanononana||%s}}" % language, "{{fanononana-%s}}" % language
            )

            pywikibot.showDiff(old_content, mg_content)
            mg_page.put(mg_content, f"{language_name}: manampy fanononana")
        else:
            print("{{fanononana||%s}} not found" % language)


def copy_pronunciations(language, language_name, ipa_or_pron="IPA"):
    pron_regex = re.compile("\\{\\{%s\\|(.*)\\|([a-z]+)\\}\\}" % ipa_or_pron)
    for mg_page in get_pages_from_category("mg", language_name):
        print(">>>>", mg_page.title(), "<<<<")
        en_page = pywikibot.Page(pywikibot.Site("en", "wiktionary"), mg_page.title())
        if en_page.isRedirectPage():
            print("redirect")
            continue
        if en_page.exists():
            en_content = en_page.get()
            match = [x for x in pron_regex.findall(en_content) if x[0] == language]
            if not match:
                print("no match")
                continue

            old_content = mg_content = mg_page.get()
            if "{{fanononana||%s}}" % language in mg_content:
                print(match)
                concat_pron = "".join(m[1] for m in match)
                mg_content = mg_content.replace(
                    "{{fanononana||%s}}" % language,
                    "{{fanononana-%s|%s}}" % (language, concat_pron),
                )
                pywikibot.showDiff(old_content, mg_content)
                mg_page.put(mg_content, f"{language_name}: manampy fanononana")
            else:
                print("{{fanononana||%s}} not found" % language)
        else:
            print("english page does not exist")
            continue


def copy_pronunciations(language, language_name, ipa_or_pron="IPA"):
    pron_regex = re.compile("\\{\\{([a-z]+)\\-%s\\|(.*)\\}\\}" % ipa_or_pron)
    for mg_page in get_pages_from_category("mg", language_name):
        print(">>>>", mg_page.title(), "<<<<")
        en_page = pywikibot.Page(pywikibot.Site("en", "wiktionary"), mg_page.title())
        if en_page.isRedirectPage():
            print("redirect")
            continue
        if en_page.exists():
            en_content = en_page.get()
            match = [x for x in pron_regex.findall(en_content) if x[0] == language]
            if not match:
                print("no match")
                continue

            old_content = mg_content = mg_page.get()
            if "{{fanononana||%s}}" % language in mg_content:
                print(match)
                concat_pron = "".join(m[1] for m in match)
                mg_content = mg_content.replace(
                    "{{fanononana||%s}}" % language,
                    "{{fanononana-%s|%s}}" % (language, concat_pron),
                )
                pywikibot.showDiff(old_content, mg_content)
                mg_page.put(mg_content, f"{language_name}: manampy fanononana")
            else:
                print("{{fanononana||%s}} not found" % language)
        else:
            print("english page does not exist")
            continue


if __name__ == "__main__":
    functions = {"c": copy_pronunciations, "r": replace_pronunciation_template}
    functions[sys.argv[1]](sys.argv[2], sys.argv[3])
