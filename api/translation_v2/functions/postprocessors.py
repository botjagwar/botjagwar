def add_language_IPA_if_not_exists(language='automatic'):
    """
    :param language: 'automatic' uses the entry's language.
    If any other value is specified, then that value.
    :return:
    """
    def add_pronunciation(entries):
        print('add_pronunciation:' + language)
        out_entries = []
        for entry in entries:
            if not hasattr(entry, 'pronunciation'):
                if language != 'automatic':
                    if entry.language == language:
                        entry.pronunciation = ['{{' + language + '-IPA}}']
                else:
                    entry.pronunciation = ['{{' + entry.language + '-IPA}}']

            out_entries.append(entry)

        return out_entries
    return add_pronunciation


def add_xlit_if_no_transcription(entries):
    out_entries = []
    for entry in entries:
        if not hasattr(entry, 'transcription'):
            entry.transcription = ['{{xlit|' + entry.language + '|{{subst:BASEPAGENAME}}}}']
        else:
            if ''.join(getattr(entry, 'transcription')).strip() == '':
                entry.transcription = ['{{xlit|' + entry.language + '|{{subst:BASEPAGENAME}}}}']

        out_entries.append(entry)

    return out_entries


def add_wiktionary_credit(wiki):
    def add_wiktionary_credit(entries):
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

        return add_wiktionary_credit
