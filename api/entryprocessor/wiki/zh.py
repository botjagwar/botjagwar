from conf.entryprocessor.languagecodes.zh import LANGUAGE_NAMES
from .en import ENWiktionaryProcessor


class ZHWiktionaryProcessor(ENWiktionaryProcessor):
    """
    Processor for zhwiktionary pages. This is a first iteration of the processor, inspired by `ENWiktionaryProcessor`,
    which should already allow you to parse a good fraction of zhwikt pages.

    WARNING: Unlike frwikt or mgwikt, zhwikt entry formatting is highly irregular. Some entries are formatted like
    enwikt and some others use zhwikt-specific formatting.
    """

    must_have_part_of_speech = True
    empty_definitions_list_if_no_definitions_found = True
    language_section_regex = r"[\n]?==[ ]?([⺀-⺙⺛-⻳⼀-⿕々〇〡-〩〸-〺〻㐀-䶵一-鿃豈-鶴侮-頻並-龎]+)[ ]?==\n"
    all_importers = []

    @property
    def processor_language(self):
        return "zh"

    @property
    def language(self):
        return self.processor_language

    def __init__(self, test=False, verbose=False):
        super(ZHWiktionaryProcessor, self).__init__(test=test, verbose=verbose)
        self.verbose = True
        self.text_set = False
        self.test = test
        self.postran = {
            # Traditional characters
            "動詞": "mat",
            "形容詞": "mpam",
            "連詞": "mpampitohy",
            "限定詞": "mpam",
            "成語": "fomba fiteny",
            "短語": "fomba fiteny",
            "諺語": "ohabolana",
            "數字": "isa",
            "名詞": "ana",
            "粒子": "kianteny",
            "副詞": "tamb",
            "根": "fototeny",
            "代詞": "solo-ana",
            "介詞": "mp.ank-teny",
            "收縮": "fanafohezana",
            "信": "litera",
            "字首": "tovona",
            "羅馬化": "rômanizasiona",
            "後綴": "tovana",
            "象徵": "eva",
            "分詞": "ova-mat",
            "欹": "tenim-piontanana",
            "中綴": "tsofoka",
            # Simplified characters
            "动词": "mat",
            "形容词": "mpam",
            "连词": "mpampitohy",
            "限定词": "mpam",
            "成语": "fomba fiteny",
            "短语": "fomba fiteny",
            "谚语": "ohabolana",
            "数字": "isa",
            "名词": "ana",
            "副词": "fototeny",
            "代词": "mp.ank-teny",
            "介词": "fanafohezana",
            "收缩": "litera",
            "恰当的": "rômanizasiona",
            "罗马化": "eva",
            "后缀": "ova-mat",
            "象征": "tenim-piontanana",
            "分词": "tsofoka",
        }
        self.verbose = verbose
        self.code = LANGUAGE_NAMES

    def lang2code(self, language_name):
        """
        Convert language name to its ISO code (2 or 3 characters
        :param l:
        :return:
        """
        if language_name in self.code:
            return self.code[language_name]
        else:
            return language_name

    def retrieve_translations(self) -> list:
        return []
        # return TranslationImporter().get_data(self.content, self.language, self.title)
