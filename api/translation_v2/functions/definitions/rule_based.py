import re

from api.parsers.en import definitions_parser as en_definitions_parser
from api.parsers.en import TEMPLATE_TO_OBJECT as EN_TEMPLATE_TO_OBJECT
from api.parsers.en import templates_parser as en_templates_parser

from api.parsers.fr import templates_parser as fr_templates_parser
from api.parsers.fr import fr_definitions_parser
from api.parsers.fr import TEMPLATE_TO_OBJECT as FR_TEMPLATE_TO_OBJECT

from api.parsers.functions.postprocessors import POST_PROCESSORS
from api.parsers.inflection_template import ParserNotFoundError
from api.translation_v2.functions.utils import regexesrep, form_of_part_of_speech_mapper
from api.translation_v2.types import (
    Definition,
    TranslatedDefinition,
    UntranslatedDefinition,
    FormOfTranslaton,
)

POS_WHITELIST = [
    "e-ana",
    "e-mpam-ana",
    "e-mat",

    # enwikt section names
    "mat",
    "ana",
    "mpam",
    "ova-mat",
]

class FormOfDefinitionTranslatorFactory:
    def __init__(self, wiktionary_language):
        self.wiktionary_language = wiktionary_language
        self.template_to_object = {
            'en': EN_TEMPLATE_TO_OBJECT,
            'fr': FR_TEMPLATE_TO_OBJECT,
        }
        self.definition_parser = {
            'en': en_definitions_parser,
            'fr': fr_definitions_parser,
        }
        self.templates_parser = {
            'en': en_templates_parser,
            'fr': fr_templates_parser,
        }



    def translate_form_of_definitions(
            self, entry, definition_line, source_language, target_language, **kw
    ) -> Definition:
        new_definition_line = definition_line
        part_of_speech = entry.part_of_speech

        # Preventing translation of non-verb form definitions
        if part_of_speech not in POS_WHITELIST:
            return UntranslatedDefinition(definition_line)

        template_to_object = self.template_to_object.get(self.wiktionary_language, {})
        definitions_parser = self.definition_parser[self.wiktionary_language]
        templates_parser = self.templates_parser[self.wiktionary_language]

        if not template_to_object:
            return UntranslatedDefinition(definition_line)

        try:
            # it is a template-based definition
            if definition_line.startswith("{{") and definition_line.endswith("}}"):

                elements = templates_parser.get_elements(
                    template_to_object[part_of_speech], definition_line
                )
            # it is a definition containing a template
            else:
                elements = definitions_parser.get_elements(
                    template_to_object[part_of_speech], definition_line
                )

        except ParserNotFoundError:
            return UntranslatedDefinition(definition_line)

        if "language" in kw and kw["language"] in POST_PROCESSORS:
            elements = POST_PROCESSORS[kw["language"]](elements)

        new_definition_line = FormOfTranslaton(elements.to_definition(target_language))
        if not new_definition_line.is_valid():
            return UntranslatedDefinition(definition_line)

        if hasattr(elements, "lemma"):
            if elements.lemma == "":
                return UntranslatedDefinition(definition_line)
            setattr(new_definition_line, "lemma", elements.lemma)

        if part_of_speech in form_of_part_of_speech_mapper:
            new_definition_line.part_of_speech = form_of_part_of_speech_mapper[
                part_of_speech
            ]
        else:
            new_definition_line.part_of_speech = part_of_speech

        return new_definition_line


    def translate_form_of_templates(
            self, entry, definition_line, source_language, target_language, **kw
    ) -> Definition:
        part_of_speech = entry.part_of_speech
        new_definition_line = definition_line

        # Clean up non-needed template to improve readability.
        # In case these templates are needed, integrate your code above this part.
        for regex, replacement in regexesrep:
            new_definition_line = re.sub(regex, replacement, new_definition_line)

        # Form-of definitions: they use templates that can be parsed using api.parsers module
        #   which is tentatively being integrated here to provide human-readable output for
        #   either English or Malagasy
        if new_definition_line == "":
            try:
                if part_of_speech in self.template_to_object[self.wiktionary_language]:
                    elements = self.templates_parser[self.wiktionary_language].get_elements(
                        self.template_to_object[self.wiktionary_language][part_of_speech], definition_line, entry=entry
                    )
                    if "language" in kw and kw["language"] in POST_PROCESSORS:
                        elements = POST_PROCESSORS[kw["language"]](elements)

                    new_definition_line = FormOfTranslaton(
                        elements.to_definition(target_language)
                    )
                    if hasattr(elements, "lemma"):
                        setattr(new_definition_line, "lemma", elements.lemma)

                    if part_of_speech in form_of_part_of_speech_mapper:
                        new_definition_line.part_of_speech = form_of_part_of_speech_mapper[
                            part_of_speech
                        ]
                    else:
                        new_definition_line.part_of_speech = part_of_speech
            except ParserNotFoundError:
                new_definition_line = UntranslatedDefinition(definition_line)

        return new_definition_line


__all__ = ["FormOfDefinitionTranslatorFactory"]
