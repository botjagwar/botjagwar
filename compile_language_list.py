import pywikibot


def main():
    s = """
{| class="wikitable sortable" width="100%"
! Fiteny
! Teny iditra
    """
    main_category = pywikibot.Category(pywikibot.Site("mg", "wiktionary"), "fiteny")

    for c in main_category.subcategories():
        name = c.titleWithoutNamespace()
        s += (
            "\n|-\n| [[:sokajy:"
            + name
            + "|"
            + name
            + "]]\n| {{PAGESINCATEGORY:"
            + name
            + "}}"
        )

    s += "\n|}\n"
    return s


if __name__ == "__main__":
    s = main()
    print(s)
