import logging
import sys
from multiprocessing.dummy import Pool as ThreadPool

from lxml import etree

from api.output import Output
from api.translation.core import Translation

language = sys.argv[1]
translation = Translation()
count = 0
log = logging.getLogger(__name__)
output = Output()


def worker(xml_buffer):
    global count
    node = etree.XML(str(xml_buffer))
    title_node = node.xpath('//title')[0].text
    print(count, ' >> ', title_node, ' <<')
    content_node = node.xpath('//revision/text')[0].text

    assert title_node is not None
    if ':' in title_node:
        return

    translation.process_wiktionary_wikitext(title_node, language, content_node)


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