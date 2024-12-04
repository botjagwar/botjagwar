import pywikibot
import requests

from api.importer import AdditionalDataImporter
from api.page_lister import get_pages_from_category
from api.servicemanager.pgrest import DynamicBackend

dyn_backend = DynamicBackend()


def use_wiktionary(language):
    def wrap_use_wiki(cls):
        cls.wiki = pywikibot.Site(language, "wiktionary")
        return cls

    return wrap_use_wiki


class WiktionaryAdditionalDataImporter(AdditionalDataImporter):
    section_name: str = None

    def get_additional_data_for_category(self, language, category_name):
        url = f"{dyn_backend.backend}/word_with_additional_data"
        params = {
            "language": f"eq.{language}",
            "select": "word,additional_data",
        }
        words = requests.get(url, params=params).json()
        # Database entries containing the data_type already defined.
        already_defined_pages = {
            w["word"]
            for w in words
            if self.is_data_type_already_defined(w["additional_data"])
        }

        url = f"{dyn_backend.backend}/word"
        params = {
            "language": f"eq.{language}",
        }
        words = requests.get(url, params=params).json()
        pages_defined_in_database = {w["word"] for w in words}
        self.counter = 0
        category_pages = {
            k.title() for k in get_pages_from_category("en", category_name)
        }
        # Wiki pages who may have not been parsed yet
        titles = (category_pages & pages_defined_in_database) - already_defined_pages
        wikipages = {pywikibot.Page(self.wiktionary, page) for page in titles}

        # print(f"{len(wikipages)} pages from '{category_name}';\n"
        #       f"{len(already_defined_pages)} already defined pages "
        #       f"out of {len(category_pages)} pages in category\n"
        # f"and {len(pages_defined_in_database)} pages currently defined in
        # DB\n\n")
        for wikipage in wikipages:
            self.process_wikipage(wikipage, language)

    def process_wikipage(self, wikipage: pywikibot.Page, language: str):
        content = wikipage.get()
        title = wikipage.title()
        return self.process_non_wikipage(title, content, language)

    def run(self, root_category: str, wiktionary=pywikibot.Site("en", "wiktionary")):
        self.wiktionary = wiktionary
        category = pywikibot.Category(wiktionary, root_category)
        for category in category.subcategories():
            name = category.title().replace("Category:", "")
            # print(name)
            language_name = name.split()[0]
            if language_name in self.languages:
                iso = self.languages[language_name]
                # print(f'Fetching for {language_name} ({iso})')
                self.get_additional_data_for_category(iso, category.title())
            # else:
            # print(f'Skipping for {language_name}...')


class TemplateImporter(WiktionaryAdditionalDataImporter):
    def get_data(self, template_title: str, wikipage: str, language: str) -> list:
        retrieved = []
        for line in wikipage.split("\n"):
            if "{{" + template_title + "|" + language in line:
                line = line[line.find("{{" + template_title + "|" + language) :]
                data = line.split("|")[2]
                data = data.replace("}}", "")
                data = data.replace("{{", "")
                retrieved.append(data)

        return retrieved


class SubsectionImporter(WiktionaryAdditionalDataImporter):
    section_name = ""
    # True if the section contains a number e.g. Etymology 1, Etymology 2, etc.
    numbered = False
    level = 3

    def __init__(self, **params):
        super(SubsectionImporter, self).__init__(**params)

    def set_whole_section_name(self, section_name: str):
        self.section_name = section_name

    def get_data(self, template_title, wikipage: str, language: str) -> list:
        raise NotImplementedError()
