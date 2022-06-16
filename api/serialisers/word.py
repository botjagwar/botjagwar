from .json import JSONBuilder


class Entry(JSONBuilder):
    def __init__(self, model):
        super(Entry, self).__init__()
        self.model = model
        self.mapped_variables = [
            ('entry', 'entry'),
            ('part_of_speech', 'part_of_speech'),
            ('language', 'language'),
            ('definitions', 'definitions'),
            ('references', 'references'),
            ('additional_data', 'additional_data'),
        ]

    @property
    def entry(self):
        return self.model.entry

    @property
    def definitions(self):
        return self.model.definitions

    @property
    def part_of_speech(self):
        return self.model.part_of_speech

    @property
    def language(self):
        return self.model.language

    @property
    def additional_data(self):
        return self.model.additional_data

    @property
    def references(self):
        return self.model.references


class Translation(JSONBuilder):
    def __init__(self, model):
        super(Translation, self).__init__()
        self.model = model
        self.mapped_variables = [
            ('word', 'word'),
            ('part_of_speech', 'part_of_speech'),
            ('language', 'language'),
            ('definition', 'definition'),
        ]

    @property
    def word(self):
        return self.model.word

    @property
    def part_of_speech(self):
        return self.model.part_of_speech

    @property
    def language(self):
        return self.model.language

    @property
    def definition(self):
        return self.model.definition
