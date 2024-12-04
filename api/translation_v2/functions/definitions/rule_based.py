import re

from api.parsers import definitions_parser, templates_parser, TEMPLATE_TO_OBJECT
from api.parsers.functions.postprocessors import POST_PROCESSORS
from api.parsers.inflection_template import ParserNotFoundError
from api.translation_v2.functions.utils import regexesrep, form_of_part_of_speech_mapper
from api.translation_v2.types import (
    TranslatedDefinition,
    UntranslatedDefinition,
    FormOfTranslaton,
)


def translate_form_of_definitions(
    part_of_speech, definition_line, source_language, target_language, **kw
) -> [UntranslatedDefinition, TranslatedDefinition]:
    new_definition_line = definition_line

    # Preventing translation of non-verb form definitions
    if not part_of_speech.startswith("e-"):
        return UntranslatedDefinition(definition_line)

    if part_of_speech in TEMPLATE_TO_OBJECT:
        try:
            elements = definitions_parser.get_elements(
                TEMPLATE_TO_OBJECT[part_of_speech], definition_line
            )
        except ParserNotFoundError:
            return UntranslatedDefinition(definition_line)

        if "language" in kw:
            if kw["language"] in POST_PROCESSORS:
                elements = POST_PROCESSORS[kw["language"]](elements)

        new_definition_line = FormOfTranslaton(elements.to_definition(target_language))
        if hasattr(elements, "lemma"):
            setattr(new_definition_line, "lemma", elements.lemma)

        if part_of_speech in form_of_part_of_speech_mapper:
            new_definition_line.part_of_speech = form_of_part_of_speech_mapper[
                part_of_speech
            ]
        else:
            new_definition_line.part_of_speech = part_of_speech

    return new_definition_line


def translate_form_of_templates(
    part_of_speech, definition_line, source_language, target_language, **kw
) -> [UntranslatedDefinition, TranslatedDefinition]:
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
            if part_of_speech in TEMPLATE_TO_OBJECT:
                elements = templates_parser.get_elements(
                    TEMPLATE_TO_OBJECT[part_of_speech], definition_line
                )
                if "language" in kw:
                    if kw["language"] in POST_PROCESSORS:
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


__all__ = ["translate_form_of_templates", "translate_form_of_definitions"]
