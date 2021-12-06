from logging import getLogger


log = getLogger(__name__)


def add_language_ipa_if_not_exists(languages: list = 'automatic'):
    """
    :param language: 'automatic' uses the entry's language.
    If any other value is specified, then that value.
    :return:
    """
    def add_pronunciation(entries):
        out_entries = []
        for entry in entries:
            if languages == 'automatic' or entry.language in languages:
                if not hasattr(entry, 'pronunciation'):
                    entry.pronunciation = ['{{' + entry.language + '-IPA}}']

            out_entries.append(entry)

        return out_entries
    return add_pronunciation


def add_xlit_if_no_transcription(languages: list = 'automatic'):
    def wrapped_add_xlit_if_no_transcription(entries):
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


def add_wiktionary_credit(wiki):
    def wrap_add_wiktionary_credit(entries):
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

        return wrap_add_wiktionary_credit
