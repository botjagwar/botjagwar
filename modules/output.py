import BJDBmodule
verbose = False

class Output(object):
    def __init__(self, output_batchfile="translate_batch.txt"):
        self.output_batchfile = file(output_batchfile, 'a')
        self.word_db = BJDBmodule.WordDatabase()


    def db(self, info):
        "updates database"
        if self.word_db.exists(info['entry'], info['lang']):
            return False
        else:
            self.word_db.append(info['entry'], info['definition'], info['POS'], info['lang'])
            if verbose: print "voavao ny banky angona"
            return True
  
    
    def batchfile(self, info):
        "return batch format (see doc)"
        string = u"%(entry)s -> %(definition)s -> %(POS)s -> %(lang)s\n"%info
        return string    
   
        
    def wikipage(self, info):
        "returns wikipage string"
        additional_note = u""
        if ("olang" in info) and ("origin" in info):
            additional_note = u"{{dikantenin'ny dikanteny|%(origin)s|%(olang)s}}\n"%info
			
        s = u"""
=={{=%(lang)s=}}==
{{-%(POS)s-|%(lang)s}}
'''{{subst:BASEPAGENAME}}''' {{fanononana X-SAMPA||%(lang)s}} {{fanononana||%(lang)s}}
# %(definition)s """%info
        s = s + additional_note%info
        try:
            return s
        except UnicodeDecodeError:
            return s.decode('utf8')

