import pywikibot

from api.entryprocessor import WiktionaryProcessorFactory
from word_forms import create_non_lemma_entry


def crawl_categories_list():
    done = set()
    task_list = set()
    with open("user_data/crawled", "r") as crawled:
        for line in crawled:
            done.add(line.strip("\n"))

    with open("user_data/crawled", "w") as crawled:
        with open("user_data/categories", "r") as f:
            for line in f:
                task_list.add(line.strip("\n"))

        remaining = task_list.difference(done)
        for line in remaining:
            crawl_subcategories(line)
            crawled.write(line)


def crawl_subcategories(category_name):
    working_language = "en"
    # Initialise processor class
    en_page_processor_class = WiktionaryProcessorFactory.create(working_language)
    en_page_processor = en_page_processor_class()
    print(category_name)
    category = pywikibot.Category(
        pywikibot.Site(working_language, "wiktionary"), category_name
    )
    if not category.isEmptyCategory():
        pywikibot.output("▒▒ \03{green}%-25s\03{default} ▒▒" % category.title())
        for article in category.articles():
            pywikibot.output(article.title())
            en_page_processor.process(article)
            entries = en_page_processor.get_all_entries(definitions_as_is=True)
            print(article, entries)
            for entry in entries:
                create_non_lemma_entry(entry)


if __name__ == "__main__":
    try:
        crawl_categories_list()
    finally:
        pass
