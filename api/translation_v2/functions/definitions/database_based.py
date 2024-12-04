from logging import getLogger

from api.servicemanager.pgrest import JsonDictionary, ConvergentTranslations
from api.translation_v2.exceptions import UnhandledTypeError, UnsupportedLanguageError
from api.translation_v2.functions.utils import MAX_DEPTH
from api.translation_v2.functions.utils import _delink
from api.translation_v2.types import (
    TranslatedDefinition,
    UntranslatedDefinition,
    ConvergentTranslation,
)

json_dictionary = JsonDictionary(use_materialised_view=False)
convergent_translations = ConvergentTranslations()
log = getLogger(__file__)


def _translate_using_bridge_language(
    part_of_speech, definition_line, source_language, target_language, ct_depth=0, **kw
) -> dict:
    if ct_depth >= MAX_DEPTH:
        return {}

    # query db
    log.debug(
        f"(bridge) {definition_line} ({part_of_speech}) [{source_language} -> {target_language}]",
    )
    data = json_dictionary.look_up_dictionary(
        source_language, part_of_speech, _delink(definition_line)
    )
    if not data:
        return {}

    translations = {}
    # lookup translation using definition
    for entry in data:
        for definition in entry["definitions"]:
            defn_language = definition["language"]
            if defn_language == target_language:
                if definition["definition"] in translations:
                    translations[definition["definition"]].append(
                        definition["language"]
                    )
                else:
                    translations[definition["definition"]] = [definition["language"]]

                log.debug(
                    f"Translated {definition_line} --> {definition['definition']}"
                )
            else:
                log.debug(
                    f"(bridge) --> {definition['definition']} [{definition['language']}]"
                )
                translation = translate_using_postgrest_json_dictionary(
                    part_of_speech,
                    definition["definition"],
                    definition["language"],
                    target_language,
                    back_check_pos=False,
                )

                if isinstance(translation, TranslatedDefinition):
                    for w in translation.split(","):
                        w = w.strip()
                        if w in translations:
                            translations[w].append(definition["language"])
                        else:
                            translations[w] = [definition["language"]]
                elif isinstance(translation, UntranslatedDefinition):
                    translation = _translate_using_bridge_language(
                        part_of_speech=part_of_speech,
                        definition_line=definition["definition"],
                        source_language=definition["language"],
                        target_language=target_language,
                        ct_depth=ct_depth + 1,
                    )

                    if translation.keys():
                        for w in translation:
                            w = w.strip()
                            if w in translations:
                                translations[w].append(definition["language"])
                            else:
                                translations[w] = [definition["language"]]
                else:
                    raise UnhandledTypeError(f"{translations.__class__.__name__}")

    return translations


# @time_this('translate_using_postgrest_json_dictionary')
def translate_using_postgrest_json_dictionary(
    part_of_speech,
    definition_line,
    source_language,
    target_language,
    back_check_pos=False,
    **kw,
) -> [UntranslatedDefinition, TranslatedDefinition]:
    if definition_line.endswith("."):
        definition_line = definition_line.strip(".")

    data = json_dictionary.look_up_dictionary(
        source_language, part_of_speech, _delink(definition_line)
    )
    if not data:
        return UntranslatedDefinition(definition_line)

    translations = []
    # lookup translation using definition
    for entry in data:
        for definition in entry["definitions"]:
            if definition["language"] == target_language:
                translations.append(TranslatedDefinition(definition["definition"]))
                log.info(f"Translated {definition_line} --> {definition['definition']}")

        # lookup translation using main word
        for definition in entry["definitions"]:
            log.debug(definition["definition"] + f" [{definition['language']}]")

    if translations:
        # back-check for part of speech.
        if back_check_pos:
            checked_translations = []
            for translation in translations:
                data = json_dictionary.look_up_word(
                    target_language, part_of_speech, translation
                )
                if data:
                    checked_translations.append(translation)

            translations = checked_translations

        # finalize
        t_string = ", ".join(translations)
        log.debug(
            f"{definition_line} ({part_of_speech}) [{source_language} -> {target_language}]: {t_string}"
        )
        return TranslatedDefinition(t_string)

    return UntranslatedDefinition(definition_line)


def translate_using_suggested_translations_fr_mg(
    part_of_speech, definition_line, source_language, target_language, **kw
) -> [UntranslatedDefinition, ConvergentTranslation]:
    convergent_translations = ConvergentTranslations()
    if source_language == "fr":
        translations = convergent_translations.get_suggested_translations_fr_mg(
            target_language, part_of_speech=part_of_speech, definition=definition_line
        )
    else:
        raise UnsupportedLanguageError(
            f"Source language '{source_language}' "
            f"cannot be used for convergent translations"
        )

    if translations:
        ret_translations = [t["suggested_definition"] for t in translations]
        if ret_translations:
            k = ", ".join(sorted(list(set(ret_translations))))
            return ConvergentTranslation(k)

    return UntranslatedDefinition(definition_line)


def translate_using_convergent_definition(
    part_of_speech, definition_line, source_language, target_language, **kw
) -> [UntranslatedDefinition, ConvergentTranslation]:
    if source_language == "en":
        translations = convergent_translations.get_convergent_translation(
            target_language,
            part_of_speech=part_of_speech,
            en_definition=definition_line,
        )
    elif source_language == "fr":
        translations = convergent_translations.get_convergent_translation(
            target_language,
            part_of_speech=part_of_speech,
            fr_definition=definition_line,
        )
    else:
        raise UnsupportedLanguageError(
            f"Source language '{source_language}' "
            f"cannot be used for convergent translations"
        )

    ret_translations = [t["suggested_definition"] for t in translations]
    print(ret_translations)
    if ret_translations:
        k = ", ".join(sorted(list(set(ret_translations))))
        return ConvergentTranslation(k)

    return UntranslatedDefinition(definition_line)


def translate_using_bridge_language(
    part_of_speech, definition_line, source_language, target_language, **kw
) -> [UntranslatedDefinition, TranslatedDefinition]:
    translations = _translate_using_bridge_language(
        part_of_speech, definition_line, source_language, target_language, **kw
    )
    log.debug(translations)

    if translations.keys():
        k = ", ".join(sorted(list(set(translations))))
        return TranslatedDefinition(k)

    return UntranslatedDefinition(definition_line)


__all__ = [
    "json_dictionary",
    "convergent_translations",
    "translate_using_bridge_language",
    "translate_using_convergent_definition",
    "translate_using_postgrest_json_dictionary",
    "translate_using_suggested_translations_fr_mg",
    "_translate_using_bridge_language",
]
