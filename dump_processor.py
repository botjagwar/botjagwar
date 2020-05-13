import logging
import sys
from multiprocessing.dummy import Pool as ThreadPool

from lxml import etree

from api.data_caching import FastTranslationLookup
from api.entryprocessor import WiktionaryProcessorFactory
from api.parsers import templates_parser, TEMPLATE_TO_OBJECT
from api.storage import EntryPageFileWriter, MissingTranslationFileWriter
from object_model.word import Entry

language = sys.argv[1] if len(sys.argv) >= 2 else 'en'
target_language = sys.argv[2] if len(sys.argv) >= 3 else 'mg'
count = 0
log = logging.getLogger(__name__)

processor_class = WiktionaryProcessorFactory.create(language)

# Lookup table
translation_lookup_table = FastTranslationLookup(language, 'mg')
translation_lookup_table.build_table()


class Processor(object):
    def __init__(self):
        self.missing_translation_writer = MissingTranslationFileWriter(language)
        self.entry_writer = EntryPageFileWriter(language)

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
                    #print('local >', new_entry)
                    self.entry_writer.add(new_entry)
                    for e in processor.retrieve_translations():
                        e.entry_definition = translation
                        self.entry_writer.add(e)
                        #print('local translation >', e)
            else:
                # RIP cyclomatic complexity.
                translations = []
                pos = entry.part_of_speech
                for definition in entry.entry_definition:
                    try:
                        translation = translation_lookup_table.translate_word(
                            definition, language, entry.part_of_speech)
                    except LookupError:  # Translation couldn't be found in lookup table
                        if entry.part_of_speech in TEMPLATE_TO_OBJECT:
                            try:
                                # Try inflection template parser
                                elements = templates_parser.get_elements(
                                    TEMPLATE_TO_OBJECT[entry.part_of_speech],
                                    definition)
                            except Exception:
                                # add to missing translations
                                self.missing_translation_writer.add(definition)
                            else:
                                if elements:
                                    # part of speech changes to become a form-of part of speech
                                    if not pos.startswith('e-'):
                                        pos = 'e-' + pos
                                    translations.append(elements.to_malagasy_definition())
                    else:
                        translations.append(translation[0])

                if translations:
                    new_entry = Entry(
                        entry=entry.entry,
                        entry_definition=list(set(translations)),
                        language=entry.language,
                        part_of_speech=pos
                    )
                    #print('foreign >', new_entry)
                    self.entry_writer.add(new_entry)

    def load(self, filename):
        """
        Generates a list of 100 XML pages
        :param filename:
        :return:
        """
        input_buffer = ''
        buffers = []
        nthreads = 4
        x = 0
        with open(filename, 'r') as input_file:
            append = False
            for line in input_file:
                if '<page>' in line:
                    input_buffer = line
                    append = True
                elif '</page>' in line:
                    input_buffer += line
                    append = False
                    if x >= nthreads * 100:
                        yield buffers
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
            yield buffers

        self.entry_writer.write()
        self.missing_translation_writer.write()

    def process(self):
        nthreads = 4
        filename = 'user_data/%s.xml' % language
        for xml_buffer in self.load(filename):
            buffers = xml_buffer
            pool = ThreadPool(nthreads)
            pool.map(self.worker, buffers)
            pool.close()
            pool.join()
            del buffers

        self.entry_writer.write()
        self.missing_translation_writer.write()


if __name__ == '__main__':
    p = Processor()
    try:
        p.process()
    finally:
        print(len(p.entry_writer.page_dump), 'elements parsed')
