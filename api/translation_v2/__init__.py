from api.model.word import Entry
from .functions import translate_form_of_templates, translate_using_postgrest_json_dictionary
from .types import TranslatedDefinition, UntranslatedDefinition


class EntryTranslator(object):
    methods = [
        translate_form_of_templates
    ]

    def translate(self, entry: Entry, source_language: str,
                  target_language: str = 'mg') -> Entry:
        out_definitions = []
        for definition in entry.definitions:
            out_entry_dict = entry.to_dict()
            for method in self.methods:
                extracted_definition = method(
                    entry.part_of_speech,
                    definition,
                    source_language,
                    target_language)
                if isinstance(extracted_definition, TranslatedDefinition):
                    out_definitions.append(extracted_definition)

            out_entry_dict['definitions'] = out_definitions
            return Entry(**out_entry_dict)

    def evaluate(self, part_of_speech, entry1, entry2) -> int:
        return 0
