# do NOT import these models here.
# from .model import Word as WordModel
# from .model import Definition as DefinitionModel

class Word(object):
    def __init__(self, model):
        self.model = model

    def set_definition(self, definitions: list):
        """
        Replace the existing definition set by the one given in argument
        :param definition:
        :return:
        """
        for d in definitions:
            if not isinstance(d, self.model.__class__):
                raise TypeError("A Definition object is expected.")

        self.model.definitions = definitions

    def add_definition(self, definition):
        if definition not in self.model.definitions:
            self.model.definitions.append(definition)

    def remove_definition(self, definition):
        if definition not in self.model.definitions:
            self.model.definitions.remove(definition)


class Definition(object):
    def __init__(self, model):
        self.model = model

