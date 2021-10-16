from api.extractors.site_extractor import RakibolanaSiteExtactor
from api.extractors.site_extractor import SiteExtractorException
from api.extractors.site_extractor import TenyMalagasySiteExtractor
from api.importer import AdditionalDataImporterError
from api.importer.rakibolanamalagasy import RakibolanaMalagasyImporter
from api.importer.rakibolanamalagasy import TenyMalagasyImporter


class EnWiktionaryCategoryImporter(object):
    importer_classes = []

    def __init__(self):
        pass

    def run(self):
        pass


class TenyMalagasyPickleImporter(object):
    def __init__(self):
        self.importer = TenyMalagasyImporter()
        self.extractor = TenyMalagasySiteExtractor()
        self.importer.populate_cache('mg')

    def run(self):
        for data in self.extractor.cache_engine.list():
            try:
                entry = self.extractor.lookup(data)
            except SiteExtractorException:
                continue

            if not entry.definitions:
                continue
            else:
                print('>>> %s <<<' % entry.entry)
                self.process_rakibolana_definition(entry)

    def process_rakibolana_definition(self, entry):
        definitions = entry.definitions
        for definition in definitions:
            try:
                self.importer.write_additional_data(
                    entry.entry, 'mg', definition)
            except Exception as exception:
                print(exception)


class RakibolanaOrgPickleImporter(object):
    def __init__(self):
        self.importer = RakibolanaMalagasyImporter()
        self.extractor = RakibolanaSiteExtactor()
        self.importer.populate_cache('mg')

    def run(self):
        for data in self.extractor.cache_engine.list():
            entry = self.extractor.lookup(data)
            if not entry.definitions:
                continue
            else:
                print('>>> %s <<<' % entry.entry)
                self.process_rakibolana_definition(entry,)

    def process_rakibolana_definition(self, entry):
        definitions = entry.definitions
        definition = definitions[0]
        definition = definition.replace('amim$$', 'amim-')
        raw_definition = definition.replace('$$', '|')

        print(raw_definition)
        self.importer.write_raw(entry.entry, 'mg', raw_definition)

        # definition listings
        pz = definition.find('$$')
        defn1 = definition[:pz]
        if '(' in defn1 and ')' in defn1:
            new_pz = definition.find('$$', pz)
            defn1 = definition[:new_pz].replace('$$', '')

        print(defn1)
        try:
            self.importer.write_additional_data(entry.entry, 'mg', defn1)
        except AdditionalDataImporterError as exc:
            pass

        # t.i.f listings
        if definition.find('t$$i$$f$$$$') != -1:
            p1 = definition.rfind('t$$i$$f$$$$') + len('t$$i$$f$$$$')
            p2 = definition.find('$$', p1)
            tif = definition[p1:p2]
            if tif:
                for char in ',/1':
                    tif = tif.replace(char, '|')
                tif = tif.replace(' f ', '|')
                tif = tif.replace(' j ', '|')
                tif = tif.replace(' l ', '|')
                tifs = [w.strip().lower() for w in tif.split('|')]
                for tif in tifs:
                    self.importer.write_tif(entry.entry, 'mg', tif)
                    print(tif)


if __name__ == '__main__':
    import requests
    from api.importer import backend
    # importer = RakibolanaOrgPickleImporter()
    # importer.run()
    Importer = EnwiktionaryDumpImporter
    importer = Importer()

    def delete_additional_word_information():
        response = requests.delete(
            backend.backend +
            '/additional_word_information',
            data={})
        assert response.status_code == 204

    delete_additional_word_information()
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
