from api.servicemanager.pgrest import PostgrestTemplateTranslationHelper


def translate_references(references: list, source='en', target='mg', use_postgrest: [bool, str] = 'automatic') -> list:
    """Translates reference templates"""
    translated_references = []
    postgrest = PostgrestTemplateTranslationHelper(use_postgrest)

    for ref in references:
        if ref.strip().startswith('{{'):
            if '|' in ref:
                title = ref[2:ref.find('|', 3)]
            else:
                title = ref[2:ref.find('}}', 3)]

            translated_title = postgrest.get_mapped_template_in_database(title, target_language=target)

            if translated_title is None:
                if 'R:' in title[:3]:
                    translated_title = title[:3].replace('R:', 'Tsiahy:') + title[3:]

            postgrest.add_translated_title(title, translated_title, source_language=source, target_language=target)
            translated_reference = ref.replace(title, translated_title)
        else:
            translated_reference = ref
        translated_references.append(translated_reference)

    return translated_references
