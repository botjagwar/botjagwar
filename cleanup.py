import pywikibot

from api.page_lister import get_pages_from_category


def cleanup(content):
    content = content.replace('{{-dika-}}', '')
    content = content.replace('{{}} :', '')
    return content


counter = 0
for page in get_pages_from_category('mg', 'Pejy ahitana dikan-teny'):
    counter += 1
    print('>>>>', page.title(), '<<<<')
    old = content = page.get()
    changed = False
    if content.find('{{anag+}}') != -1:
        changed = True
        content = content.replace('{{anag+}}', '')

    if content.find('=mg=') == -1:
        changed = True
        content = cleanup(content)
    else:
        if (content.find('-e-mat-|mg') != -1
            or content.find('-e-ana-|mg') != -1
            ):
            changed = True
            content = cleanup(content)

    if changed:
        pywikibot.showDiff(old, content)
    page.put(content, 'fandiovana')
