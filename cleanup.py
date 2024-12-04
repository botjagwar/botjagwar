import pywikibot

from api.page_lister import get_pages_from_category


def cleanup(content):
    content = content.replace("{{-dika-}}", "")
    content = content.replace("{{}} :", "")
    return content


for counter, page in enumerate(get_pages_from_category("mg", "Pejy ahitana dikan-teny")):
    print(">>>>", page.title(), "<<<<")
    old = content = page.get()
    changed = False
    if content.find("{{anag+}}") != -1:
        changed = True
        content = content.replace("{{anag+}}", "")

    if content.find("=mg=") == -1:
        changed = True
        content = cleanup(content)
    elif content.find("-e-mat-|mg") != -1 or content.find("-e-ana-|mg") != -1:
        changed = True
        content = cleanup(content)

    if changed:
        pywikibot.showDiff(old, content)
    page.put(content, "fandiovana")
