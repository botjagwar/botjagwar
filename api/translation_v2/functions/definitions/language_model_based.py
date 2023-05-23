import re
from logging import getLogger

from api.servicemanager.nllb import NllbDefinitionTranslation
from api.servicemanager.openmt import OpenMtTranslation
from api.servicemanager.pgrest import JsonDictionary, ConvergentTranslations
from api.translation_v2.types import TranslatedDefinition, \
    UntranslatedDefinition

json_dictionary = JsonDictionary(use_materialised_view=False)
convergent_translations = ConvergentTranslations()
log = getLogger(__file__)


def translate_using_nltk(part_of_speech, definition_line, source_language, target_language,
                         **kw) -> [UntranslatedDefinition, TranslatedDefinition]:
    pass


def translate_using_opus_mt(part_of_speech, definition_line, source_language, target_language,
                            **kw) -> [UntranslatedDefinition, TranslatedDefinition]:
    helper = OpenMtTranslation(source_language, target_language)
    data = helper.get_translation(definition_line)
    if data is not None:
        return TranslatedDefinition(data)


def enrich_english_definition(part_of_speech, definition_line):
    if part_of_speech == 'ana':
        prefix = 'it is '
        if not definition_line.lower().startswith('a ') and definition_line.lower()[0] not in 'aeioy':
            prefix += 'a '
        elif not definition_line.lower().startswith('an ') and definition_line.lower()[0] in 'aeioy':
            prefix += 'an '

        definition_line = prefix + definition_line

    # Another trick when it is an adjective
    elif part_of_speech == 'mpam':
        prefix = 'something that is '
        definition_line = prefix + definition_line

    elif part_of_speech == 'mat':
        prefix = 'he is able '
        if not definition_line.startswith('to '):
            prefix += ' to '

        definition_line = re.sub("\([a-zA-Z\ \,\;]+\)", '', definition_line)
        definition_line = definition_line.strip('.').strip()
        if definition_line.endswith(' of'):
            definition_line += ' someone or something.'

    return definition_line


def enrich_french_definition(part_of_speech, definition_line):
    if part_of_speech == 'ana':
        prefix = 'c\'est'
        if not definition_line.lower().startswith('un ') or not definition_line.lower().startswith('une '):
            prefix += ' une '
        definition_line = prefix + definition_line + '.'
    elif part_of_speech == 'mat':
        if definition_line.endswith(' à'):
            definition_line = 'il est capable de ' + definition_line
            definition_line += " quelqu'un ou quelque chose"
    elif part_of_speech == 'mpam':
        definition_line = 'quelque chose de ' + definition_line

    return definition_line


def remove_enrichment_artefacts(part_of_speech, translation):
    if translation.lower().startswith('afaka '):
        translation = translation.lower().replace('afaka ', '')
    if translation.lower().startswith('mahay '):
        translation = translation.lower().replace('mahay ', '')
    if translation.lower().endswith(' azy.'):
        translation = translation.lower().replace('azy.', '')
    if translation.lower().endswith(' izy.'):
        translation = translation.lower().replace('izy.', '')
    if translation.lower().endswith(' azy'):
        translation = translation.lower().replace('azy.', '')
    if translation.lower().endswith(' izany.'):
        translation = translation.lower().replace('izany.', '')
    if translation.lower().endswith(' izao.'):
        translation = translation.lower().replace('izao.', '')

    if part_of_speech in ('ana', 'mat'):
        if translation.lower().startswith('afaka '):
            translation = translation.replace('afaka ', '')

        if translation.lower().startswith('dia '):
            translation = translation.replace('dia ', '')

        while translation.lower().startswith('a '):
            translation = translation[2:]

        for word in 'izany izao izy io iny'.split():
            if f' {word}' in translation.lower():
                translation = translation.replace(f' {word}', '').strip()
            if f' {word}.' in translation.lower():
                translation = translation.replace(f' {word}.', '').strip()
            if translation.startswith(f'{word.lower()} dia '):
                translation = translation.replace(f'{word.title()} dia ', '')
            if translation.startswith(f'{word.title()} dia '):
                translation = translation.replace(f'{word.title()} dia ', '')

            if translation.lower().startswith(f'{word} no '):
                translation = translation.replace(f'{word.title()} no ', '')
                translation = translation.replace(f'{word} no ', '')

        if translation.lower().endswith(' izao'):
            translation = translation.lower().replace(' izao', '')

    return translation


def remove_duplicate_definitions(translation):
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

    return data


def translate_using_nllb(part_of_speech, definition_line, source_language, target_language,
                         **kw) -> [UntranslatedDefinition, TranslatedDefinition]:
    helper = NllbDefinitionTranslation(source_language, target_language)

    # Implementation of various tricks to improve the translation quality
    # provided by NLLB on one-word translation sometimes given as definition
    definition_line = definition_line[:3].lower() + definition_line[3:].strip('.')
    if part_of_speech.startswith('e-'):
        print("NLLB should not translate form words.")
        return UntranslatedDefinition(definition_line)

    # remove:
    definition_line = re.sub("\{\{lexique\|([\w]+)\|" + source_language + "\}\}", '(\\1)', definition_line)
    definition_line = re.sub("\{\{([\w]+)\|" + source_language + "\}\}", '(\\1)', definition_line)
    definition_line = re.sub("<ref>(.*)<\/ref>", '', definition_line)

    # Restrict to short definition, as longer definitions seems to be doing just fine (for now)
    if len(definition_line.split()) <= 10:
        if source_language == 'en':
            definition_line = enrich_english_definition(part_of_speech, definition_line)
        elif source_language == 'fr':
            definition_line = enrich_french_definition(part_of_speech, definition_line)

    translation = helper.get_translation(definition_line)
    # Remove all translation artefacts that could have been generated by the tricks performed above.
    translation = remove_enrichment_artefacts(part_of_speech, translation)
    translation = remove_duplicate_definitions(translation)

    if len(translation) > len(definition_line) * 3:
        return UntranslatedDefinition(definition_line)

    if translation is not None:
        return TranslatedDefinition(translation)

    return UntranslatedDefinition(definition_line)


__all__ = [
    'translate_using_nllb',
    'translate_using_opus_mt',
    'translate_using_nltk'
]
