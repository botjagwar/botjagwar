# coding: utf8

import mwparserfromhell

from api.model.word import Entry

from .base import WiktionaryProcessor


class VOWiktionaryProcessor(WiktionaryProcessor):
    """Extract entries from Volapük Wiktionary word templates."""

    @property
    def language(self) -> str:
        return "vo"

    def get_WW_definition(self) -> str:
        """Return the direct dictionary definition from the word template."""

        return self._get_param_in_temp("Samafomot:VpVöd", "WW")

    def _get_param_in_temp(self, template_name: str, parameter_name: str) -> str:
        """Read a parameter from raw content without requiring a live Page."""

        expected_name = template_name.replace("_", " ").strip().casefold()
        expected_basename = expected_name.rsplit(":", 1)[-1]
        for template in mwparserfromhell.parse(self.content or "").filter_templates(
            recursive=True
        ):
            actual_name = str(template.name).replace("_", " ").strip().casefold()
            if actual_name.rsplit(":", 1)[-1] != expected_basename:
                continue
            for parameter in template.params:
                if str(parameter.name).strip().casefold() == parameter_name.casefold():
                    return str(parameter.value).strip()
        return ""

    def get_all_entries(
        self, keep_native_entries: bool = False, **kw: object
    ) -> list[Entry]:
        """Return the entry encoded by the page's ``VpVöd`` template."""

        del keep_native_entries, kw
        pos_translations = {"värb": "mat", "subsat": "ana", "ladyek": "mpam-ana"}
        pos = self._get_param_in_temp("Samafomot:VpVöd", "klad")
        definition = self.get_WW_definition()
        if not pos or not definition:
            return []
        return [
            Entry(
                entry=self.title or "",
                part_of_speech=pos_translations.get(pos.casefold(), pos),
                language="vo",
                definitions=[definition],
            )
        ]

    def retrieve_translations(self) -> list[object]:
        """Volapük translation extraction is not implemented."""

        return []
