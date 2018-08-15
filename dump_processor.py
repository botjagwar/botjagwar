import logging
import sys
from multiprocessing.dummy import Pool as ThreadPool

from lxml import etree

from api.data_caching import FastWordLookup, FastTranslationLookup
from api.entry_page_file import EntryPageFileWriter
from api.entryprocessor import WiktionaryProcessorFactory
from object_model.word import Entry

language = sys.argv[1] if len(sys.argv) >= 2 else 'en'
target_language = sys.argv[2] if len(sys.argv) >= 3 else 'mg'
count = 0
log = logging.getLogger(__name__)

processor_class = WiktionaryProcessorFactory.create(language)

# Lookup table
lookup_table = FastWordLookup()
lookup_table.build_fast_word_tree()
translation_lookup_table = FastTranslationLookup(language, 'mg')
translation_lookup_table.build_table()


class Processor(object):
    def __init__(self):
        self.writer = EntryPageFileWriter(language)

    def worker(self, xml_buffer):
        global count
        node = etree.XML(str(xml_buffer))
        title_node = node.xpath('//title')[0].text
        content_node = node.xpath('//revision/text')[0].text

        assert title_node is not None
        if ':' in title_node:
            return

        processor = processor_class()
        processor.set_title(title_node)
        processor.set_text(content_node)
        entries = processor.getall()

        for entry in entries:
            if entry.language == language:
                if translation_lookup_table.lookup(entry):
                    translation = translation_lookup_table.translate(entry)
                    new_entry = Entry(
                        entry=entry.entry,
                        entry_definition=translation,
                        language=entry.language,
                        part_of_speech=entry.part_of_speech
                    )
                    self.writer.add(new_entry)
            else:
                try:
                    translation = translation_lookup_table.translate_word(
                        entry.entry_definition[0], language, entry.part_of_speech)
                except LookupError:
                    pass
                else:
                    if translation:
                        new_entry = Entry(
                            entry=entry.entry,
                            entry_definition=translation,
                            language=entry.language,
                            part_of_speech=entry.part_of_speech
                        )
                        self.writer.add(new_entry)

    def process(self):
        input_buffer = ''
        buffers = []
        nthreads = 15
        x = 0
        with open('user_data/%s.xml' % language, 'r') as input_file:
            append = False
            for line in input_file:
                if '<page>' in line:
                    input_buffer = line
                    append = True
                elif '</page>' in line:
                    input_buffer += line
                    append = False
                    if x >= nthreads*100:
                        pool = ThreadPool(nthreads)
                        pool.map(self.worker, buffers)
                        pool.close()
                        pool.join()
                        del buffers
                        buffers = []
                        x = 0
                    else:
                        x += 1
                        buffers.append(input_buffer)
                    input_buffer = None
                    del input_buffer
                elif append:
                    input_buffer += line

        self.writer.write()


if __name__ == '__main__':
    p = Processor()
    try:
        p.process()
    finally:
        print(len(p.writer.page_dump), 'elements parsed')