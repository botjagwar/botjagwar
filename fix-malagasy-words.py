import pywikibot
import requests

from api.page_lister import get_pages_from_category


class Fixer(object):
    def run_fixer(self, *args, **kwargs):
        raise NotImplementedError()

    def run(self):
        for page in get_pages_from_category("mg", "Pejy ahitana dikan-teny"):
            self.run_fixer(page)


class TranslationFixer(Fixer):
    def run_fixer(self, page):
        """
        Translations are included in the "{{-dika-}}" section and traditionally end with "{{}} :"
        This function will change that by deleting the "{{}} :" section and including each translation with a dedicated
        template "{{dikan-teny|x|y}}"
        :param page:
        :return:
        """
        section_template = "{{-dika-}}"
        text = page.get()
        print(f">>> {page.title()} <<< ")

        if section_template not in text:
            return

        if "{{}} :" not in text:
            return

        lines = text.split("\n")
        kept_lines, deleted_lines = self.remove_between_lines(
            lines, section_template, "{{}} :"
        )
        pos = self.get_part_of_speech(text)
        convergent_translations = self.fetch_convergent_translations(page.title(), pos)
        translation_section = "{{-dika-}}\n"
        for language_code, translations in convergent_translations:
            line = "# {{%s}} : " % language_code
            for translation in translations:
                line += (
                    "{{dikan-teny|"
                    + translation["word"]
                    + "|"
                    + translation["language"]
                    + "}}, "
                )
            line = line.strip(", ")
            line += "\n"
            translation_section += line

        new_text = text.replace("\n".join(deleted_lines), translation_section)

        translations = len(convergent_translations)
        print(f"{translations} translations suggested.")
        pywikibot.showDiff(text, new_text)
        if translations:
            summary = "Nanitsy dikan-teny"
        else:
            summary = "Nanitsy fizarana sy ny mpitazon-toerana"

        page.put(new_text, summary)

    @staticmethod
    def get_part_of_speech(content):
        for pos in ["ana", "mat", "mpam"]:
            if f"-{pos}-|mg" in content:
                return pos
        if "-verb-|mg" in content:
            return "mat"
        if "-nom-|mg" in content:
            return "ana"
        if "-adj-|mg" in content:
            return "mpam"
        return "mpam" if "-mpam-ana-|mg" in content else "ana"

    @staticmethod
    def fetch_convergent_translations(word, part_of_speech):
        parameters = {
            "part_of_speech": f"eq.{part_of_speech}",
            "select": "word,language,part_of_speech",
            "suggested_definition": f"eq.{word}",
        }

        rq = requests.get(
            "http://localhost:8100/convergent_translations", params=parameters
        )
        convergent_translations_json = rq.json()
        convergent_translations = {}
        for data in convergent_translations_json:
            if data["language"] in convergent_translations:
                convergent_translations[data["language"]].append(data)
            else:
                convergent_translations[data["language"]] = [data]

        return sorted(convergent_translations.items())

    @staticmethod
    def remove_between_lines(lines, begin_line, end_line=None):
        kept_lines = []
        deleted_lines = []
        entered = False
        exited = False
        for line in lines:
            if begin_line in line:
                entered = True

            if not entered and not exited:
                kept_lines.append(line)
            else:
                deleted_lines.append(line)

            if end_line in line:
                entered = False

        return kept_lines, deleted_lines


class AnagramFixer(Fixer):
    def run_fixer(self, page):
        pass


if __name__ == "__main__":
    bot = TranslationFixer()
    try:
        bot.run()
        # bot.run_fixer(pywikibot.Page(pywikibot.Site('mg', 'wiktionary'), 'rano'))
    finally:
        pywikibot.stopme()
