"""
NOTE:
Postprocessors must return a callable accepting a list of Entry objects
String arguments are recommended for the function generator to allow it to be
used in dynamic postprocessor loading though config file.
"""

from logging import getLogger
from typing import List


log = getLogger(__name__)


def add_language_ipa_if_not_exists(languages: List = "automatic"):
    """
    :param language: 'automatic' uses the entry's language.
    If any other value is specified, then that value.
    :return:
    """

    def add_pronunciation(entries: list):
        out_entries = []
        for entry in entries:
            if entry.additional_data is None:
                entry.additional_data = {}

            if languages == "automatic" or entry.language in languages:
                if not "pronunciation" in entry.additional_data:
                    entry.additional_data["pronunciation"] = [
                        "{{" + entry.language + "-IPA}}"
                    ]

            out_entries.append(entry)

        return out_entries

    return add_pronunciation


def add_japanese_verb_form(languages: List = "automatic"):
    def wrapped_add_japanese_verb_form(entries: list):
        out_entries = []
        for entry in entries:

            if entry.language == "ja":
                if entry.additional_data is None:
                    entry.additional_data = {}

                if "inflection" not in entry.additional_data:
                    entry.additional_data["inflection"] = ["{{ja-ojad}}"]

            out_entries.append(entry)
        return out_entries

    return wrapped_add_japanese_verb_form


def add_xlit_if_no_transcription(languages: List = "automatic"):
    def wrapped_add_xlit_if_no_transcription(entries: list):
        out_entries = []
        for entry in entries:
            if entry.additional_data is None:
                entry.additional_data = {}

            if languages == "automatic" or entry.language in languages:
                if "transcription" not in entry.additional_data:
                    entry.additional_data["transcription"] = [
                        "{{xlit|" + entry.language + "|{{subst:BASEPAGENAME}}}}"
                    ]
                else:
                    if "".join(entry.additional_data["transcription"]).strip() == "":
                        entry.additional_data["transcription"] = [
                            "{{xlit|" + entry.language + "|{{subst:BASEPAGENAME}}}}"
                        ]

            out_entries.append(entry)

        return out_entries

    return wrapped_add_xlit_if_no_transcription


def add_wiktionary_credit(wiki: str):
    def wrap_add_wiktionary_credit(entries: list):
        out_entries = []
        for entry in entries:
            if entry.additional_data is None:
                entry.additional_data = {}

            reference = "{{wikibolana|" + wiki + "|" + entry.entry + "}}"
            if "reference" in entry.additional_data:
                if isinstance(entry.additional_data["reference"], list):
                    entry.additional_data["reference"].append(reference)
                else:
                    entry.additional_data["reference"] = [reference]
            else:
                entry.additional_data["reference"] = [reference]
            out_entries.append(entry)

        return out_entries

    return wrap_add_wiktionary_credit


def filter_out_languages(*languages):
    def _delete_languages(entries: list):
        out_entries = []
        for entry in entries:
            if entry.language not in languages:
                out_entries.append(entry)

        return out_entries

    return _delete_languages


def only_accept_from_source_wiki(*args):
    def _delete_languages(entries: list):
        out_entries = []
        source_wiki = args[0]
        for entry in entries:
            exclude = False
            if hasattr(entry, "origin_wiktionary"):
                if entry.origin_wiktionary != source_wiki:
                    exclude = True
            else:
                log.warning(
                    f"Cannot apply only_accept_from_source_wiki for "
                    f"{entry.entry}: it has no 'origin_wiktionary' attribute."
                )

            if not exclude:
                log.debug("Removing entry: " + entry.entry)
                out_entries.append(entry)

        return out_entries

    return _delete_languages
