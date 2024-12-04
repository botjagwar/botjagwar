import pywikibot

SITENAME = "wiktionary"


def load_pages_from_category(working_language, category_name):
    with open(f"user_data/list_{working_language}_{category_name}", "w") as f:
        pages = pywikibot.Category(
            pywikibot.Site(working_language, SITENAME), category_name
        )
        for word_page in pages.articles():
            f.write(word_page.title() + "\n")


def load_categories_from_category(working_language, category_name):
    with open(f"user_data/category_list_{working_language}_{category_name}", "w") as f:
        pages = pywikibot.Category(
            pywikibot.Site(working_language, SITENAME), category_name
        )
        for word_page in pages.subcategories():
            f.write(word_page.title(with_ns=False) + "\n")


def get_categories_for_category(working_language, category_name):
    def read_categories_in_category():
        with open(f"user_data/category_list_{working_language}_{category_name}", "r") as f:
            for line in f:
                title = line.strip("\n")
                if title:
                    yield pywikibot.Page(
                        pywikibot.Site(working_language, SITENAME), title
                    )

    try:
        yield from read_categories_in_category()
    except FileNotFoundError:
        load_categories_from_category(working_language, category_name)
        yield from read_categories_in_category()


def parameterized_get_pages_from_category(site_class, page_class):
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
            with open(f"user_data/list_{working_language}_{category_name}", "r") as f:
                for line in f:
                    title = line.strip("\n")
                    if title:
                        yield page_class(site_class(working_language, SITENAME), title)

        try:
            yield from read_pages_in_category()
        except FileNotFoundError:
            load_pages_from_category(working_language, category_name)
            yield from read_pages_in_category()

    return get_pages_from_category


def redis_get_pages_from_category(working_language, category_name):
    from redis_wikicache import RedisSite, RedisPage

    return parameterized_get_pages_from_category(RedisSite, RedisPage)(
        working_language, category_name
    )


def get_pages_from_category(working_language, category_name):
    return parameterized_get_pages_from_category(pywikibot.Site, pywikibot.Page)(
        working_language, category_name
    )


if __name__ == "__main__":
    import sys

    language, category_name = sys.argv[1:3]
    count = sum(1 for _ in get_pages_from_category(language, category_name))
    print(language, category_name, count)
