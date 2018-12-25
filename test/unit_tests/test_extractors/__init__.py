from api.extractors.site_extractor import RakibolanaSiteExtactor
from api.extractors.site_extractor import SiteExtractorException
from api.extractors.site_extractor import TenyMalagasySiteExtractor


def test_teny_malagasy():
    extractor = TenyMalagasySiteExtractor()
    for word in [
        'fandraisana',
        'fantsika',
        'miroahana'
    ]:
        try:
            print(word, extractor.lookup(word))
        except SiteExtractorException:
            continue


def test_rakibolana():
    extractor = RakibolanaSiteExtactor()
    for word in [
        'fandraisana',
        'ray',
        'fantsika',
        'miroahana'
    ]:
        try:
            print(word, extractor.lookup(word))
        except SiteExtractorException:
            continue