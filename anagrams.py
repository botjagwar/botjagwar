import argparse
import pickle
import random
import re

import pywikibot

from api.page_lister import get_pages_from_category

parser = argparse.ArgumentParser(description="Anagrams bot")
parser.add_argument("--begin", dest="BEGIN", required=False)
parser.add_argument("--code", dest="CODE", required=True)
parser.add_argument("--language-code", dest="LANGUAGE_CODE", required=True)
parser.add_argument("--language", dest="LANGUAGE", required=True)

args = parser.parse_args()


class AnagramsFinderBot(object):
    def __init__(self):
        # Mandatory
        self.language = args.LANGUAGE
        self.code = args.CODE

        # Optional
        self.language_code = args.LANGUAGE_CODE if args.LANGUAGE_CODE else None
        self.begin = self.get_alphagram(args.BEGIN) if args.BEGIN else None

        print("Beginning work from alphagram %s" % self.begin)
        self.filename = "/opt/botjagwar/user_data/anagrams_%s" % self.code
        self.line_filename = "/opt/botjagwar/user_data/anagrams_%s_%s.linefile" % (
            self.language,
            self.code,
        )
        self.page_list = [
            page for page in get_pages_from_category(args.CODE, args.LANGUAGE)
        ]
        self.language_regex = re.compile(r"=([a-z]+)=")
        self.pages_total = len(self.page_list)

        try:
            with open(self.filename, "r") as f:
                self.counter, self.anagrams = pickle.load(f)
        except Exception:
            self.counter = 0
            self.anagrams = {}

    def get_alphagram(self, word):
        str = word.upper()
        # return ''.join(sorted(c for c in str if c >= 'A' and c <= 'Z'))
        return "".join(sorted(c for c in str))

    def populate_anagrams(self):
        for page in self.page_list:
            alphagram = self.get_alphagram(page.title())
            if alphagram in self.anagrams:
                self.anagrams[alphagram].append(page)
            else:
                self.anagrams[alphagram] = [page]

    def add_anagram_section(self, content, placeholder):
        """
        Create an anagram section in the content at the relevant language section
        :param content: page content
        :param placeholder: gibberish string to be replaced later
        :return:
        """
        lines = content.split("\n")
        in_language = False
        inserted = False
        anagram_section = "{{-anagr-}}\n*" + placeholder + "{{anag+}}"

        # case: language entry at beginning or middle of page
        for index, line in enumerate(lines):
            if inserted:
                continue
            if in_language:
                if self.language_regex.search(line) is not None:
                    lines.insert(index - 1, anagram_section)
                    inserted = True

            if "=%s=" % self.language_code in line:
                in_language = True

        # compile our page
        content = "\n".join(lines)

        # case: language at end of page
        if content.find("{{-anagr-}}") == -1:
            content += anagram_section

        return content

    def retrieve_old_content(self, content):
        old_content = ""
        anag_begin = content.find("{{-anagr-}}")
        if anag_begin != -1:
            anag_end = content.find("{{anag+}}", anag_begin)
            if anag_end != -1:
                old_content = content[anag_begin:anag_end]

        return old_content

    def run(self):
        self.populate_anagrams()
        f = open(self.line_filename, "w")
        for alphagram in self.anagrams:
            for _ in self.anagrams[alphagram]:
                line = (
                    alphagram
                    + ":"
                    + ",".join([page.title() for page in self.anagrams[alphagram]])
                    + "\n"
                )
                f.write(line)

        if self.begin:
            skip = True
        else:
            skip = False

        for alphagram in self.anagrams:
            if self.begin and self.begin.upper() == alphagram:
                print("Beginning work from alphagram %s" % alphagram)
                skip = False

            if skip:
                continue

            print(alphagram, len(self.anagrams[alphagram]))
            if len(self.anagrams[alphagram]) < 2:
                continue

            for page in self.anagrams[alphagram]:
                self.counter += 1
                original_content = content = page.get()

                new_content = "\n{{-anagr-}}\n*"
                for page2 in self.anagrams[alphagram]:
                    if page2.title() != page.title():
                        new_content += "[[%s]], " % page2.title()

                print(">>>>> ", page.title(), " <<<<<")
                new_content = new_content.strip(", ")

                # anagram section exists: replace section's old content
                old_content = self.retrieve_old_content(content)

                # anagram section does NOT exist
                if not old_content:
                    anag_begin = content.find("=={{=%s=}}==" % self.language_code)
                    if anag_begin == -1:
                        print("Language section not found")
                        continue

                    # Adding anagram section, additional checks
                    placeholder = str(random.randint(10**10, 10**13))
                    content = self.add_anagram_section(content, placeholder)
                    anag_begin = content.find("{{-anagr-}}")
                    assert anag_begin != -1
                    old_content = self.retrieve_old_content(content)
                    if placeholder not in old_content:
                        print("%s/%s" % (placeholder, old_content))
                        continue

                if not old_content or len(old_content.replace("\n", "")) == 0:
                    print("old_content is empty: %s" % old_content)
                    continue

                new_page_content = content.replace(old_content, new_content)
                if content == new_page_content:
                    print("no page change")
                    continue

                pywikibot.showDiff(original_content, new_page_content)
                page.put(new_page_content, "+anagrama amin'ny teny %s" % self.language)
                print("%s/%s" % (self.counter, self.pages_total))


if __name__ == "__main__":
    bot = AnagramsFinderBot()
    bot.run()
