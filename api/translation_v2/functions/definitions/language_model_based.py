import os
import re
from functools import lru_cache
from logging import getLogger
from pathlib import Path

from api.servicemanager.gemma import GemmaDefinitionReformulator
from api.servicemanager.nllb import DefinitionTranslationError, NllbDefinitionTranslation
from api.servicemanager.openmt import OpenMtTranslation
from api.servicemanager.pgrest import JsonDictionary, ConvergentTranslations
from api.translation_v2.types import TranslatedDefinition, UntranslatedDefinition

from api.translation_v2.functions.definitions.postprocessors import (
    fix_repeated_subsentence, remove_empty_translations,
    remove_definition_if_too_many_foreign_words,
)

json_dictionary = JsonDictionary(use_materialised_view=False)
convergent_translations = ConvergentTranslations()
log = getLogger(__file__)

# All translation bugs by NLLB belong here
NLLB_GOTCHAS = ["famaritana malagasy", "fa tsy misy dikany"]
BASIC_ENGLISH_THRESHOLD = 0.75
BASIC_ENGLISH_MINIMUM_WORDS = 7
BASIC_ENGLISH_PATH = Path(__file__).resolve().parents[4] / "user_data/basic_english.txt"
_ENGLISH_WORD_PATTERN = re.compile(r"[a-z]+(?:['-][a-z]+)*", re.IGNORECASE)

ENRICHMENT_ARTEFACTS_STARTSWITH = [
    "-ny is an",
    "-ny is a",
    "afaka",
    "izay",
    "ny cela dia",
    "sela dia",
    "ny sela dia",
    "cela dia",
    "fa",
    "mahay",
    "mahavita",
]
ENRICHMENT_ARTEFACTS_ENDSWITH = [
    "ho azy",
    "azy",
    "izy",
    "izany",
    "izao" "toy izany" "toy izao",
]

# Connectors used when removing duplicate words
DUPLICATE_WORD_CONNECTORS = ["na", "sy"]

MPAM_ENRICHMENT_ARTEFACTS_STARTSWITH = [
    "zavatra iray izay ",
    "zavatra iray ",
    "zavatra izay ",
    "zavatra ",
]


def fetch_whitelist(language):
    global whitelists
    returned_data = []
    whitelist = os.path.join(os.path.dirname(__file__), f"{language}-whitelist")
    for line in open(whitelist, "r", encoding="utf-8"):
        line = line.strip("\n")
        if len(line) > 3:
            returned_data.append(line)

    whitelists[language] = returned_data


# whitelists to limit translation to certain words
whitelists = {}

fetch_whitelist("en")
fetch_whitelist("fr")


def translate_using_nltk(
        part_of_speech, definition_line, source_language, target_language, **kw
) -> [UntranslatedDefinition, TranslatedDefinition]:
    pass


def translate_using_opus_mt(
        part_of_speech, definition_line, source_language, target_language, **kw
) -> [UntranslatedDefinition, TranslatedDefinition]:
    helper = OpenMtTranslation(source_language, target_language)
    data = helper.get_translation(definition_line)
    if data is not None:
        return TranslatedDefinition(data)


def _english_ana_enrichment(definition_line: str) -> str:
    prefix = "that is "
    if (
        not definition_line.lower().startswith("a")
        and definition_line.lower()[1:].strip()[0] not in "aeioy"
    ):
        if not definition_line.lower().startswith("a "):
            prefix += "a "
    elif (
        not definition_line.lower().startswith("an")
        and definition_line.lower()[2:].strip()[0] in "aeioy"
    ):
        if not definition_line.lower().startswith("an "):
            prefix += "an "

    return prefix + definition_line


def _english_mpam_enrichment(definition_line: str) -> str:
    return "something that is " + definition_line


def _english_mat_enrichment(definition_line: str) -> str:
    prefix = "he is able "
    if not definition_line.startswith("to "):
        prefix += " to "

    definition_line = prefix + definition_line
    definition_line = re.sub(r"\([a-zA-Z\ \,\;]+\)", "", definition_line)
    definition_line = definition_line.strip(".").strip()
    if definition_line.endswith(" of"):
        definition_line += " someone or something."

    return definition_line


ENGLISH_ENRICHERS = {
    "ana": _english_ana_enrichment,
    "mpam": _english_mpam_enrichment,
    "mat": _english_mat_enrichment,
}


def enrich_english_definition(part_of_speech, definition_line):
    """Enrich an English definition based on its part of speech."""
    definition_line = definition_line.strip()
    enricher = ENGLISH_ENRICHERS.get(part_of_speech)
    return enricher(definition_line) if enricher else definition_line


def enrich_french_definition(part_of_speech, definition_line):
    if part_of_speech == "ana":
        prefix = "cela est"
        if not definition_line.lower().startswith(
                "un "
        ) or not definition_line.lower().startswith("une "):
            prefix += " un ou une "
        definition_line = prefix + definition_line + "."
    elif part_of_speech == "mat":
        definition_line = f"il est capable de {definition_line}"
        if definition_line.endswith(" à"):
            definition_line += " quelqu'un ou quelque chose"
    elif part_of_speech == "mpam":
        definition_line = f"quelque chose de {definition_line}"

    return definition_line


def enrich_german_definition(part_of_speech, definition_line):
    if part_of_speech == "ana":
        prefix = "es ist "
        if not definition_line.lower().startswith(
                "ein "
        ) or not definition_line.lower().startswith("eine"):
            prefix += "ein "
        definition_line = prefix + definition_line + "."
    elif part_of_speech == "mat":
        if definition_line.endswith(" à"):
            definition_line = f"Er kannt {definition_line} können"

    return definition_line


def remove_unknown_characters(translation):
    if "⁇" in translation:
        translation = translation.replace("⁇", "")

    return translation.strip()


def _strip_prefixes_case_insensitive(text, prefixes):
    for prefix in prefixes:
        if text.lower() == prefix.rstrip().lower():
            return ""
        if text.lower().startswith(prefix.lower()):
            text = text[len(prefix):].strip()
    return text


def _strip_mpam_enrichment_prefix(text: str) -> str:
    """Strip exactly one generated adjective scaffold from translated text."""
    normalized = re.sub(r"\s+", " ", text).strip()
    for prefix in MPAM_ENRICHMENT_ARTEFACTS_STARTSWITH:
        if normalized.lower() == prefix.rstrip().lower():
            return ""
        if normalized.lower().startswith(prefix.lower()):
            return normalized[len(prefix):].strip()
    return text


def _strip_suffixes_case_insensitive(text, suffixes):
    for suffix in suffixes:
        if text.lower().endswith(suffix.lower()):
            text = text[:-len(suffix)].strip()
    return text


def _strip_izy_suffix_case_insensitive(text: str) -> str:
    """Strip a trailing ' izy' only when it is a generated enrichment artifact.

    The suffix is removed when it appears after a bare word, but kept when it
    follows a genitive construction ('{word}n\' izy') because in that case the
    pronoun is grammatically meaningful rather than an artifact.
    """
    suffix = " izy"
    lower_text = text.lower()
    if not lower_text.endswith(suffix):
        return text

    prefix = text[: -len(suffix)].rstrip()
    if prefix.endswith("'") or prefix.endswith("n'"):
        # Preserve izy after genitive marker: ...n' izy / ...' izy
        return text

    return prefix


def _strip_prefixes_with_caps(text, prefixes):
    working_set = set(prefixes)
    set_size = len(working_set)
    iter_count = 0
    while working_set:
        hit = 0
        for prefix in prefixes:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
                hit += 1
            elif text.startswith(prefix[0].upper() + prefix[1:]):
                text = text[len(prefix):].strip()
                hit += 1

            if hit != 0:
                working_set -= {prefix}

        iter_count += 1
        if iter_count > set_size:
            break

    return text


def _remove_case_insensitive_prefix(text, prefix):
    if text.lower().startswith(prefix.lower()):
        text = text.replace(prefix, "").replace(prefix.capitalize(), "")
    return text


def _strip_pronoun_artifacts(text, words):
    for word in words:
        stripped_prefix = False
        if text.startswith(word):
            text = text[len(word):].strip()
            stripped_prefix = True
        elif text.startswith(word.lower()):
            text = text[len(word):].strip()
            stripped_prefix = True

        if text.startswith("no "):
            text = text[len("no"):].strip()

        if text.startswith("dia "):
            text = text[len("dia"):].strip()

        first_occurrence = text.lower().find(f" {word.lower()}")
        if stripped_prefix and first_occurrence > 0:
            text = text[:first_occurrence].strip()

        if text.lower().startswith(f"{word} no "):
            text = text.replace(f"{word} no ", "")
            text = text.replace(f"{word} no ", "")

    return text


def remove_enrichment_artefacts(part_of_speech, translation):
    translation = translation.strip()
    if part_of_speech == "mpam":
        translation = _strip_mpam_enrichment_prefix(translation)

    translation = _strip_prefixes_case_insensitive(
        translation, [f"{p} " for p in ENRICHMENT_ARTEFACTS_STARTSWITH]
    )
    other_suffixes = [
        f" {p}" for p in ENRICHMENT_ARTEFACTS_ENDSWITH if p != "izy"
    ]
    translation = _strip_suffixes_case_insensitive(translation, other_suffixes)
    translation = _strip_izy_suffix_case_insensitive(translation)

    if part_of_speech in ("ana", "mat"):
        enrichment_artefacts_startswith = [
            "afaka ny ",
            "afaka ",
            "mety ho ",
            "dia ",
            "azony atao ny " "azo atao ny ",
            "atao hoe ",
        ]

        translation = _strip_prefixes_with_caps(
            translation, enrichment_artefacts_startswith
        )
        translation = _remove_case_insensitive_prefix(translation, "azony atao ny ")
        translation = _remove_case_insensitive_prefix(translation, "azo atao ny ")

        while translation.lower().startswith("a "):
            print("stripping 'a' at the beginning of sentence")
            translation = translation[2:]

        while translation.lower().startswith("an "):
            print("stripping 'an' at the beginning of sentence")
            translation = translation[3:]

        translation = _strip_pronoun_artifacts(
            translation, "Izany Izao Izy Io Iny Ireo".split()
        )

        if translation.lower().endswith(" izao"):
            translation = translation.lower().replace(" izao", "")

        if translation.lower().startswith("hoe "):
            translation = translation.strip()[3:].strip()

        if translation.lower().endswith(" noho"):
            translation = translation + " izany"

    return translation


def remove_duplicate_definitions(translation):
    translation = translation.strip(".")
    data = translation
    for character in ",;":
        data_as_list = data.split(character)
        out_data = []
        included = []
        for d in data_as_list:
            d = d.strip()
            if d.lower() not in included:
                out_data.append(d)
                included.append(d)

        data = f"{character} ".join(out_data)

    if " sy " in data or " na " in data:
        for conj in [" sy ", " na "]:
            d = data.split(conj)
            if len(d) == 2 and d[1].lower() == d[0].lower():
                data = d[0]

    data = data.strip()
    return data


def remove_duplicate_words(translation: str) -> str:
    """Remove consecutive duplicate words joined by connectors."""
    for connector in DUPLICATE_WORD_CONNECTORS:
        pattern = re.compile(
            rf"\b([\w-]+)\b\s+{connector}\s+\b\1\b",
            flags=re.IGNORECASE,
        )
        while True:
            translation, count = pattern.subn(lambda m: m.group(1), translation)
            if count == 0:
                break
    return translation


def remove_gotcha_translations(translation):
    for gotcha in NLLB_GOTCHAS:
        translation = translation.replace(gotcha, "")
        translation = translation.replace(gotcha.title(), "")
        translation = translation.replace(gotcha.upper(), "")
        translation = translation.replace(gotcha.lower(), "")

    return translation


def translate_individual_word_using_dictionary(word, source_language, target_language):
    source_matches = []
    target_matches = []
    if source_language not in whitelists:
        return []
    if word.strip() in whitelists[source_language]:
        for pos in ["ana", "mat", "mpam", "tamb"]:
            data_source_language = json_dictionary.look_up_dictionary(
                source_language, pos, word
            )
            data_mg = json_dictionary.look_up_dictionary("mg", pos, word)
            if data_source_language and not data_mg:
                definitions = data_source_language[0]["definitions"]
                source_matches.extend(
                    definition["definition"]
                    for definition in definitions
                    if definition["language"] == target_language
                )
    return [] if target_matches else source_matches


def translate_using_dictionary(translation, source_language, target_language):
    words = translation.split()
    out_translation = "".join(
        (
            f" {matches[0]}"
            if (
                matches := translate_individual_word_using_dictionary(
                    w, source_language, target_language
                )
            )
            else f" {w}"
        )
        for w in words
    )
    print(f"translate_using_dictionary: {out_translation}")
    return out_translation.strip()


def translate_using_nllb(
        entry,
        definition_line,
        source_language,
        target_language,
        **additional_arguments
):
    """
    Translate a definition using NLLB model with language-specific processing.
    """
    part_of_speech = entry.part_of_speech
    # Skip form words and known problematic patterns
    if part_of_speech.startswith("e-"):
        log.debug("NLLB skipping form word translation")
        return UntranslatedDefinition(definition_line)

    if definition_line.lower() in NLLB_GOTCHAS:
        return UntranslatedDefinition(definition_line)

    # Basic preprocessing
    definition_line = definition_line[:3].lower() + definition_line[3:].strip(".")
    definition_line = _remove_template_patterns(definition_line, source_language)

    if _should_reformulate_with_gemma(
        definition_line,
        source_language,
        additional_arguments.get("basic_english_gate_enabled"),
    ):
        try:
            definition_line = GemmaDefinitionReformulator().reformulate(definition_line)
        except RuntimeError as exc:
            log.warning(
                "Unable to reformulate low-vocabulary definition %r with Gemma: %s",
                definition_line,
                exc,
            )
            return UntranslatedDefinition(definition_line)

    # Apply language-specific processing
    processed_definition = _process_by_language(
        definition_line, part_of_speech, source_language
    )

    # Get translation
    helper = NllbDefinitionTranslation(
        target_language=target_language,
        source_language=source_language,
    )
    try:
        roundtrip_setting = additional_arguments.get(
            "nllb_roundtrip_validation_enabled"
        )
        if callable(roundtrip_setting):
            translation = helper.get_translation(
                processed_definition,
                roundtrip_validation_enabled=roundtrip_setting(),
            )
        else:
            translation = helper.get_translation(processed_definition)
    except DefinitionTranslationError as exc:
        log.warning("Unable to translate definition %r with NLLB: %s", definition_line, exc)
        return UntranslatedDefinition(definition_line)

    if translation is None:
        return UntranslatedDefinition(definition_line)

    # Postprocess translation
    translation = _postprocess_translation(translation, part_of_speech, source_language, target_language)

    # Final validation
    if not translation:
        log.debug("NLLB translation resulted in empty string")
        return UntranslatedDefinition(definition_line)

    if _is_verbatim_copy(translation, processed_definition):
        log.warning(
            "NLLB left the source text untranslated: %r", translation
        )
        return UntranslatedDefinition(definition_line)

    if len(definition_line.split()) > 3 and len(translation) > len(definition_line) * 3:
        log.debug(f"Translation too long compared to original: {translation}")
        return UntranslatedDefinition(definition_line)

    return TranslatedDefinition(translation)


@lru_cache(maxsize=1)
def _basic_english_vocabulary() -> frozenset[str]:
    """Load the Basic English vocabulary distributed with Botjagwar."""
    with BASIC_ENGLISH_PATH.open(encoding="utf-8") as vocabulary_file:
        return frozenset(
            word.strip().casefold()
            for word in vocabulary_file
            if word.strip()
        )


def basic_english_score(definition: str) -> float:
    """Return the share of definition words found in the Basic English list."""
    words = [word.casefold() for word in _ENGLISH_WORD_PATTERN.findall(definition)]
    if not words:
        return 0.0
    vocabulary = _basic_english_vocabulary()
    return sum(word in vocabulary for word in words) / len(words)


def _should_reformulate_with_gemma(
    definition: str,
    source_language: str,
    enabled_provider: object,
) -> bool:
    """Return whether an English definition must be simplified before NLLB."""
    words = _ENGLISH_WORD_PATTERN.findall(definition)
    if source_language != "en" or len(words) < BASIC_ENGLISH_MINIMUM_WORDS:
        return False

    if not callable(enabled_provider) or not enabled_provider():
        log.info("Basic English vocabulary gate skipped per configuration")
        return False

    score = basic_english_score(definition)
    log.info(
        "Basic English vocabulary gate running: score=%.3f threshold=%.3f",
        score,
        BASIC_ENGLISH_THRESHOLD,
    )
    return score < BASIC_ENGLISH_THRESHOLD


def _is_verbatim_copy(translation: str, source: str) -> bool:
    """Return whether a translation merely reproduces the source text.

    The comparison is case-insensitive and ignores punctuation, whitespace and
    the enrichment artifacts that are prepended before translation.
    """
    normalised_translation = _normalise_translation(translation)
    normalised_source = _normalise_translation(source)
    return normalised_translation == normalised_source


def _normalise_translation(text: str) -> str:
    """Normalise a definition for verbatim-copy comparison."""
    text = re.sub(r"[.,;:()!?'\"-]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def _process_by_language(definition_line, part_of_speech, source_language):
    """Apply language-specific processing to the definition."""
    # Only apply enrichment for shorter and medium definitions
    if len(definition_line.split()) <= 30:
        language_processors = {
            "en": _process_english,
            "fr": _process_french,
            "de": _process_german
        }

        processor = language_processors.get(source_language)
        if processor:
            return processor(definition_line, part_of_speech)

    return definition_line


def _process_english(definition_line, part_of_speech):
    """Process English definitions with language-specific rules."""
    definition_line = definition_line.replace(';', ':')
    if part_of_speech == "ana":
        prefix = "that is "
        normalized_definition = definition_line.lower()
        after_first_char = normalized_definition[1:].strip()
        after_second_char = normalized_definition[2:].strip()
        if (
            not normalized_definition.startswith("a")
            and after_first_char
            and after_first_char[0] not in "aeioy"
        ):
            prefix += "a "
        elif (
            not normalized_definition.startswith("an")
            and after_second_char
            and after_second_char[0] in "aeioy"
        ):
            prefix += "an "
        definition_line = prefix + definition_line

    elif part_of_speech == "mpam":
        definition_line = "something that is " + definition_line

    elif part_of_speech == "mat":
        prefix = "he is able "
        if not definition_line.startswith("to "):
            prefix += "to "
        definition_line = prefix + definition_line

        definition_line = re.sub(r"\([a-zA-Z\ \,\;]+\)", "", definition_line)
        definition_line = definition_line.strip(".").strip()
        if definition_line.endswith(" of"):
            definition_line += " someone or something."

    return definition_line


def _process_french(definition_line, part_of_speech):
    """Process French definitions with language-specific rules."""
    if part_of_speech == "ana":
        prefix = "cela est"
        if not definition_line.lower().startswith("un ") or not definition_line.lower().startswith("une "):
            prefix += " un ou une "
        definition_line = prefix + definition_line + "."

    elif part_of_speech == "mat":
        definition_line = f"il est capable de {definition_line}"
        if definition_line.endswith(" à"):
            definition_line += " quelqu'un ou quelque chose"

    elif part_of_speech == "mpam":
        definition_line = f"quelque chose de {definition_line}"

    return definition_line


def _process_german(definition_line, part_of_speech):
    """Process German definitions with language-specific rules."""
    if part_of_speech == "ana":
        prefix = "es ist "
        if not definition_line.lower().startswith("ein ") or not definition_line.lower().startswith("eine"):
            prefix += "ein "
        definition_line = prefix + definition_line + "."

    elif part_of_speech == "mat":
        if definition_line.endswith(" à"):
            definition_line = f"Er kannt {definition_line} können"

    return definition_line


def _remove_template_patterns(definition_line, source_language):
    """Remove wiki templates and references from definition."""
    definition_line = re.sub(
        r"\{\{lexique\|([\w]+)\|" + source_language + r"\}\}", r"(\1)", definition_line
    )
    definition_line = re.sub(
        r"\{\{([\w]+)\|" + source_language + r"\}\}", r"(\1)", definition_line
    )
    definition_line = re.sub(r"<ref>(.*)</ref>", "", definition_line)
    return definition_line


def _postprocess_translation(translation, part_of_speech, source_language, target_language):
    """Apply all post-processing steps to the translation."""
    # Remove artifacts and issues
    translation = remove_unknown_characters(translation)
    translation = remove_enrichment_artefacts(part_of_speech, translation)
    translation = remove_duplicate_definitions(translation)
    translation = remove_duplicate_words(translation)
    translation = remove_gotcha_translations(translation)

    # Use dictionary for very short translations
    if len(translation.split()) < 5:
        log.debug(f"Short translation, using dictionary: {translation}")
        translation = translate_using_dictionary(
            translation, source_language, target_language
        )

    # Apply general post-processing
    return post_process_translation(translation)


def post_process_translation(translation):
    translation = fix_repeated_subsentence(translation)
    translation = remove_empty_translations(translation)
    translation = remove_definition_if_too_many_foreign_words(translation)
    return translation


__all__ = ["translate_using_nllb", "translate_using_opus_mt", "translate_using_nltk", 'whitelists']
