import re
from logging import getLogger

import requests

from api.parsers import templates_parser, TEMPLATE_TO_OBJECT
from api.parsers.functions.postprocessors import POST_PROCESSORS
from api.parsers.inflection_template import ParserNotFoundError
from api.servicemanager.pgrest import StaticBackend
from .exceptions import UnhandledTypeError
from .types import TranslatedDefinition, \
    UntranslatedDefinition

regexesrep = [
    (r'\{\{l\|en\|(.*)\}\}', '\\1'),
    (r'\{\{vern\|(.*)\}\}', '\\1'),
    (r"\[\[(.*)#(.*)\|?[.*]?\]?\]?", "\\1"),
    (r"\{\{(.*)\}\}", ""),
    (r'\[\[(.*)\|(.*)\]\]', '\\1'),
    (r"\((.*)\)", "")
]
CYRILLIC_ALPHABET_LANGUAGES = 'be,bg,mk,ru,uk'.split(',')
MAX_DEPTH = 5
form_of_part_of_speech_mapper = {
    'ana': 'e-ana',
    'mat': 'e-mat',
    'mpam-ana': 'e-mpam-ana',
    'mpam': 'e-mpam',
}

backend = StaticBackend()
log = getLogger(__file__)


def _get_unaccented_word(word):
    for char in "́̀":
        if word.find(char) != -1:
            word = word.replace(char, "")
    return word


def _delink(line):
    # change link e.g. [[xyz|XYZ#en]] --> xyz
    for link, link_name in re.findall('\\[\\[(\\w+)\\|(\\w+)\\]\\]', line):
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
    resp = requests.get(backend.backend + '/json_dictionary', params=params)
    data = resp.json()
    return data


def _look_up_word(language, part_of_speech, word):
    params = {
        'language': 'eq.' + language,
        'part_of_speech': 'eq.' + part_of_speech,
        'word': 'eq.' + word
    }
    log.debug(params)
    resp = requests.get(backend.backend + '/word', params=params)
    data = resp.json()
    return data


def _generate_redirections(infos):
    redirection_target = infos.entry
    if infos.language in CYRILLIC_ALPHABET_LANGUAGES:
        for char in "́̀":
            if redirection_target.find(char) != -1:
                redirection_target = redirection_target.replace(char, "")
        if redirection_target.find("æ") != -1:
            redirection_target = redirection_target.replace("æ", "ӕ")
        if infos.entry != redirection_target:
            # page = pwbot.Page(pwbot.Site(WORKING_WIKI_LANGUAGE, 'wiktionary'), infos.entry)
            # if not page.exists():
            # page.put_async("#FIHODINANA [[%s]]" % redirection_target,
            # "fihodinana")
            infos.entry = redirection_target


def _translate_using_bridge_language(
        part_of_speech,
        definition_line,
        source_language,
        target_language,
        ct_depth=0,
        **kw) -> dict:
    if ct_depth >= MAX_DEPTH:
        return {}

    # query db
    log.debug(
        f'(bridge) {definition_line} ({part_of_speech}) [{source_language} -> {target_language}]',
    )
    data = _look_up_dictionary(
        source_language,
        part_of_speech,
        _delink(definition_line))
    if not data:
        return {}

    translations = {}
    # lookup translation using definition
    for entry in data:
        for definition in entry['definitions']:
            defn_language = definition['language']
            if defn_language == target_language:
                if definition['definition'] in translations:
                    translations[definition['definition']].append(
                        definition['language'])
                else:
                    translations[definition['definition']] = [
                        definition['language']]

                log.debug(
                    f"Translated {definition_line} --> {definition['definition']}")
            else:
                log.debug(
                    f"(bridge) --> {definition['definition']} [{definition['language']}]")
                translation = translate_using_postgrest_json_dictionary(
                    part_of_speech,
                    definition['definition'],
                    definition['language'],
                    target_language,
                    back_check_pos=False)

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
                        target_language=target_language,
                        ct_depth=ct_depth + 1
                    )

                    if translation.keys():
                        for w in translation:
                            w = w.strip()
                            if w in translations:
                                translations[w].append(definition['language'])
                            else:
                                translations[w] = [definition['language']]
                else:
                    raise UnhandledTypeError(
                        f"{translations.__class__.__name__}")

    return translations


def translate_form_of_templates(part_of_speech,
                                definition_line,
                                source_language,
                                target_language,
                                **kw) -> [UntranslatedDefinition,
                                          TranslatedDefinition]:

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
                elements = templates_parser.get_elements(
                    TEMPLATE_TO_OBJECT[part_of_speech], definition_line)
                if 'language' in kw:
                    if kw['language'] in POST_PROCESSORS:
                        elements = POST_PROCESSORS[kw['language']](elements)
                new_definition_line = TranslatedDefinition(
                    elements.to_definition(target_language))
                if hasattr(elements, 'lemma'):
                    setattr(new_definition_line, 'lemma', elements.lemma)
                if part_of_speech in form_of_part_of_speech_mapper:
                    new_definition_line.part_of_speech = form_of_part_of_speech_mapper[
                        part_of_speech]
                else:
                    new_definition_line.part_of_speech = part_of_speech
        except ParserNotFoundError:
            new_definition_line = UntranslatedDefinition(definition_line)

    return new_definition_line


# @time_this('translate_using_postgrest_json_dictionary')
def translate_using_postgrest_json_dictionary(
        part_of_speech, definition_line, source_language, target_language,
        back_check_pos=False, **kw)\
        -> [UntranslatedDefinition, TranslatedDefinition]:

    data = _look_up_dictionary(
        source_language,
        part_of_speech,
        _delink(definition_line))
    if not data:
        return UntranslatedDefinition(definition_line)

    translations = []
    # lookup translation using definition
    for entry in data:
        for definition in entry['definitions']:
            if definition['language'] == target_language:
                translations.append(
                    TranslatedDefinition(
                        definition['definition']))
                log.info(
                    f"Translated {definition_line} --> {definition['definition']}")

        # lookup translation using main word
        for definition in entry['definitions']:
            log.debug(
                definition['definition'] +
                f" [{definition['language']}]")

    if translations:
        # back-check for part of speech.
        if back_check_pos:
            checked_translations = []
            for translation in translations:
                data = _look_up_word(
                    target_language, part_of_speech, translation)
                if data:
                    checked_translations.append(translation)

            translations = checked_translations

        # finalize
        t_string = ', '.join(translations)
        log.debug(
            f'{definition_line} ({part_of_speech}) [{source_language} -> {target_language}]: {t_string}')
        return TranslatedDefinition(t_string)
    else:
        return UntranslatedDefinition(definition_line)


def translate_using_convergent_definition(
        part_of_speech,
        definition_line,
        source_language,
        target_language,
        **kw) -> [
            UntranslatedDefinition,
        TranslatedDefinition]:
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


def translate_using_bridge_language(part_of_speech,
                                    definition_line,
                                    source_language,
                                    target_language,
                                    **kw) -> [UntranslatedDefinition,
                                              TranslatedDefinition]:
    translations = _translate_using_bridge_language(
        part_of_speech, definition_line, source_language, target_language, **kw
    )
    log.debug(translations)

    if translations.keys():
        k = ', '.join(sorted(list(set(translations))))
        return TranslatedDefinition(k)
    else:
        return UntranslatedDefinition(definition_line)


def translate_using_nltk(part_of_speech,
                         definition_line,
                         source_language,
                         target_language,
                         **kw) -> [UntranslatedDefinition,
                                   TranslatedDefinition]:
    pass
