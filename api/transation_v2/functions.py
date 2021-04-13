import re

from api.parsers import templates_parser, TEMPLATE_TO_OBJECT
from api.parsers.inflection_template import ParserNotFoundError
from .types import TranslatedDefinition, UntranslatedDefinition

regexesrep = [
            (r'\{\{l\|en\|(.*)\}\}', '\\1'),
            (r'\{\{vern\|(.*)\}\}', '\\1'),
            (r"\[\[(.*)#(.*)\|?[.*]?\]?\]?", "\\1"),
            (r"\{\{(.*)\}\}", ""),
            (r'\[\[(.*)\|(.*)\]\]', '\\1'),
            (r"\((.*)\)", "")]


def translate_form_of_templates(
      part_of_speech, definition_line,
      source_language, target_language) -> [UntranslatedDefinition, TranslatedDefinition]:
    new_definition_line = definition_line

    # Clean up non-needed template to improve readability.
    # In case these templates are needed, integrate your code above this part.
    for regex, replacement in regexesrep:
        new_definition_line = re.sub(regex, replacement, new_definition_line)

    # Form-of definitions: they use templates that can be parsed using api.parsers module
    #   which is tentatively being integrated here to provide human-readable output for
    #   either English or Malagasy
    if new_definition_line == '':
        try:
            if part_of_speech in TEMPLATE_TO_OBJECT:
                elements = templates_parser.get_elements(TEMPLATE_TO_OBJECT[part_of_speech], definition_line)
                new_definition_line = TranslatedDefinition(elements.to_definition(target_language))
        except ParserNotFoundError:
            new_definition_line = UntranslatedDefinition(definition_line)

    # print(definition_line, new_definition_line)
    return new_definition_line


def translate_using_dictionary(
      part_of_speech, definition_line,
      source_language, target_language) -> [UntranslatedDefinition, TranslatedDefinition]:
    pass


def translate_using_nltk(
      part_of_speech, definition_line,
      source_language, target_language) -> [UntranslatedDefinition, TranslatedDefinition]:
    pass


def translate_using_bridge_language(
      part_of_speech, definition_line,
      source_language, target_language) -> [UntranslatedDefinition, TranslatedDefinition]:
    pass


