import pywikibot

from api.page_lister import redis_get_pages_from_category as get_pages_from_category


def replace():
    print('fetching mg_words')
    for page in get_pages_from_category('mg', "Endrik'anarana amin'ny teny malagasy"):
        title = page.title()
        content = page.get()
        new_content = content
        new_content = new_content.replace("Mpanao voalohany", 'Mpandray anjara voalohany')
        new_content = new_content.replace("Mpanao faharoa", 'Mpandray anjara faharoa')
        new_content = new_content.replace("Mpanao fahatelo", 'Mpandray anjara fahatelo')
        if content == new_content:
            print(f"No change necessary for {title}")
            continue
        pywikibot.output('>>>> %s <<<<<' % title)
        pywikibot.showDiff(content, new_content)
        page.put(
            new_content,
            "fanitsiana: 'mpanao' lasa 'mpandray anjara'")


if __name__ == '__main__':
    replace()
