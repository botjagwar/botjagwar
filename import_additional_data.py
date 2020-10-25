import sys

from additional_data_importer import SynonymImporter, AntonymImporter, EtymologyImporter
from dump_processor import Processor


class AdditionalDataProcessor(Processor):
    importer_classes = [SynonymImporter, AntonymImporter, EtymologyImporter]
    importers = [c(dry_run=False) for c in importer_classes]
    language_code = 'en'

    def worker(self, xml_buffer: str):
        title, content = self.base_worker(xml_buffer)
        for importer in self.importers:
            importer.process_non_wikipage(title, content, self.language_code)


class EnwiktionaryDumpImporter(object):
    importer_classes = [SynonymImporter, AntonymImporter]

    language_code = 'en'

    def __init__(self):
        self.processor = AdditionalDataProcessor(self.language_code)

    def run(self, filename):
        self.processor.process(filename)


if __name__ == '__main__':
    Importer = EnwiktionaryDumpImporter
    Importer.language_code = sys.argv[1]
    importer = Importer()
    importer.run('user_data/en.xml')

    # addi.run('English nouns')

    # addi = SubsectionImporter(data='etym/en', dry_run=True)
    # addi.section_name = 'Etymology'
    # addi.run('Lemmas by language')
