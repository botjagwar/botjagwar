from api.serialisers.json import JSONBuilder

# do NOT import these models here.
# from .model import Word as WordModel
# from .model import Definition as DefinitionModel


class Definition(JSONBuilder):
    def __init__(self, definition):
        super(Definition, self).__init__()
        self.model = definition
        self.mapped_variables = [
            ('type', 'type'),
            ('id', 'id'),
            ('definition', 'definition'),
            ('language', 'language'),
            ('last_modified', 'last_modified'),
        ]

    @property
    def words(self) -> list:
        return [
            Word(word).serialise_without_definition()
            for word in self.model.words
        ]

    def serialise_with_words(self):
        self.mapped_variables.append(('words', 'words'))
        return self.serialise()

    @property
    def type(self):
        return self.model.__class__.__name__

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


class Word(JSONBuilder):
    def __init__(self, word):
        super(Word, self).__init__()
        self.model = word
        self.mapped_variables = [
            ('type', 'type'),
            ('id', 'id'),
            ('word', 'word'),
            ('language', 'language'),
            ('part_of_speech', 'part_of_speech'),
            ('last_modified', 'last_modified'),
            ('additional_data', 'additional_data'),
        ]

    def serialise_without_definition(self):
        data = self.serialise()
        del data['definitions']
        return data

    @property
    def type(self) -> str:
        return self.model.__class__.__name__

    @property
    def id(self):
        return self.model.id

    @property
    def word(self) -> str:
        return self.model.word

    @property
    def language(self) -> str:
        return self.model.language

    @property
    def part_of_speech(self) -> str:
        return self.model.part_of_speech

    @property
    def last_modified(self) -> str:
        return self.model.date_changed.strftime("%Y-%m-%d %H:%M:%S")

    @property
    def additional_data(self) -> dict:
        data = {}
        if self.model.additional_data:
            for adt, adi in self.model.additional_data.items():
                if adt in data:
                    data[adt].append(adi)
                else:
                    data[adt] = [adi]

        return data
