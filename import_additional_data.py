import re
import traceback

from api.importer.wiktionary.en import AlternativeFormsImporter
from api.importer.wiktionary.en import DerivedTermsImporter
from api.importer.wiktionary.en import FurtherReadingImporter
from api.importer.wiktionary.en import ReferencesImporter
from dump_processor import Processor


class AdditionalDataProcessor(Processor):

    def __init__(self, importer_classes: list):
        self.importers = [c(dry_run=False) for c in importer_classes]
        self.count = 0
        self.missing_translation_writer = None
        self.processor_class = None
        self.translation_lookup_table = None
        self.entry_writer = None

    def worker(self, xml_buffer: str):
        title, content = self.base_worker(xml_buffer)
        try:
            languages = re.findall('==[ ]?([A-Za-z]+)[ ]?==\n', content)
            for language in languages:
                for importer in self.importers:
                    if language in importer.languages:
                        language_code = importer.languages[language]
                        importer.process_non_wikipage(title, content, language_code)
        except Exception as exc:
            traceback.print_exc()



class EnWiktionaryCategoryImporter(object):
    importer_classes = []
    def __init__(self):
        pass

    def run(self):
        pass


class EnwiktionaryDumpImporter(object):
    importer_classes = [
        DerivedTermsImporter,
        ReferencesImporter,
        FurtherReadingImporter,
        AlternativeFormsImporter
    ]

    def __init__(self):
        self.processor = AdditionalDataProcessor(self.importer_classes)

    def run(self, filename):
        self.processor.process(filename)


class RakibolanaOrgPickleImporter(object):

    def run(self):
        pass


if __name__ == '__main__':
    Importer = EnwiktionaryDumpImporter
    importer = Importer()
    importer.run('user_data/dumps/en_1.xml')
    importer.run('user_data/dumps/en_2.xml')
    importer.run('user_data/dumps/en_3.xml')
    importer.run('user_data/dumps/en_4.xml')
    importer.run('user_data/dumps/en_5.xml')
    importer.run('user_data/dumps/en_6.xml')
    importer.run('user_data/dumps/en_7.xml')
    importer.run('user_data/dumps/en_8.xml')
    importer.run('user_data/dumps/en_9.xml')
    importer.run('user_data/dumps/en_10.xml')
    importer.run('user_data/dumps/en_11.xml')
    importer.run('user_data/dumps/en_12.xml')
    importer.run('user_data/dumps/en_13.xml')
