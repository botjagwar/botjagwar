import os
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

# whitelists to limit translation to certain words
whitelists = {}

# All translation bugs by NLLB belong here
NLLB_GOTCHAS = [
    'famaritana malagasy',
    'fa tsy misy dikany'
]

ENRICHMENT_ARTEFACTS_STARTSWITH = [
    'afaka',
    'izay',
    'ny cela dia',
    'sela dia',
    'ny sela dia',
    'cela dia',
    'fa',
    'mahay',
    'mahavita',

]
ENRICHMENT_ARTEFACTS_ENDSWITH = [
    'ho azy',
    'azy',
    'izy',
    'izany',
    'izao'
    'toy izany'
    'toy izao'
]


def fetch_whitelist(language):
    global whitelists
    returned_data = set()
    whitelist = os.path.join(os.path.dirname(__file__), f'{language}-whitelist')
    for line in open(whitelist, 'r').readlines():
        line = line.strip('\n')
        if len(line) > 3:
            returned_data.add(line)

    whitelists[language] = returned_data


fetch_whitelist('en')
fetch_whitelist('fr')


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
        prefix = 'cela est'
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
    for enrichment_artefact in ENRICHMENT_ARTEFACTS_STARTSWITH:
        if translation.lower().startswith(enrichment_artefact + ' '):
            translation = translation[len(enrichment_artefact + ' '):].strip()

    for enrichment_artefact in ENRICHMENT_ARTEFACTS_ENDSWITH:
        if translation.lower().endswith(' ' + enrichment_artefact):
            translation = translation[:-len(' ' + enrichment_artefact)].strip()

    if part_of_speech in ('ana', 'mat'):
        enrichment_artefacts_startswith = [
            'afaka ',
            'mety ho ',
            'dia ',
            'azony atao ny '
            'azo atao ny '
        ]

        for enrichment_artefact in enrichment_artefacts_startswith:
            if translation.startswith(enrichment_artefact):
                translation = translation[len(enrichment_artefact):].strip()
            if translation.startswith(enrichment_artefact[0].upper() + enrichment_artefact[1:]):
                translation = translation[len(enrichment_artefact):].strip()

        if translation.lower().startswith('azony atao ny '):
            translation = translation.replace('azony atao ny ', '')
            translation = translation.replace('Azony atao ny ', '')

        if translation.lower().startswith('azo atao ny '):
            translation = translation.replace('azo atao ny ', '')
            translation = translation.replace('Azo atao ny ', '')

        while translation.lower().startswith('a '):
            print("stripping 'a' at the beginning of sentence")
            translation = translation[2:]

        while translation.lower().startswith('an '):
            print("stripping 'an' at the beginning of sentence")
            translation = translation[3:]

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
        included = []
        for d in data_as_list:
            d = d.strip()
            if d.lower() not in included:
                out_data.append(d)
                included.append(d)

        data = f'{character} '.join(out_data)

    if ' sy ' in data or ' na ' in data:
        for conj in [' sy ', ' na ']:
            d = data.split(conj)
            if len(d) == 2:
                if d[1].lower() == d[0].lower():
                    data = d[0]

    data = data.strip()
    return data


def remove_gotcha_translations(translation):
    for gotcha in NLLB_GOTCHAS:
        translation = translation.replace(gotcha, '')
        translation = translation.replace(gotcha.title(), '')
        translation = translation.replace(gotcha.upper(), '')
        translation = translation.replace(gotcha.lower(), '')

    return translation


def translate_individual_word_using_dictionary(word, source_language, target_language):
    source_matches = []
    target_matches = []
    if source_language not in whitelists:
        return []
    if word.strip() in whitelists[source_language]:
        for pos in ['ana', 'mat', 'mpam', 'tamb']:
            data_source_language = json_dictionary.look_up_dictionary(source_language, pos, word)
            data_mg = json_dictionary.look_up_dictionary('mg', pos, word)
            if data_source_language and not data_mg:
                definitions = data_source_language[0]['definitions']
                for definition in definitions:
                    if definition['language'] == target_language:
                        source_matches.append(definition['definition'])

    if len(target_matches) == 0:
        return source_matches
    else:
        return []


def translate_using_dictionary(translation, source_language, target_language):
    words = translation.split()
    out_translation = ''
    for w in words:
        matches = translate_individual_word_using_dictionary(w, source_language, target_language)
        if matches:
            out_translation += ' ' + matches[0]
        else:
            out_translation += ' ' + w

    print(f'translate_using_dictionary: {out_translation}')
    return out_translation.strip()


def translate_using_nllb(part_of_speech, definition_line, source_language, target_language,
                         **additional_arguments) -> [UntranslatedDefinition, TranslatedDefinition]:
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

    # One-word definitions are trickier to translate without appropriate context
    # if len(definition_line.split()) < 2:
    #     return UntranslatedDefinition(definition_line)

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
    if len(translation.split()) < 5:
        translation = translate_using_dictionary(translation, source_language, target_language)

    print(f'translate_using_nllb: {definition_line}')

    if definition_line.lower() in NLLB_GOTCHAS:
        return UntranslatedDefinition(definition_line)

    if len(definition_line.split()) > 3:
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
