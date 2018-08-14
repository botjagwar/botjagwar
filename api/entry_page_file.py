import pickle
from threading import Lock

from api.decorator import critical_section, singleton
from object_model.word import Entry

cs_lock = Lock()


@singleton
class EntryPageFileWriter(object):
    def __init__(self, language):
        self.page_dump_file = open('user_data/dump-%s.pkl' % language, 'wb')
        self.page_dump = {}
        self.counter = 0

    @critical_section(cs_lock)
    def add(self, entry: Entry):
        self.counter += 1
        if self.counter % 250 == 0:
            print(self.counter)

        if entry.entry in self.page_dump:
            if entry not in self.page_dump[entry.entry]:
                self.page_dump[entry.entry].append(entry)
        else:
            self.page_dump[entry.entry] = [entry]

    def write(self):
        pickle.dump(self.page_dump, self.page_dump_file, pickle.HIGHEST_PROTOCOL)
        self.page_dump_file.close()


@singleton
class EntryPageFileReader(object):
    def __init__(self, language):
        self.page_dump_file = open('user_data/dump-%s.pkl' % language, 'rb')
        self.page_dump = {}

    def read(self):
        self.page_dump = pickle.load(self.page_dump_file)
