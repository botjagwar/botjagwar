 \
import re
from logging import getLogger

import requests

from api.decorator import time_this
from api.parsers import templates_parser, TEMPLATE_TO_OBJECT
from api.parsers.inflection_template import ParserNotFoundError
from api.servicemanager.pgrest import StaticBackend
from .types import TranslatedDefinition, \
    UntranslatedDefinition \
 \
regexesrep = [
    (r'\{\{l\|en\|(.*)\}\}', '\\1'),
    (r'\{\{vern\|(.*)\}\}', '\\1'),
    (r"\[\[(.*)#(.*)\|?[.*]?\]?\]?", "\\1"),
    (r"\{\{(.*)\}\}", ""),
    (r'\[\[(.*)\|(.*)\]\]', '\\1'),
    (r"\((.*)\)", "")
]
backend = StaticBackend()
log = getLogger(__file__)


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


def _look_up_word(language, part_of_speech, word):
    params = {
        'language': 'eq.' + language,
        'part_of_speech': 'eq.' + part_of_speech,
        'word': 'eq.' + word
    }
    print(params)
    resp = requests.get(backend.backend + '/word', params=params)
    data = resp.json()
    return data


def _translate_using_bridge_language(part_of_speech, definition_line, source_language, target_language, **kw)\
      -> dict:
    # query db
    print(f'(bridge) {definition_line} ({part_of_speech}) [{source_language} -> {target_language}]',)
    data = _look_up_dictionary(source_language, part_of_speech, _delink(definition_line))
    if not data:
        return {}

    translations = {}
    # lookup translation using definition
    for entry in data:
        for definition in entry['definitions']:
            defn_language = definition['language']
            if defn_language == target_language:
                if definition['definition'] in translations:
                    translations[definition['definition']].append(definition['language'])
                else:
                    translations[definition['definition']] = [definition['language']]

                print(f"Translated {definition_line} --> {definition['definition']}")
            else:
                print(f"(bridge) --> {definition['definition']} [{definition['language']}]")
                translation = translate_using_postgrest_json_dictionary(
                    part_of_speech, definition['definition'], definition['language'],
                    target_language, back_check_pos=False
                )

                if isinstance(translation, TranslatedDefinition):
                    for w in translation.split(','):
                        w = w.strip()
                        if w in translations:
                            translations[w].append(definition['language'])
                        else:
                            translations[w] = [definition['language']]
                elif isinstance(translation, UntranslatedDefinition):
                    translation = _translate_using_bridge_language(
                        part_of_speech=part_of_speech,
                        definition_line=definition['definition'],
                        source_language=definition['language'],
                        target_language=target_language
                    )

                    if translation.keys():
                        for w in translation:
                            w = w.strip()
                            if w in translations:
                                translations[w].append(definition['language'])
                            else:
                                translations[w] = [definition['language']]
                else:
                    raise TypeError()

    return translations


def translate_form_of_templates(part_of_speech, definition_line, source_language, target_language, **kw)\
      -> [UntranslatedDefinition, TranslatedDefinition]:

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
    part_of_speech, definition_line, source_language, target_language,
    back_check_pos=False, **kw)\
      -> [UntranslatedDefinition, TranslatedDefinition]:

    data = _look_up_dictionary(source_language, part_of_speech, _delink(definition_line))
    if not data:
        return UntranslatedDefinition(definition_line)

    translations = []
    # lookup translation using definition
    for entry in data:
        for definition in entry['definitions']:
            if definition['language'] == target_language:
                translations.append(TranslatedDefinition(definition['definition']))
                log.info(f"Translated {definition_line} --> {definition['definition']}")

        # lookup translation using main word
        for definition in entry['definitions']:
            print(definition['definition'], f"[{definition['language']}]")

    if translations:
        # back-check for part of speech.
        if back_check_pos:
            checked_translations = []
            for translation in translations:
                data = _look_up_word(target_language, part_of_speech, translation)
                if data:
                    checked_translations.append(translation)

            translations = checked_translations

        # finalize
        t_string = ', '.join(translations)
        print(f'{definition_line} ({part_of_speech}) [{source_language} -> {target_language}]: {t_string}')
        return TranslatedDefinition(t_string)
    else:
        return UntranslatedDefinition(definition_line)


def translate_using_convergent_definition(part_of_speech, definition_line, source_language, target_language, **kw) \
      -> [UntranslatedDefinition, TranslatedDefinition]:
    translations = _translate_using_bridge_language(
         part_of_speech, definition_line, source_language, target_language, **kw
    )
    ret_translations = []
    for translation, languages in translations.items():
        if len(languages) > 1:
            ret_translations.append(translation)

    if ret_translations:
        k = ', '.join(sorted(list(set(ret_translations))))
        return TranslatedDefinition(k)
    else:
        return UntranslatedDefinition(definition_line)


@time_this('translate_using_bridge_language')
def translate_using_bridge_language(part_of_speech, definition_line, source_language, target_language, **kw) \
      -> [UntranslatedDefinition, TranslatedDefinition]:
    translations = _translate_using_bridge_language(
        part_of_speech, definition_line, source_language, target_language, **kw
    )
    print(translations)

    if translations.keys():
        k = ', '.join(sorted(list(set(translations))))
        return TranslatedDefinition(k)
    else:
        return UntranslatedDefinition(definition_line)


def translate_using_nltk(part_of_speech, definition_line, source_language, target_language, **kw) \
      -> [UntranslatedDefinition, TranslatedDefinition]:
    pass

