import logging
import sys
from multiprocessing.dummy import Pool as ThreadPool

from lxml import etree

from api.data_caching import FastWordLookup, FastTranslationLookup
from api.entryprocessor import WiktionaryProcessorFactory
from api.output import Output
from api.translation.core import Translation
from object_model.word import Entry

language = sys.argv[1]
translation = Translation()
count = 0
log = logging.getLogger(__name__)
output = Output()

processor_class = WiktionaryProcessorFactory.create(language)

# Lookup table
lookup_table = FastWordLookup()
lookup_table.build_fast_word_tree()
translation_lookup_table = FastTranslationLookup(language, 'mg')
translation_lookup_table.build_table()


def worker(xml_buffer):
    global count
    node = etree.XML(str(xml_buffer))
    title_node = node.xpath('//title')[0].text
    content_node = node.xpath('//revision/text')[0].text

    assert title_node is not None
    if ':' in title_node:
        return

    print(count, ' >> ', title_node, ' <<')
    processor = processor_class()
    processor.set_title(title_node)
    processor.set_text(content_node)
    entries = processor.getall()

    for entry in entries:
        if translation_lookup_table.lookup(entry):
            translation = translation_lookup_table.translate(entry)
            new_entry = Entry(
                entry=entry.entry,
                entry_definition=translation,
                language=entry.language,
                part_of_speech=entry.part_of_speech
            )
            print(new_entry)
            output.db(new_entry)


def process_dump():
    input_buffer = ''
    buffers = []
    nthreads = 40
    x = 0
    with open('user_data/%s.xml' % language,'r') as input_file:
        append = False
        for line in input_file:
            if '<page>' in line:
                input_buffer = line
                append = True
            elif '</page>' in line:
                input_buffer += line
                append = False
                if x >= nthreads:
                    pool = ThreadPool(nthreads)
                    pool.map(worker, buffers)
                    pool.close()
                    pool.join()
                    del buffers
                    buffers = []
                    x = 0
                else:
                    x += 1
                    buffers.append(input_buffer)
                input_buffer = None
                del input_buffer #probably redundant...
            elif append:
                input_buffer += line


if __name__ == '__main__':
    process_dump()