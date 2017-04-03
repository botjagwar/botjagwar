
class Entry(object):
    """
    Class used for a better polymorphism of entry
    """
    def __init__(self, inputVar=None):
        """
        @inputVar can either be None, a tuple like ( unicode, unicode, unicode, unicode ) or a unicode string.
        
        if a tuple :
            1st is entry
            2nd is definition
            3rd is part of speech
            4th is language code
        
        if a string:
            "entry->definition->partofspeech->language"
            
        if None
            entry has to be initialised by calling the required methods fromEntryTuple or fromBatchString.
            if this has not been done, toBatchString and toDictionary will raise a ValueError
        """
        self.entry = u''
        self.wtype = u''
        self.definition = u''
        self.initialised = False
        if type(inputVar) is tuple:
            self.fromEntryTuple(inputVar)
        elif type(inputVar) is str:
            self.fromBatchString(inputVar)
            
    def __repr__(self):
        return u"Entry{%s}"%self.entry
    
    def fromEntryTuple(self, entrytuple):
        self.entry = entrytuple[0]
        self.definition = entrytuple[1]
        self.wtype = entrytuple[2]
        self.language = entrytuple[3]
        self.initialised = True
        
    def fromBatchString(self, batchstring):  
        batchstring = batchstring.decode('utf8')[:-1]
        inputVar = batchstring.split(u" -> ")
        self.entry = inputVar[0]
        self.definition = inputVar[1]
        self.wtype = inputVar[2]
        self.language = inputVar[3]
        self.initialised = True
    
    def manual(self, entry, wtype, definition, language):                
        self.entry = entry
        self.definition = definition
        self.wtype = wtype
        self.language = language
        self.initialised = True
        
    def toBatchString(self):   
        if self.initialised:
            return u"%s -> %s -> %s -> %s\n"%(self.entry, self.definition, self.wtype, self.language)
        else:
            raise ValueError("Error: the class must be initialised!!")
    
    def toDictionary(self):
        if self.initialised:
            return {'entry':self.entry,
                'definition':self.definition,
                'type':self.wtype}
        else:
            raise ValueError("Error: the class must be initialised!!")
    
    def toWikipage(self):
        if self.initialised:
            return (self.entry , u"""=={{=%s=}}==
{{-%s-|%s}}
'''{{subst:BASEPAGENAME}}''' {{pron||%s}}
# %s"""%(self.language, self.wtype, self.language, self.language, self.definition))
        else:
            raise ValueError("Error: the class must be initialised!!")


class EntryBatchHandler(object):
    """
    Handles the batch reading and writing. 
    Can also be used as a lightweight solution for running Bot-Jagwar without the need of a dedicated database.    
    """
    def __init__(self, filename, mode):
        """
        @filename must be a valid filename for reading, located in the data subdirectory 
        @mode takes the same parameter as the second argument in file() instantiation (most common ar 'r' and 'w')
        """
        self.filename = filename
        self.file = file(u"data/" +filename, mode)
        self.entrylist = []
        
    def add(self, entry):
        """
        @entry an Entry object containing required information
        """
        self.entrylist.append( Entry(entry) )
    
    
    def read(self):
        for item in self.file.readlines():
            self.add(item)
            yield Entry(item)
    
    
    def build_batch(self, output_file='same'):
        """
        Builds all the list that has been added to the local file
        @output_file if has the value 'same', then the same filename as the one specified at instantiation will be kept
        and data in the old file will be overwritten. If different, a new file will be created at the data subdirectory.        
        """
        if output_file=='same':
            self.file.close()
            self.file = file(self.filename, 'w')
        else:
            self.file = file(output_file, 'w')
            
        for item in self.entrylist:
            self.file.write(item.toBatchString())
        
        self.file.close()
    
