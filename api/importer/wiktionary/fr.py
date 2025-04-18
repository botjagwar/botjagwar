import re

from api.importer.wiktionary import SubsectionImporter as BaseSubsectionImporter
from api.importer.wiktionary import use_wiktionary


class SubsectionImporter(BaseSubsectionImporter):
    def get_data(self, template_title, wikipage: str, language: str) -> list:
        return []


@use_wiktionary("fr")
class ListSubsectionImporter(SubsectionImporter):
    def get_data(self, template_title, content: str, language: str):
        subsection_data = SubsectionImporter.get_data(
            self, template_title, content, language
        )
        retrieved = []
        for subsection_item in subsection_data:
            if "*" in subsection_item:
                retrieved.extend(
                    item
                    for item in subsection_item.split("*")
                    if item.strip() != ""
                )
        return list(set(retrieved))


class SynonymImporter(ListSubsectionImporter):
    level = 5
    data_type = "synonym"
    section_name = "{{S|synonymes}}"


@use_wiktionary("fr")
class EtymologyImporter(SubsectionImporter):
    level = 3
    data_type = "etym/mg"
    numbered = True
    section_name = "{{S|étymologie}}"


@use_wiktionary("fr")
class ReferencesImporter(SubsectionImporter):
    level = 3
    data_type = "reference"
    section_name = "{{S|références}}"

    def get_data(self, template_title, wikipage: str, language: str):
        refs = super(ReferencesImporter, self).get_data(
            template_title, wikipage, language
        )
        refs_to_return = []
        returned_references = "".join(refs)
        for ref_line in returned_references.split("\n"):
            if ref_line == "":
                continue

            if ref_line.startswith("* "):
                refs_to_return.append(ref_line.lstrip("* "))
            else:
                refs_to_return.append(ref_line)

        return refs_to_return


class AlternativeFormsImporter(ListSubsectionImporter):
    level = 4
    data_type = "alternative_form"
    section_name = "{{S|variantes orthographiques}}"


class AntonymImporter(ListSubsectionImporter):
    level = 4
    data_type = "antonym"
    section_name = "{{S|antonymes}}"


class DerivedTermsImporter(ListSubsectionImporter):
    level = 4
    data_type = "derived"
    section_name = "{{S|dérivés}}"

    def get_data(self, template_title, content: str, language: str):
        subsection_data = SubsectionImporter.get_data(
            self, template_title, content, language
        )
        retrieved = []
        for subsection_item in subsection_data:
            # Simple list
            if "*" in subsection_item:
                for item in subsection_item.split("*"):
                    if "[[Thesaurus:" in item:
                        continue
                    if "{{l|" + language in item:
                        retrieved.extend(
                            iter(
                                re.findall(
                                    "{{l\\|" + language + "\\|([0-9A-Za-z- ]+)}}",
                                    item,
                                )
                            )
                        )
                    elif "[[" in item and "]]" in item:
                        retrieved.extend(iter(re.findall("\\[\\[([0-9A-Za-z- ]+)\\]\\]", item)))
            # List in a template
            for template_name in (
                [f"der{d}" for d in range(1, 5)]
                + ["der-bottom", "der-top", "der-top3"]
                + [f"der-mid{d}" for d in range(1, 5)]
                + [f"col{d}" for d in range(1, 6)]
            ):
                if ("{{" + template_name + "|" + language) in subsection_item:
                    for item in subsection_item.split("\n"):
                        if item.startswith("|"):
                            if "#" in item:
                                item = item[: item.find("#")]
                            if "}}" in item:
                                item = item.replace("}}", "")

                            item = item.lstrip("|")
                            retrieved.append(item.strip())
                        elif item == "}}":
                            break

        return list(set(retrieved))


class PronunciationImporter(SubsectionImporter):
    level = 3
    data_type = "pronunciation"
    section_name = "{{S|prononciation}}"


all_importers = [
    AlternativeFormsImporter,
    AntonymImporter,
    DerivedTermsImporter,
    PronunciationImporter,
    ReferencesImporter,
    EtymologyImporter,
    SynonymImporter,
]
