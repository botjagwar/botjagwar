import sys

import pywikibot

from page_lister import get_categories_for_category


def generate_categories(category_name):
    for page in get_categories_for_category('mg', 'fiteny'):
        language = page.title()
        by_language_category_template = f"{category_name} amin'ny teny {language}"
        category = pywikibot.Category(
            pywikibot.Site('mg', 'wiktionary'),
            by_language_category_template)
        content = f'[[sokajy:{category_name}]]\n[[sokajy:{language}]]'
        if not category.isEmptyCategory():
            category.put(content)


if __name__ == '__main__':
    generate_categories(sys.argv[1])
