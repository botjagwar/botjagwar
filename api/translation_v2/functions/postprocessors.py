"""
NOTE:
Postprocessors must return a callable accepting a list of Entry objects
String arguments are recommended for the function generator to allow it to be
used in dynamic postprocessor loading though config file.
"""
from logging import getLogger
from typing import List


log = getLogger(__name__)


def add_language_ipa_if_not_exists(languages: List = 'automatic'):
    """
    :param language: 'automatic' uses the entry's language.
    If any other value is specified, then that value.
    :return:
    """
    def add_pronunciation(entries: list):
        out_entries = []
        for entry in entries:
            if languages == 'automatic' or entry.language in languages:
                if not hasattr(entry, 'pronunciation'):
                    entry.pronunciation = ['{{' + entry.language + '-IPA}}']

            out_entries.append(entry)

        return out_entries
    return add_pronunciation


def add_xlit_if_no_transcription(languages: List = 'automatic'):
    def wrapped_add_xlit_if_no_transcription(entries: list):
        out_entries = []
        for entry in entries:
            if languages == 'automatic' or entry.language in languages:
                if not hasattr(entry, 'transcription'):
                    entry.transcription = ['{{xlit|' + entry.language + '|{{subst:BASEPAGENAME}}}}']
                else:
                    if ''.join(getattr(entry, 'transcription')).strip() == '':
                        entry.transcription = ['{{xlit|' + entry.language + '|{{subst:BASEPAGENAME}}}}']

            out_entries.append(entry)

        return out_entries
    return wrapped_add_xlit_if_no_transcription


def add_wiktionary_credit(wiki: str):
    def wrap_add_wiktionary_credit(entries: list):
        out_entries = []
        for entry in entries:
            reference = "{{wikibolana|" + wiki + '|' + entry.entry + '}}'
            if hasattr(entry, 'reference'):
                if isinstance(entry.reference, list):
                    entry.reference.append(reference)
                else:
                    entry.reference = [reference]
            else:
                entry.reference = [reference]
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
