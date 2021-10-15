import xml.etree.cElementTree as ElementTree

from sqlalchemy.orm.exc import DetachedInstanceError

from object_model.word import Entry


# do NOT import these models here.
# from .model import Word as WordModel
# from .model import Definition as DefinitionModel


class Definition(object):
    def __init__(self, definition):
        self.model = definition

    def serialise(self):
        """Helper function which uses the serialiser"""
        definition_data = {
            'type': self.model.__class__.__name__,
            'id': self.model.id,
            'definition': self.model.definition,
            'language': self.model.definition_language,
            'last_modified':
                self.model.date_changed.strftime("%Y-%m-%d %H:%M:%S")
                if self.model.date_changed is not None else ''
        }
        return definition_data

    def serialise_with_words(self):
        definition_data = self.serialise()
        definition_data['words'] = [
            Word(word).serialise_without_definition() for word in self.model.words]
        return definition_data

    def serialise_xml(self):
        root = ElementTree.Element(self.model.__class__.__name__)
        json_dict = self.model.serialise()
        for node, value in json_dict.items():
            ElementTree.SubElement(root, node).text = str(value)

        return root


class Word(object):
    def __init__(self, word):
        self.model = word

    def serialise(self):
        word_data = self.serialise_without_definition()
        word_data['definitions'] = [
            Definition(definition).serialise() for definition in self.model.definitions]
        return word_data

    def serialise_xml(self):
        root = ElementTree.Element(self.model.__class__.__name__)
        word_data = self.model.serialise_without_definition()
        definitions = ElementTree.SubElement(root, 'Definitions')
        for definition in self.model.definitions:
            definitions.append(definition.serialise_xml())

        for node, value in word_data.items():
            ElementTree.SubElement(root, node).text = str(value)

        return root

    def serialise_to_entry(self, definitions_language=['mg']):
        definition = [definition.definition
                      for definition in self.model.definitions
                      if definition.definition_language in definitions_language]
        return Entry(
            entry=self.model.word,
            part_of_speech=self.model.part_of_speech,
            entry_definition=definition,
            language=self.model.language,
        )

    def serialise_without_definition(self):
        last_modified = ''
        try:
            if self.model.date_changed:
                last_modified = self.model.date_changed.strftime(
                    "%Y-%m-%d %H:%M:%S")
        except DetachedInstanceError:
            pass

        word_data = {
            'type': self.model.__class__.__name__,
            'id': self.model.id,
            'word': self.model.word,
            'language': self.model.language,
            'part_of_speech': self.model.part_of_speech,
            'last_modified': last_modified,
            'additional_data': self.model.additional_data
        }
        if self.model.additional_data:
            for adt, adi in self.model.additional_data:
                if adt.type in word_data['additional_data']:
                    word_data['additional_data'][adt.type].append(adi)
                else:
                    word_data['additional_data'][adt.type] = [adi]

        return word_data
