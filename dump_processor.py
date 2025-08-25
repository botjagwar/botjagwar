import logging
import sys
from multiprocessing.pool import Pool as ThreadPool

from lxml import etree

from api.data.caching import FastTranslationLookup
from api.entryprocessor import WiktionaryProcessorFactory
from api.model.word import Entry
from api.parsers.en import templates_parser, TEMPLATE_TO_OBJECT
from api.storage import MissingTranslationFileWriter

# from multiprocessing.dummy import Pool as ThreadPool

log = logging.getLogger(__name__)


class Processor(object):
    def __init__(self, language):
        self.count = 0
        self.missing_translation_writer = MissingTranslationFileWriter(language)
        self.translation_lookup_table = FastTranslationLookup(language, "mg")
        self.translation_lookup_table.build_table()
        self.entry_writer = None  # EntryPageFileWriter(language)
        self.processor_class = None
        self.language = language

    def base_worker(self, xml_buffer: str):
        node = etree.XML(xml_buffer)
        title_node = node.xpath("//title")[0].text
        content_node = node.xpath("//revision/text")[0].text

        return title_node, content_node

    def create_missing_entries(self, xml_buffer: str):
        title_node, content_node = self.base_worker(xml_buffer)

        assert title_node is not None
        if ":" in title_node:
            return
        if self.processor_class is None:
            self.processor_class = WiktionaryProcessorFactory.create("en")
            assert self.processor_class is not None

        processor = self.processor_class()
        processor.set_title(title_node)
        processor.set_text(content_node)
        entries = processor.get_all_entries()

        for entry in entries:
            if entry.language == self.language:
                if self.translation_lookup_table.lookup(entry):
                    translation = self.translation_lookup_table.translate(entry)
                    new_entry = Entry(
                        entry=entry.entry,
                        definitions=translation,
                        language=entry.language,
                        part_of_speech=entry.part_of_speech,
                    )
                    # print('local >', new_entry)
                    self.entry_writer.add(new_entry)
                    for e in processor.retrieve_translations():
                        e.definitions = translation
                        self.entry_writer.add(e)
                        # print('local translation >', e)
            else:
                # RIP cyclomatic complexity.
                translations = []
                pos = entry.part_of_speech
                for definition in entry.definitions:
                    try:
                        translation = self.translation_lookup_table.translate_word(
                            definition, language, entry.part_of_speech
                        )
                    except LookupError:  # Translation couldn't be found in lookup table
                        if entry.part_of_speech in TEMPLATE_TO_OBJECT:
                            try:
                                # Try inflection template parser
                                elements = templates_parser.get_elements(
                                    TEMPLATE_TO_OBJECT[entry.part_of_speech], definition
                                )
                            except Exception:
                                # add to missing translations
                                self.missing_translation_writer.add(definition)
                            else:
                                if elements:
                                    # part of speech changes to become a
                                    # form-of part of speech
                                    if not pos.startswith("e-"):
                                        pos = f"e-{pos}"
                                    translations.append(
                                        elements.to_malagasy_definition()
                                    )
                    else:
                        translations.append(translation[0])

                if translations:
                    new_entry = Entry(
                        entry=entry.entry,
                        definitions=list(set(translations)),
                        language=entry.language,
                        part_of_speech=pos,
                    )
                    # print('foreign >', new_entry)
                    self.entry_writer.add(new_entry)

    def load(self, filename):
        """
        Generates a list of 100 XML pages
        :param filename:
        :return:
        """
        input_buffer = ""
        buffers = []
        nthreads = 4
        x = 0
        buffered = 0
        with open(filename, "r") as input_file:
            append = False
            for line in input_file:
                # line = line.encode('utf8')
                if "<page>" in line:
                    input_buffer = line
                    append = True
                elif "</page>" in line:
                    input_buffer += line
                    append = False
                    if x >= nthreads * 100:
                        yield buffers
                        del buffers
                        buffers = []
                        x = 0
                    else:
                        buffered += 1
                        x += 1
                        if not buffered % 1000:
                            print("buffered:", buffered)
                            print("buffers size:", len(buffers))
                        buffers.append(input_buffer)
                    input_buffer = None
                    del input_buffer
                elif append:
                    input_buffer += line
            yield buffers

        if self.entry_writer is not None:
            try:
                self.entry_writer.write()
            except ValueError as err:
                log.exception("Could not write state.")

        if self.missing_translation_writer is not None:
            self.missing_translation_writer.write()

    def process(self, function="default", filename="default"):
        if function == "default":
            function = self.create_missing_entries
        else:
            assert callable(function)

        if filename == "default":
            filename = f"user_data/{language}.xml"

        def pmap(pool, buffers, lvl=0):
            print(" " * lvl, "buffer size is:", len(buffers))
            try:
                pool.map(function, buffers)
            except Exception:
                if len(buffers) > 2:
                    pmap(pool, buffers[: (len(buffers) - 1) // 2], lvl + 1)
                    pmap(pool, buffers[(len(buffers) - 1) // 2 :], lvl + 1)

        nthreads = 1
        for xml_buffer in self.load(filename):
            buffers = xml_buffer
            pool = ThreadPool(nthreads)
            pmap(pool, buffers)
            pool.close()
            pool.join()
            del buffers

        if self.missing_translation_writer is not None:
            self.missing_translation_writer.write()


if __name__ == "__main__":
    language = sys.argv[1] if len(sys.argv) >= 2 else "en"
    p = Processor(language)
    try:
        p.process()
    finally:
        print(len(p.entry_writer.page_dump), "elements parsed")
