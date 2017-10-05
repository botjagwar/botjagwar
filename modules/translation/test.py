
from core import Translation

data_file = "conf/dikantenyvaovao/"


class TestTranslation(object):
    def test_translate_english(self):
        listPages = [""]
        test = Translation()
        listpagestring = parseErrlog()
        for page in listpagestring:
            page = page.decode('utf8')
            test.process_wiktionary_page('en', Page)
