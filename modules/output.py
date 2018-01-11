verbose = False

from modules.database.word import WordDatabase
from _mysql_exceptions import DataError

class Output(object):
    def __init__(self, output_batchfile="translate_batch.txt"):
        self.output_batchfile = file(output_batchfile, 'a')
        self.word_db = WordDatabase()

    def db(self, info):
        "updates database"
        if self.word_db.exists(info.entry, info.language):
            return False
        else:
            try:
                self.word_db.append(info.entry, info.entry_definition, info.part_of_speech, info.language)
                if verbose:
                    print ("voavao ny banky angona")
                return True
            except DataError:
                return False
    
    def batchfile(self, info):
        "return batch format (see doc)"
        string = u"%(entry)s -> %(entry_definition)s -> %(part_of_speech)s -> %(language)s\n" % info.properties
        return string
        
    def wikipage(self, info):
        "returns wikipage string"
        additional_note = u"{{dikantenin'ny dikanteny|%(origin_wiktionary_page_name)s|%(origin_wiktionary_edition)s}}\n" % info.properties
        s = u"""
=={{=%(language)s=}}==
{{-%(part_of_speech)s-|%(language)s}}
'''{{subst:BASEPAGENAME}}''' {{fanononana X-SAMPA||%(language)s}} {{fanononana||%(language)s}}
# %(entry_definition)s """%info.properties
        s = s + additional_note % info.properties
        try:
            return s
        except UnicodeDecodeError:
            return s.decode('utf8')

