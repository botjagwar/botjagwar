# coding: utf8

import re

from api.model.word import Entry
from .base import WiktionaryProcessor
from .base import stripwikitext


class MGWiktionaryProcessor(WiktionaryProcessor):
    form_of_regex = r"\{\{\-([a-z]+\-[a-z]{3,7})\-\|([a-z]{2,3})\}\}"
    lemma_regex = r"\{\{\-([a-z]{3,7})\-\|([a-z]{2,3})\}\}"

    @property
    def language(self):
        return "mg"

    def __init__(self, test=False, verbose=False):
        super(MGWiktionaryProcessor, self).__init__(test=test, verbose=verbose)
        self.content = None

    def retrieve_translations(self):
        return []

    def get_all_entries(self, keep_native_entries=False, **kw):
        items = []
        if self.content is None:
            return []
        for regex in [self.form_of_regex, self.lemma_regex]:
            for pos, lang in re.findall(regex, self.content):
                pos = pos.strip()
                if pos.strip() in ("etim"):
                    continue
                # word DEFINITION Retrieving
                d1 = self.content.find("{{-%s-|%s}}" % (pos, lang)) + len(
                    "{{-%s-|%s}}" % (pos, lang)
                )
                if d2 := (
                    self.content.find("=={{=", d1) + 1
                    or self.content.find("== {{=", d1) + 1
                ):
                    definition = self.content[d1:d2]
                else:
                    definition = self.content[d1:]
                try:
                    definitions = definition.split("\n# ")[1:]
                except IndexError:
                    # print(" Hadisoana : Tsy nahitana famaritana")
                    continue

                entry_definition = []
                for definition in definitions:
                    if definition.find("\n") + 1:
                        definition = definition[: definition.find("\n")]
                        definition = re.sub(
                            "\\[\\[(.*)#(.*)\\|?\\]?\\]?", "\\1", definition
                        )
                    if definition := stripwikitext(definition):
                        entry_definition.append(definition)

                if entry_definition := [d for d in entry_definition if len(d) > 1]:
                    i = Entry(
                        entry=self.title,
                        part_of_speech=pos.strip(),
                        language=lang.strip(),
                        definitions=entry_definition,
                    )
                    items.append(i)
        # print("Nahitana dikanteny ", len(items) ", len(items))
        return items
