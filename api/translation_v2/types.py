
class UntranslatedDefinition(str):

    def __repr__(self):
        return self.__class__.__name__ + '(' + self.__str__() + ')'


class TranslatedDefinition(str):
    def __init__(self, translation, languages: list = list()):
        self.translation = translation
        self.languages = languages

    def __add__(self, other):
        if isinstance(other, str):
            return self.translation + other

    def __getattr__(self, name):
        if hasattr(self.translation, name):
            return getattr(self.translation, name)

    def __str__(self):
        return self.translation

    def __repr__(self):
        return self.__class__.__name__ + \
            '(' + self.__str__() + ', ' + self.synonym + ')'


class ConvergentTranslation(TranslatedDefinition):

    @property
    def is_translated_definition(self):
        return len(self.languages) > 1


__all__ = [UntranslatedDefinition, TranslatedDefinition]
