import sys

from api.decorator import singleton
from object_model.word import Entry
from word_forms import perform_function_on_entry

language_code = sys.argv[1]
category_name = sys.argv[2]
template = sys.argv[3] if len(sys.argv) >= 4 else 'e-ana'


@singleton
class Writer(object):
    def __init__(self):
        self.file = open(
            f'user_data/cache_extractor/{language_code}_{category_name}.csv', 'w')

    def writeln(self, data):
        self.file.write(data + '\n')


def action(entry: Entry):
    file_handler = Writer()
    for defn in entry.entry_definition:
        if '{{' in defn or '}}' in defn:
            continue

        if entry.language == 'la':
            defn = defn.replace(';', ',')
            file_handler.writeln(
                f'{entry.entry}; {entry.part_of_speech}; {defn}')

    return 0


if __name__ == '__main__':
    perform_function_on_entry(action, language_code, category_name)()
