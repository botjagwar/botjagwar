# coding: utf8

import re

from api.model.word import Entry
from .base import WiktionaryProcessor
from .base import stripwikitext


class MGWiktionaryProcessor(WiktionaryProcessor):
    language_regex = r"([a-z][a-z0-9-]*)"
    form_of_regex = rf"\{{\{{\-([a-z]+(?:\-[a-z]+)+)\-\|{language_regex}\}}\}}"
    lemma_regex = rf"\{{\{{\-([a-z]+)\-\|{language_regex}\}}\}}"
    entry_regex = re.compile(rf"(?:{form_of_regex}|{lemma_regex})", re.IGNORECASE)

    @property
    def language(self):
        return "mg"

    def __init__(self, test=False, verbose=False):
        super(MGWiktionaryProcessor, self).__init__(test=test, verbose=verbose)
        self.content = None

    def retrieve_translations(self):
        return []

    def get_all_entries(
        self, keep_native_entries: bool = False, **kw: object
    ) -> list[Entry]:
        items = []
        if self.content is None:
            return []
        matches = list(self.entry_regex.finditer(self.content))
        for index, match in enumerate(matches):
            pos, lang = next(
                (match.group(group), match.group(group + 1))
                for group in (1, 3)
                if match.group(group) is not None
            )
            if pos == "etim":
                continue
            block_end = (
                matches[index + 1].start()
                if index + 1 < len(matches)
                else len(self.content)
            )
            definition_block = self.content[match.end():block_end]
            entry_definition = []
            for definition in definition_block.split("\n# ")[1:]:
                definition = definition.split("\n", 1)[0]
                definition = re.sub(
                    "\\[\\[(.*)#(.*)\\|?\\]?\\]?", "\\1", definition
                )
                if definition := stripwikitext(definition):
                    entry_definition.append(definition)

            if entry_definition := [d for d in entry_definition if len(d) > 1]:
                items.append(
                    Entry(
                        entry=self.title,
                        part_of_speech=pos,
                        language=lang,
                        definitions=entry_definition,
                    )
                )
        # print("Nahitana dikanteny ", len(items) ", len(items))
        return items
