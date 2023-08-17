from api.importer.wiktionary.en import (
    FurtherReadingImporter,
    PronunciationImporter,
    AntonymImporterL5,
    HeadwordImporter,
    TranscriptionImporter,
    AlternativeFormsImporter,
    DerivedTermsImporter,
    ReferencesImporter,
    EtymologyImporter,
    SynonymImporter
)
from . import ApiImporterTester


class TestFurtherReadingImporter(ApiImporterTester):
    Importer = FurtherReadingImporter
    data_exists_index = 0
    data_does_not_exist_index = None
    filename = 'importers/further_reading.wiki'
    language = 'fr'

    def test_corner_case(self):
        importer = self.Importer()
        data = importer.get_data('', self.wikipages[self.data_exists_index], self.language)
        self.assertEqual(len(data), 1)


class TestAlternativeFormsImporter(ApiImporterTester):
    Importer = AlternativeFormsImporter
    data_exists_index = 0
    data_does_not_exist_index = None
    filename = 'importers/alternative_forms.wiki'
    language = 'pl'

    def test_get_data_check_equality(self):
        importer = self.Importer()
        data = importer.get_data('', self.wikipages[self.data_exists_index], 'pl')
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0], '{{alt|pl|fi}}')


class TestAntonymImporter(ApiImporterTester):
    Importer = AntonymImporterL5
    data_exists_index = 6
    data_does_not_exist_index = 0
    filename = 'importers/en-wikipage_references.txt'


class TestDerivedTermsImporter(ApiImporterTester):
    Importer = DerivedTermsImporter
    data_exists_index = 0
    data_does_not_exist_index = None
    filename = 'importers/derived_terms.wiki'
    language = 'vi'

    def test_get_data_exists(self):
        pass


class TestPronunciationImporter(ApiImporterTester):
    Importer = PronunciationImporter
    data_exists_index = 0
    data_does_not_exist_index = None
    filename = 'importers/pronunciation.wiki'
    language = 'ja'

    # def test_get_data_exists(self):
    #     pass


class TestReferencesImporter(ApiImporterTester):
    Importer = ReferencesImporter
    data_exists_index = 0
    data_does_not_exist_index = 2
    filename = 'importers/en-wikipage_references.txt'


class TestEtymologyImporter(ApiImporterTester):
    Importer = EtymologyImporter
    data_exists_index = 6
    data_does_not_exist_index = 1


class TestSynonymImporter(ApiImporterTester):
    Importer = SynonymImporter
    data_exists_index = 6
    data_does_not_exist_index = 1


class TestHeadwordImporter(ApiImporterTester):
    Importer = HeadwordImporter
    data_exists_index = 3
    data_does_not_exist_index = 0

    def test_get_data_exists(self):
        pass


class TestTranscriptionImporter(ApiImporterTester):
    Importer = TranscriptionImporter
    data_exists_index = 3
    data_does_not_exist_index = 0

    def test_get_data_exists(self):
        pass
