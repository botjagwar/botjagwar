import pywikibot

SiteMock = pywikibot.Site

class PageMock(pywikibot.Page):
    def put(self, **kwargs):
        return