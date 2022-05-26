from unittest.case import TestCase

from api.importer.wiktionary.en import FurtherReadingImporter


class ApiImporterTester(TestCase):
    Importer = FurtherReadingImporter
    data_exists_index = 1
    data_does_not_exist_index = 1
    corner_case_index = 3
    language = 'fr'
    filename = 'importers/en-wikipage.txt'

    def setUp(self) -> None:
        self.wikipages = ""
        with open('test_data/' + self.filename, 'r') as f:
            sections = f.read().split('----')
            self.wikipages = sections

    def test_get_data_exists(self):
        importer = self.Importer()
        # print(self.wikipages[self.data_exists_index])
        if self.data_exists_index is not None:
            data = importer.get_data('', self.wikipages[self.data_exists_index], self.language)
            self.assertNotEquals(data, [])

    def test_get_data_returns_right_type(self):
        importer = self.Importer()
        if self.data_does_not_exist_index is not None:
            data = importer.get_data('', self.wikipages[self.data_exists_index], self.language)
            self.assertNotEquals(data, list)

