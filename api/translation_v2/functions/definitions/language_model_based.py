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

# All translations bugs by NLLB belong here
nllb_gotchas = [
    'famaritana malagasy',
    'fa tsy misy dikany'
]


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
    definition_line = definition_line.strip()
    if part_of_speech == 'ana':
        prefix = 'that is '
        if not definition_line.lower().startswith('a') and definition_line.lower()[1:].strip()[0] not in 'aeioy':
            prefix += 'a '
        elif not definition_line.lower().startswith('an') and definition_line.lower()[2:].strip()[0] in 'aeioy':
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

        definition_line = prefix + definition_line

        definition_line = re.sub("\([a-zA-Z\ \,\;]+\)", '', definition_line)
        definition_line = definition_line.strip('.').strip()
        if definition_line.endswith(' of'):
            definition_line += ' someone or something.'

    return definition_line


def enrich_french_definition(part_of_speech, definition_line):
    if part_of_speech == 'ana':
        prefix = 'c\'est'
        if not definition_line.lower().startswith('un ') or not definition_line.lower().startswith('une '):
            prefix += ' un ou une '
        definition_line = prefix + definition_line + '.'
    elif part_of_speech == 'mat':
        definition_line = 'il est capable de ' + definition_line
        if definition_line.endswith(' à'):
            definition_line += " quelqu'un ou quelque chose"
    elif part_of_speech == 'mpam':
        definition_line = 'quelque chose de ' + definition_line

    return definition_line


def enrich_german_definition(part_of_speech, definition_line):
    if part_of_speech == 'ana':
        prefix = 'es ist '
        if not definition_line.lower().startswith('ein ') or not definition_line.lower().startswith('eine'):
            prefix += 'ein '
        definition_line = prefix + definition_line + '.'
    elif part_of_speech == 'mat':
        if definition_line.endswith(' à'):
            definition_line = 'Er kannt ' + definition_line + ' können'

    return definition_line


def remove_unknown_characters(translation):
    if '⁇' in translation:
        translation = translation.replace('⁇', '')

    return translation.strip()


def remove_enrichment_artefacts(part_of_speech, translation):
    if translation.lower().startswith('afaka '):
        translation = translation.replace('afaka ', '')
    if translation.lower().startswith('izay '):
        translation = translation.strip()[4:].strip()

    if translation.lower().startswith('fa '):
        translation = translation.strip()[2:].strip()
    if translation.lower().startswith('mahay '):
        translation = translation.replace('mahay ', '')
    if translation.lower().startswith('mahavita '):
        translation = translation.replace('mahavita ', '')
    if not translation.lower().endswith('ho azy') or not translation.lower().endswith(' izy azy'):
        if translation.lower().endswith(' azy'):
            translation = translation[:-4].strip()
    if translation.lower().endswith(' izy') and not translation.lower().endswith('maha izy'):
        translation = translation[:-4].strip()
    # if translation.lower().endswith(' azy'):
    #     translation = translation[:-4].strip()
    if translation.lower().endswith(' izany') and not translation.lower().endswith('toy izany'):
        translation = translation[:-5].strip()
    if translation.lower().endswith(' izao') and not translation.lower().endswith('toy izao'):
        translation = translation[:-4].strip()

    if part_of_speech in ('ana', 'mat'):
        if translation.lower().startswith('afaka '):
            translation = translation.replace('afaka ', '')
            translation = translation.replace('Afaka ', '')

        if translation.lower().startswith('mety ho '):
            translation = translation.replace('mety ho ', '')
            translation = translation.replace('Mety ho ', '')

        if translation.lower().startswith('dia '):
            translation = translation.replace('dia ', '')
            translation = translation.replace('Dia ', '')

        if translation.lower().startswith('azony atao ny '):
            translation = translation.replace('azony atao ny ', '')
            translation = translation.replace('Azony atao ny ', '')

        while translation.lower().startswith('a '):
            print("stripping 'a' at the beginning of sentence")
            translation = translation[2:]

        for word in 'Izany Izao Izy Io Iny Ireo'.split():
            if translation.startswith(word):
                translation = translation[len(word):].strip()

            if translation.startswith(word.lower()):
                translation = translation[len(word):].strip()

            if translation.startswith('no '):
                translation = translation[len('no'):].strip()

            if translation.startswith('dia '):
                translation = translation[len('dia'):].strip()

            first_occurrence = translation.find(f' {word.lower()}')
            if first_occurrence > 0:
                translation = translation[:first_occurrence].strip()

            if translation.lower().startswith(f'{word} no '):
                translation = translation.replace(f'{word} no ', '')
                translation = translation.replace(f'{word} no ', '')

        if translation.lower().endswith(' izao'):
            translation = translation.lower().replace(' izao', '')

        if translation.lower().startswith('hoe '):
            translation = translation.strip()[3:].strip()

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


def remove_gotcha_translations(translation):
    for gotcha in nllb_gotchas:
        translation = translation.replace(gotcha, '')
        translation = translation.replace(gotcha.title(), '')
        translation = translation.replace(gotcha.upper(), '')
        translation = translation.replace(gotcha.lower(), '')

    return translation


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

    # One-word definitions are tricker to translate without appropriate context
    if len(definition_line.split()) < 2:
        return UntranslatedDefinition(definition_line)

    # For medium-sized definitions, further enrich as longer definitions seems to be doing just fine (for now)
    if len(definition_line.split()) <= 30:
        if source_language == 'en':
            definition_line = enrich_english_definition(part_of_speech, definition_line)
        elif source_language == 'fr':
            definition_line = enrich_french_definition(part_of_speech, definition_line)
        elif source_language == 'de':
            definition_line = enrich_german_definition(part_of_speech, definition_line)

    translation = helper.get_translation(definition_line)
    # Remove all translation artefacts that could have been generated by the tricks performed above.
    translation = remove_enrichment_artefacts(part_of_speech, translation)
    translation = remove_unknown_characters(translation)
    translation = remove_duplicate_definitions(translation)
    translation = remove_gotcha_translations(translation)

    if definition_line.lower() in nllb_gotchas:
        return UntranslatedDefinition(definition_line)

    if len(translation) > len(definition_line) * 3:
        return UntranslatedDefinition(definition_line)

    if translation is not None:
        return TranslatedDefinition(translation)

    return UntranslatedDefinition(definition_line)


def translate_roundtrip_using_nllb(part_of_speech, definition_line, source_language='mg', target_language='mg',
                         **kw) -> [UntranslatedDefinition, TranslatedDefinition]:
    # Performs a round-trip translation malagasy -> x -> malagasy to reformulate the definition
    # in order to avoid copyright infringement.
    # This is a very expensive operation, so it should be used only when the definition is not]
    if source_language != target_language:
        raise ValueError("Round-trip translation is only possible when source and target languages are the same.")

    x_to_english = NllbDefinitionTranslation(source_language, 'eng_Latn')
    english_to_x = NllbDefinitionTranslation('eng_Latn', source_language)
    translation = x_to_english.get_translation(definition_line)
    back_translation = english_to_x.get_translation(translation)
    if translation == back_translation:
        return UntranslatedDefinition(definition_line)
    else:
        return TranslatedDefinition(back_translation)


__all__ = [
    'translate_using_nllb',
    'translate_using_opus_mt',
    'translate_using_nltk'
]
