import re

import requests

from api.decorator import time_this
from api.parsers import templates_parser, TEMPLATE_TO_OBJECT
from api.parsers.inflection_template import ParserNotFoundError
from api.servicemanager.pgrest import StaticBackend
from .types import TranslatedDefinition, UntranslatedDefinition

regexesrep = [
    (r'\{\{l\|en\|(.*)\}\}', '\\1'),
    (r'\{\{vern\|(.*)\}\}', '\\1'),
    (r"\[\[(.*)#(.*)\|?[.*]?\]?\]?", "\\1"),
    (r"\{\{(.*)\}\}", ""),
    (r'\[\[(.*)\|(.*)\]\]', '\\1'),
    (r"\((.*)\)", "")
]

backend = StaticBackend()


def _delink(line):
    # change link e.g. [[xyz|XYZ#en]] --> xyz
    for link, link_name in re.findall('\[\[(\w+)\|(\w+)\]\]', line):
        line = line.replace(f'[[{link}|{link_name}]]', link)

    # remove remaining wiki markup
    for c in '{}[]':
        line = line.replace(c, '')

    return line


def _look_up_dictionary(w_language, w_part_of_speech, w_word):
    params = {
        'language': 'eq.' + w_language,
        'part_of_speech': 'eq.' + w_part_of_speech,
        'word': 'eq.' + w_word
    }
    resp = requests.get(backend.backend + '/vw_json_dictionary', params=params)
    data = resp.json()
    return data


def translate_form_of_templates(
      part_of_speech, definition_line,
      source_language, target_language,
      **kw
      ) -> [UntranslatedDefinition, TranslatedDefinition]:

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

    return new_definition_line


@time_this('translate_using_postgrest_json_dictionary')
def translate_using_postgrest_json_dictionary(
      part_of_speech, definition_line,
      source_language, target_language,
      use_synonyms=True,
      **kw
      ) -> [UntranslatedDefinition, TranslatedDefinition]:

    data = _look_up_dictionary(source_language, part_of_speech, _delink(definition_line))
    if not data:
        return UntranslatedDefinition(definition_line)

    translations = []

    # lookup translation using definition
    for entry in data:
        for definition in entry['definitions']:
            if definition['language'] == target_language:
                translations.append(definition['definition'])

    # lookup translation using synonyms, if any
        if use_synonyms and entry['additional_data']:
            for additional_data in entry['additional_data']:
                if additional_data['data_type'] == 'synonym':
                    synonym = additional_data['data']

    if translations:
        return TranslatedDefinition(','.join(translations))
    else:
        return UntranslatedDefinition(definition_line)


def translate_using_nltk(part_of_speech, definition_line, source_language, target_language, **kw) -> [UntranslatedDefinition, TranslatedDefinition]:
    pass


def translate_using_bridge_language(part_of_speech, definition_line, source_language, target_language, **kw) -> [UntranslatedDefinition, TranslatedDefinition]:
    pass



