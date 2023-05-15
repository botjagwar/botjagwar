import re
from logging import getLogger

from api.parsers import definitions_parser, templates_parser, TEMPLATE_TO_OBJECT
from api.parsers.functions.postprocessors import POST_PROCESSORS
from api.parsers.inflection_template import ParserNotFoundError
from api.servicemanager.nllb import NllbDefinitionTranslation
from api.servicemanager.openmt import OpenMtTranslation
from api.servicemanager.pgrest import JsonDictionary, ConvergentTranslations
from .utils import MAX_DEPTH
from .utils import regexesrep, \
    _delink, \
    form_of_part_of_speech_mapper
from ..exceptions import UnhandledTypeError, UnsupportedLanguageError
from ..types import TranslatedDefinition, \
    UntranslatedDefinition, FormOfTranslaton, ConvergentTranslation

json_dictionary = JsonDictionary(use_materialised_view=False)
convergent_translations = ConvergentTranslations()
log = getLogger(__file__)


def _translate_using_bridge_language(part_of_speech, definition_line, source_language, target_language, ct_depth=0,
                                     **kw) -> dict:
    if ct_depth >= MAX_DEPTH:
        return {}

    # query db
    log.debug(
        f'(bridge) {definition_line} ({part_of_speech}) [{source_language} -> {target_language}]',
    )
    data = json_dictionary.look_up_dictionary(
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


def translate_form_of_definitions(part_of_speech, definition_line, source_language, target_language,
                                  **kw) -> [UntranslatedDefinition, TranslatedDefinition]:
    new_definition_line = definition_line

    # Preventing translation of non-verb form definitions
    if not part_of_speech.startswith('e-'):
        return UntranslatedDefinition(definition_line)

    if part_of_speech in TEMPLATE_TO_OBJECT:
        try:
            elements = definitions_parser.get_elements(
                TEMPLATE_TO_OBJECT[part_of_speech], definition_line)
        except ParserNotFoundError:
            return UntranslatedDefinition(definition_line)

        if 'language' in kw:
            if kw['language'] in POST_PROCESSORS:
                elements = POST_PROCESSORS[kw['language']](elements)

        new_definition_line = FormOfTranslaton(elements.to_definition(target_language))
        if hasattr(elements, 'lemma'):
            setattr(new_definition_line, 'lemma', elements.lemma)

        if part_of_speech in form_of_part_of_speech_mapper:
            new_definition_line.part_of_speech = form_of_part_of_speech_mapper[
                part_of_speech]
        else:
            new_definition_line.part_of_speech = part_of_speech

    return new_definition_line


def translate_form_of_templates(part_of_speech, definition_line, source_language, target_language,
                                **kw) -> [UntranslatedDefinition, TranslatedDefinition]:
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

                new_definition_line = FormOfTranslaton(elements.to_definition(target_language))
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
def translate_using_postgrest_json_dictionary(part_of_speech, definition_line, source_language, target_language,
                                              back_check_pos=False, **kw) \
    -> [UntranslatedDefinition, TranslatedDefinition]:
    if definition_line.endswith('.'):
        definition_line = definition_line.strip('.')

    data = json_dictionary.look_up_dictionary(
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
                data = json_dictionary.look_up_word(
                    target_language, part_of_speech, translation)
                if data:
                    checked_translations.append(translation)

            translations = checked_translations

        # finalize
        t_string = ', '.join(translations)
        log.debug(
            f'{definition_line} ({part_of_speech}) [{source_language} -> {target_language}]: {t_string}')
        return TranslatedDefinition(t_string)

    return UntranslatedDefinition(definition_line)


def translate_using_suggested_translations_fr_mg(part_of_speech, definition_line, source_language, target_language,
                                                 **kw) -> [UntranslatedDefinition, ConvergentTranslation]:
    convergent_translations = ConvergentTranslations()
    if source_language == 'fr':
        translations = convergent_translations.get_suggested_translations_fr_mg(
            target_language, part_of_speech=part_of_speech, definition=definition_line)
    else:
        raise UnsupportedLanguageError(f"Source language '{source_language}' "
                                       f"cannot be used for convergent translations")

    if translations:
        ret_translations = [t['suggested_definition'] for t in translations]
        if ret_translations:
            k = ', '.join(sorted(list(set(ret_translations))))
            return ConvergentTranslation(k)

    return UntranslatedDefinition(definition_line)


def translate_using_convergent_definition(part_of_speech, definition_line, source_language, target_language,
                                          **kw) -> [UntranslatedDefinition, ConvergentTranslation]:
    if source_language == 'en':
        translations = convergent_translations.get_convergent_translation(
            target_language, part_of_speech=part_of_speech, en_definition=definition_line)
    elif source_language == 'fr':
        translations = convergent_translations.get_convergent_translation(
            target_language, part_of_speech=part_of_speech, fr_definition=definition_line)
    else:
        raise UnsupportedLanguageError(f"Source language '{source_language}' "
                                       f"cannot be used for convergent translations")

    ret_translations = [t['suggested_definition'] for t in translations]
    print(ret_translations)
    if ret_translations:
        k = ', '.join(sorted(list(set(ret_translations))))
        return ConvergentTranslation(k)

    return UntranslatedDefinition(definition_line)


def translate_using_bridge_language(part_of_speech, definition_line, source_language, target_language,
                                    **kw) -> [UntranslatedDefinition, TranslatedDefinition]:
    translations = _translate_using_bridge_language(
        part_of_speech, definition_line, source_language, target_language, **kw
    )
    log.debug(translations)

    if translations.keys():
        k = ', '.join(sorted(list(set(translations))))
        return TranslatedDefinition(k)

    return UntranslatedDefinition(definition_line)


def translate_using_nltk(part_of_speech, definition_line, source_language, target_language,
                         **kw) -> [UntranslatedDefinition, TranslatedDefinition]:
    pass


def translate_using_opus_mt(part_of_speech, definition_line, source_language, target_language,
                            **kw) -> [UntranslatedDefinition, TranslatedDefinition]:
    helper = OpenMtTranslation(source_language, target_language)
    data = helper.get_translation(definition_line)
    if data is not None:
        return TranslatedDefinition(data)

    return UntranslatedDefinition(definition_line)


def translate_using_nllb(part_of_speech, definition_line, source_language, target_language,
                         **kw) -> [UntranslatedDefinition, TranslatedDefinition]:
    helper = NllbDefinitionTranslation(source_language, target_language)

    # Implementation of various tricks to improve the translation quality
    # provided by NLLB on one-word translation sometimes given as definition
    definition_line = definition_line[:3].lower() + definition_line[3:].strip('.')
    if part_of_speech.startswith('e-'):
        print("NLLB should not translate form words.")
        return UntranslatedDefinition(definition_line)

    # Restrict to short definition, as longer definitions seems to be doing just fine (for now)
    if len(definition_line.split()) <= 10:
        # Add "it is (a/an)" before the definition if it is a noun
        if part_of_speech == 'ana':
            if source_language == 'en':
                enriched = True
                prefix = 'it is '
                if not definition_line.lower().startswith('a ') or not definition_line.lower().startswith('an '):
                    prefix += 'a '
                definition_line = prefix + definition_line
            elif source_language == 'fr':
                prefix = 'c\'est'
                if not definition_line.lower().startswith('un ') or not definition_line.lower().startswith('une '):
                    prefix += ' une '
                definition_line = prefix + definition_line + '.'

        elif part_of_speech == 'mat':
            if definition_line.endswith(' à'):
                definition_line += " quelqu'un ou quelque chose"

        # Another trick when it is an adjective
        elif part_of_speech == 'mpam':
            if source_language == 'en':
                prefix = 'something that is '
                definition_line = prefix + definition_line
            elif source_language == 'fr':
                definition_line = 'quelque chose de ' + definition_line

    # Specific case for verbs. use a form like "He is able to X" to force X being
    # an impersonal verb in Malagasy. Put the translation in the active voice, where that is possible.
    if len(definition_line.split()) <= 10:
        if part_of_speech == 'mat':
            if source_language == 'en':
                prefix = 'he is able '
                if not definition_line.startswith('to '):
                    prefix += ' to '

                definition_line = re.sub("\([a-zA-Z\ \,\;]+\)", '', definition_line)
                definition_line = definition_line.strip('.').strip()
                if definition_line.endswith(' of'):
                    definition_line += ' someone or something'

                translation = helper.get_translation(prefix + definition_line + '.')
            elif source_language == 'fr':
                translation = helper.get_translation('il est capable de ' + definition_line + '.')
            else:
                translation = helper.get_translation(definition_line)

            if translation.lower().startswith('afaka '):
                translation = translation.lower().strip('afaka').strip('izy.')
            if translation.lower().startswith('mahay '):
                translation = translation.lower().strip('mahay').strip('izy.')
            if translation.lower().endswith(' azy.'):
                translation = translation.lower().strip('azy.')
            if translation.lower().endswith(' izy.'):
                translation = translation.lower().strip('izy.')
            if translation.lower().endswith(' azy'):
                translation = translation.lower().strip('azy.')
            if translation.lower().endswith(' izany.'):
                translation = translation.lower().strip('izany.')
            if translation.lower().endswith(' izao.'):
                translation = translation.lower().strip('izao.')
            # if enriched and unexpected_format:
            #     translation = helper.get_translation(definition_line)
        else:
            translation = helper.get_translation(definition_line)
    else:
        translation = helper.get_translation(definition_line)

    # Remove all translation artefacts that could have been generated by the tricks performed above.
    if part_of_speech in ('ana', 'mat'):
        if translation.lower().startswith('afaka '):
            translation = translation.replace('afaka ', '')

        if translation.lower().startswith('dia '):
            translation = translation.replace('dia ', '')

        for word in 'izany izao izy io iny'.split():
            if f' {word}' in translation.lower():
                translation = translation.replace(f' {word}', '').strip()
            if f' {word}.' in translation.lower():
                translation = translation.replace(f' {word}.', '').strip()

        if translation.startswith('io dia '):
            translation = translation.replace('io dia ', '')

        if translation.lower().endswith(' izao'):
            translation = translation.lower().replace('izao', '')

    translation = translation.strip('.')
    data = translation
    for character in ',;':
        data_as_list = data.split(character)
        out_data = []
        for d in data_as_list:
            d = d.strip()
            if d not in out_data:
                out_data.append(d)

        data = f'{character} '.join(out_data)

    print(data_as_list)
    if len(data) > len(definition_line) * 3:
        return UntranslatedDefinition(definition_line)

    if data is not None:
        return TranslatedDefinition(data)

    return UntranslatedDefinition(definition_line)
