import json

from api.page_lister import load_categories_from_category
from redis_wikicache import RedisSite as Site, RedisPage as Page


class LanguageStatisticsBuilder(object):
    def __init__(self):
        load_categories_from_category("mg", "fiteny")

        self.languages = []
        with open("user_data/category_list_mg_fiteny", "r") as opened_file:
            self.languages.extend(entry.strip("\n") for entry in opened_file)
        self.languages.sort()
        self._data = {}

    @property
    def data(self):
        if not self._data:
            self.fetch_data()
        return self._data

    def fetch_data(self):
        with open("user_data/category_stats_mgwiktionary.json", "r") as jsonfile:
            data = json.load(jsonfile)
            for category_name, pages in data["rows"]:
                self._data[category_name] = pages

    # def fetch_data(self):
    #     toolforge.set_user_agent('Bot-Jagwar')
    #     connection = toolforge.connect("mgwiktionary")
    #     with connection.cursor() as cursor:
    #         cursor.execute("select cat_title as category_name, cat_pages as page from category where cat_pages > 9;")
    #         self._data = cursor.fetchall()

    def run(self):
        data = self.data
        table_text = """
{| class="wikitable sortable" width="100%"
! Fiteny
! Teny rehetra
! Foto-teny
! Endri-teny
"""
        for language in self.languages:
            # print(language)
            if language.replace(" ", "_") not in data:
                continue

            lemma = sum(
                data[f"{pos} amin'ny teny {language}".replace(" ", "_")]
                for pos in [
                    "Anarana",
                    "Anarana iombonana",
                    "Mpamaritra",
                    "Mpamaritra anarana",
                    "Matoanteny",
                    "Tambinteny",
                    "Fomba fiteny",
                    "Mpampiankin-teny",
                    "Litera",
                ]
                if f"{pos} amin'ny teny {language}".replace(" ", "_") in data
            )
            form_of = sum(
                data[f"{pos} amin'ny teny {language}".replace(" ", "_")]
                for pos in [
                    "Endrik'anarana",
                    "Endri-pamaritra",
                    "Endriky ny matoanteny",
                    "Ova matoanteny",
                    "Rômanizasiona",
                ]
                if f"{pos} amin'ny teny {language}".replace(" ", "_") in data
            )
            entries = lemma + form_of
            table_text += f"""
|-
| [[:sokajy:{language}|{language}]]
| {" {{formatnum:" + str(entries) + "}}"}
| {" {{formatnum:" + str(lemma) + '}}'}
| {" {{formatnum:" + str(form_of) + '}}'}
"""
            print(language, entries, lemma, form_of)
        page = Page(Site("mg", "wiktionary"), "Wiktionary:statistika/tabilao")
        page.put(table_text + "\n|}", "fanavaozana")


if __name__ == "__main__":
    bot = LanguageStatisticsBuilder()
    bot.run()
