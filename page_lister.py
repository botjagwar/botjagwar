import pywikibot

SITENAME = 'wiktionary'


def load_pages_from_category(working_language, category_name):
    with open('user_data/list_%s_%s' % (working_language, category_name), 'w') as f:
        pages = pywikibot.Category(pywikibot.Site(working_language, SITENAME), category_name)
        for word_page in pages.articles():
            f.write(word_page.title() + '\n')


def load_categories_from_category(working_language, category_name):
    with open('user_data/category_list_%s_%s' % (working_language, category_name), 'w') as f:
        pages = pywikibot.Category(pywikibot.Site(working_language, SITENAME), category_name)
        for word_page in pages.subcategories():
            f.write(word_page.title(with_ns=False) + '\n')


def get_categories_for_category(working_language, category_name):
    def read_categories_in_category():
        with open('user_data/category_list_%s_%s' % (working_language, category_name), 'r') as f:
            for line in f.readlines():
                title = line.strip('\n')
                if title:
                    yield pywikibot.Page(pywikibot.Site(working_language, SITENAME), title)

    try:
        for p in read_categories_in_category():
            yield p
    except FileNotFoundError:
        load_categories_from_category(working_language, category_name)
        for p in read_categories_in_category():
            yield p


def get_pages_from_category(working_language, category_name):
    """
    Yields a page list from a given category.
    - Page list is fetched from a local file in user_data.
      - If file doesn't exist, load the page list from on-wiki category, and saves it locally for future use
    :param working_language
    :param category_name
    :return:
    """
    def read_pages_in_category():
        with open('user_data/list_%s_%s' % (working_language, category_name), 'r') as f:
            for line in f.readlines():
                title = line.strip('\n')
                if title:
                    yield pywikibot.Page(pywikibot.Site(working_language, SITENAME), title)

    try:
        for p in read_pages_in_category():
            yield p
    except FileNotFoundError:
        load_pages_from_category(working_language, category_name)
        for p in read_pages_in_category():
            yield p


if __name__ == '__main__':
    import sys
    language, category_name = sys.argv[1:3]
    count = 0
    for p in get_pages_from_category(language, category_name):
        count += 1
    print (language, category_name, count)