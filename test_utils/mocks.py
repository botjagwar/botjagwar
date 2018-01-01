import pywikibot
from xml.dom import minidom
from modules.decorator import time_this
SiteMock = pywikibot.Site


class PageMock(pywikibot.Page):
    def __init__(self, *args, **kwargs):
        super(PageMock, self).__init__(*args, **kwargs)
        self.filename = "test_data/test_pages_%s.xml" % self.site.lang
        self.parsed = minidom.parse(file(self.filename, 'r'))
        self.pages = self.parsed.getElementsByTagName('page')

    def put(self, **kwargs):
        print (u'Saving page [[%s]]' % self.title())

    def get(self):
        for page in self.pages:
            xml_title = page.getElementsByTagName('title')[0].childNodes[0].nodeValue
            if xml_title == self.title():
                return page.getElementsByTagName('text')[0].childNodes[0].nodeValue

        print u'No page found in "%s"' % self.filename
        return u''


p = PageMock(SiteMock('en','wiktionary'), u'gaon')
e = p.get()