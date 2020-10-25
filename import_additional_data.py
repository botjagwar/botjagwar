import re

from additional_data_importer import SynonymImporter, AntonymImporter, EtymologyImporter
from dump_processor import Processor


class AdditionalDataProcessor(Processor):
    importer_classes = [SynonymImporter, AntonymImporter, EtymologyImporter]
    importers = [c(dry_run=False) for c in importer_classes]

    def __init__(self):
        self.count = 0
        self.missing_translation_writer = None
        self.processor_class = None
        self.translation_lookup_table = None
        self.entry_writer = None

    def worker(self, xml_buffer: str):
        title, content = self.base_worker(xml_buffer)
        languages = re.findall('==[ ]?([A-Za-z]+)[ ]?==\n', content)
        for language in languages:
            for importer in self.importers:
                if language in importer.languages:
                    language_code = importer.languages[language]
                    importer.process_non_wikipage(title, content, language_code)


class EnwiktionaryDumpImporter(object):
    importer_classes = [SynonymImporter, AntonymImporter]

    def __init__(self):
        self.processor = AdditionalDataProcessor()

    def run(self, filename):
        self.processor.process(filename)


if __name__ == '__main__':
    Importer = EnwiktionaryDumpImporter
    importer = Importer()
    importer.run('user_data/en.xml')

    # addi.run('English nouns')

    # addi = SubsectionImporter(data='etym/en', dry_run=True)
    # addi.section_name = 'Etymology'
    # addi.run('Lemmas by language')
