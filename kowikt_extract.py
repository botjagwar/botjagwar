import re

from api.model.word import Translation
from api.page_lister import get_pages_from_category

lang_rgx = "\\(([a-z]+)\\):"


def get_entries_from_content(title, content):
    start = False
    pos = "ana"
    for line in content.split("\n"):
        if "{{외국어|" in line:
            start = True
            continue

        if "=== 명사 ===" in line:
            pos = "ana"

        if start:
            if lang_found := re.findall(lang_rgx, line):
                words = line.split(":")[1]
                if not words:
                    continue

                for word in words.split(","):

                    if word.find("(") > 0:
                        word = word[: word.find("(")]
                    if word.find("|") > 0:
                        word = word[: word.find("|")]

                    word = word.replace("{{lang", "")
                    for char in "()[]":
                        word = word.replace(char, "")

                    if word := word.strip():
                        yield Translation(
                            word=word,
                            language=lang_found[0],
                            part_of_speech=pos,
                            definition=title,
                        )


def get_definitions_from_content(title, content):
    start = False
    pos = "ana"
    for line in content.split("\n"):
        if "=== 명사 ===" in line:
            pos = "ana"

        if line.startswith(":* "):
            word = title
            line = line.strip(":* ")
            line = line.replace("'", "")
            if word:
                yield Translation(
                    word=word, language="ko", part_of_speech=pos, definition=line
                )


def main():
    with open("user_data/ko-ko.csv", "a") as f:
        for page in get_pages_from_category("ko", "한국어 명사"):
            translations = list(get_definitions_from_content(page.title(), page.get()))
            for t in translations:
                s = "%s;%s;%s;%s;%s\n" % (
                    t.word,
                    t.language,
                    t.part_of_speech,
                    t.translation,
                    "ko",
                )
                print(s.strip("\n"))
                f.write(s)


if __name__ == "__main__":
    main()
