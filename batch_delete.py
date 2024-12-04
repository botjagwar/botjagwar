import re
import sys

import pywikibot

reason = "Voaforona an-kadisoana"
count = 1

site = pywikibot.Site("mg", "wiktionary")
bots = set(["Interwicket", "JanDbot"] + [i["name"] for i in site.botusers()])


def is_edited_by_bot_only(page: pywikibot.Page) -> bool:
    contributors = set(page.contributors())
    is_edited_by_bot_only = True
    for contributor in contributors:
        if not contributor.lower().endswith("bot") and contributor not in bots:
            print(contributor, " is not a bot!")
            is_edited_by_bot_only = False

    return is_edited_by_bot_only


def mass_delete2():
    global count
    with open(sys.argv[1], "r") as f:
        for line in f:
            count += 1
            if count <= 0:
                continue
            page = pywikibot.Page(pywikibot.Site("mg", "wiktionary"), line)
            if page.exists() and not page.isRedirectPage():
                content = page.get()
                if "{{=mg=}}" not in content:
                    print(count, line[:-1])
                    try:
                        if is_edited_by_bot_only(page):
                            page.delete(reason)
                    except Exception as e:
                        print(e)


def mass_delete():
    global count
    with open(sys.argv[1], "r") as f:
        for line in f:
            count += 1
            if count <= 0:
                continue
            page = pywikibot.Page(pywikibot.Site("mg", "wiktionary"), line)
            if page.exists() and not page.isRedirectPage():
                page.delete(reason)


def section_delete(section_name, wiki_page):
    print("deleting ", section_name)
    if section_name in wiki_page:
        lines = wiki_page.split("\n")
        section_begin = None
        section_end = None
        for line_no, line in enumerate(lines):
            section_rgx = re.search("==[ ]?" + section_name + "[ ]?==", line)
            if section_rgx is not None and section_begin is None:
                section_begin = line_no
                continue

            if section_begin is not None:
                section_end_rgx = re.search("==[ ]?{{=", line)
                if section_end_rgx is not None:
                    section_end = line_no
                    break

        assert section_begin is not None
        if section_end is not None:
            to_delete = "\n".join(lines[section_begin:section_end])
        else:
            to_delete = "\n".join(lines[section_begin:])

        new_text = wiki_page.replace(to_delete, "")
        return new_text
    else:
        return wiki_page


def remove_bot_section():
    global count
    with open(sys.argv[1], "r") as f:
        for line in f:
            line = line.strip("\n")
            line = line.split("\t")
            count += 1
            if count <= 0:
                continue
            title = line[0]
            sections = line[1:]
            print(title, sections)
            print(">>>> ", line, " <<<<")
            page = pywikibot.Page(pywikibot.Site("mg", "wiktionary"), title)
            if page.exists() and not page.isRedirectPage():
                content = page.get()
                try:
                    to_delete = False
                    if True:  # is_edited_by_bot_only(page):
                        to_delete = True

                    created = page.getVersionHistory()[-1]
                    print("created on ", created.timestamp)
                    if created.timestamp < pywikibot.Timestamp(2020, 9, 28, 0, 0, 0):
                        to_delete = True

                    if to_delete:
                        for section in sections:
                            content = section_delete(section, content)
                        pywikibot.showDiff(page.get(), content)
                        page.put(content, reason)
                except Exception as e:
                    print(e)


if __name__ == "__main__":
    mass_delete()
