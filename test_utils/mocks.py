import pywikibot

SiteMock = pywikibot.Site

class PageMock(pywikibot.Page):
    def get(self):

    def put(self, **kwargs):
        return