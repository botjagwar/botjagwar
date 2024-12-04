import re
import sys

import pywikibot

reason = "[[:m:Requests for comment/Large-scale errors at Malagasy Wiktionary/mg|Famafana ambongadiny vokatry ny fanadihadiana momba ny Wikibolana malagasy]]"
count = 1

site = pywikibot.Site("mg", "wiktionary")
bots = set(["Interwicket", "JanDbot"] + [i["name"] for i in site.botusers()])


def is_edited_by_bot_only(page: pywikibot.Page) -> bool:
    contributors = set(page.contributors())
    is_edited_by_bot_only = True
    for contributor in contributors:
        if (
            not contributor.lower().endswith("bot")
            and not contributor.lower().startswith("bot")
            and contributor not in bots
        ):
            print(contributor, " is not a bot!")
            is_edited_by_bot_only = False

    return is_edited_by_bot_only


def mass_delete():
    global count
    cat = "Dikanteny tokony homarinana"
    for page in pywikibot.Category(pywikibot.Site("mg", "wiktionary"), cat).articles():
        if page.exists() and not page.isRedirectPage():
            print(page.title())
            if ":" in page.title():
                page.delete(reason)
                continue

            try:
                if "{{=mg=}}" not in page.get():
                    created = list(page.revisions())[-1]
                    if created.timestamp < pywikibot.Timestamp(2020, 11, 1, 0, 0, 0) and is_edited_by_bot_only(page):
                        page.delete(reason)
                        continue
                    try:
                        if is_edited_by_bot_only(page):
                            page.delete(reason)
                    except Exception as e:
                        print(e)
            except Exception as e:
                print(e)


def section_delete(section_name, wiki_page):
    print("deleting ", section_name)
    if section_name not in wiki_page:
        return wiki_page
    lines = wiki_page.split("\n")
    section_begin = None
    section_end = None
    for line_no, line in enumerate(lines):
        section_rgx = re.search(f"==[ ]?{section_name}[ ]?==", line)
        if section_rgx is not None and section_begin is None:
            section_begin = line_no
            continue

        if section_begin is not None:
            section_end_rgx = re.search("==[ ]?{{=", line)
            if section_end_rgx is not None:
                section_end = line_no
                break

    assert section_begin is not None
    to_delete = (
        "\n".join(lines[section_begin:section_end])
        if section_end is not None
        else "\n".join(lines[section_begin:])
    )
    return wiki_page.replace(to_delete, "")


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
