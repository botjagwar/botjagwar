"""
use a mg.wiktionary.org dump and import all its contents to the botjagwar database.
"""
import time
from copy import deepcopy

from lxml import etree

# import pywikibot
from api.entryprocessor import WiktionaryProcessorFactory
from api.output import Output
from dump_processor import Processor


class MgWiktionaryDumpImporter():
    def __init__(self, file_name):
        self.file_name = file_name
        self.processor = Processor()
        self.EntryProcessor = WiktionaryProcessorFactory.create('mg')
        self.entryprocessor = self.EntryProcessor()

    def load(self):
        for _100_page_batch in self.processor.load(self.file_name):
            for xml_page in _100_page_batch:
                yield xml_page

    def process(self, xml_page):
        #print("processing page xml")
        node = etree.XML(str(xml_page))
        title_node = node.xpath('//title')[0].text
        content_node = node.xpath('//revision/text')[0].text
        self.entryprocessor.set_title(title_node)
        self.entryprocessor.set_text(content_node)
        dt = time.time()
        for entry in self.entryprocessor.getall():
            c = 0
            for definitions in entry.entry_definition:
                for definition in definitions.split(','):
                    new_entry = deepcopy(entry)
                    for char in '[]=':
                        definition = definition.replace(char, '')

                    new_entry.entry_definition = [definition.strip()]
                    Output().db(new_entry)
                    c += 1

            if not c >= 100:
                q = 60. * c / (time.time() - dt)
                print('{} wpm'.format((q,)))
                c = 0
                dt = time.time()


    def run(self):
        for xml_page in self.load():
            self.process(xml_page)


if __name__ == '__main__':
    bot = MgWiktionaryDumpImporter('mgwiktionary-20200501-pages-articles.xml')
    bot.run()
