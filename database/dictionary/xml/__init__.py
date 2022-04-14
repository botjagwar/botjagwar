from api.serialisers.xml import XMLBuilder

# do NOT import these models here.
# from .model import Word as WordModel
# from .model import Definition as DefinitionModel


class Definition(XMLBuilder):
    def __init__(self, definition):
        super(Definition, self).__init__()
        self.model = definition
        self.xml_node = self.model.__class__.__name__
        self.mapped_variables = [
            ('Id', 'id'),
            ('Definition', 'definition'),
            ('Language', 'language'),
            ('LastModified', 'last_modified'),
        ]

    @property
    def id(self):
        return self.model.id

    @property
    def definition(self):
        return self.model.definition

    @property
    def language(self):
        return self.model.definition_language

    @property
    def last_modified(self):
        return self.model.date_changed.strftime("%Y-%m-%d %H:%M:%S") \
            if self.model.date_changed is not None else ''


class Word(XMLBuilder):
    def __init__(self, word):
        super(Word, self).__init__()
        self.model = word
        self.xml_node = self.model.__class__.__name__
        self.mapped_variables = [
            ('Id', 'id'),
            ('Word', 'word'),
            ('Language', 'language'),
            ('PartOfSpeech', 'part_of_speech'),
            ('LastModified', 'last_modified'),
            ('AdditionalData', 'additional_data'),
        ]

    @property
    def type(self):
        return self.model.__class__.__name__

    @property
    def id(self):
        return self.model.id

    @property
    def word(self):
        return self.model.word

    @property
    def language(self):
        return self.model.language

    @property
    def part_of_speech(self):
        return self.model.part_of_speech

    @property
    def last_modified(self):
        return self.model.date_changed.strftime("%Y-%m-%d %H:%M:%S")

    @property
    def additional_data(self):
        data = {}
        if self.model.additional_data:
            for adt, adi in self.model.additional_data.items():
                if adt in data:
                    data[adt].append(adi)
                else:
                    data[adt] = [adi]

        return data
