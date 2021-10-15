from xml.dom import minidom

import pywikibot

from api.decorator import time_this

SiteMock = pywikibot.Site


class PageMock(pywikibot.Page):
    def __init__(self, *args, **kwargs):
        super(PageMock, self).__init__(*args, **kwargs)
        self.filename = "test_data/test_pages_%s.xml" % self.site.lang
        self.parsed = minidom.parse(open(self.filename, 'r'))
        self.pages = self.parsed.getElementsByTagName('page')

    def put(self, newtext, summary=None, watch=None, minor=True, botflag=None,
            force=False, asynchronous=False, callback=None, **kwargs):
        print(('Saving page [[%s]] through put' % self.title()))

    def save(self, summary=None, watch=None, minor=True, botflag=None,
             force=False, asynchronous=False, callback=None,
             apply_cosmetic_changes=None, quiet=False, **kwargs):
        print(('Saving page [[%s]] through save' % self.title()))

    def _save(self, summary=None, watch=None, minor=True, botflag=None,
              cc=None, quiet=False, **kwargs):
        print(('Saving page [[%s]] through save' % self.title()))

    @time_this('Page.get() method mock')
    def get(self, force=False, get_redirect=False, sysop=False):
        for page in self.pages:
            xml_title = page.getElementsByTagName(
                'title')[0].childNodes[0].nodeValue
            if xml_title == self.title():
                return page.getElementsByTagName(
                    'text')[0].childNodes[0].nodeValue

        print(('No page %s found in "%s"' % (self.title(), self.filename)))
        return ''


p = PageMock(SiteMock('en', 'wiktionary'), 'gaon')
e = p.get()
