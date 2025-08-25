class Definition(str):
    pass


class UntranslatedDefinition(Definition):

    def __repr__(self):
        return f"{self.__class__.__name__}({self.__str__()})"


class TranslatedDefinition(Definition):
    def __init__(self, translation, languages: list = None):
        if languages is None:
            languages = []
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
        ret = self.__class__.__name__
        ret += f"({self}, "
        ret += f"{self.synonym})" if self.synonym else ")"
        return ret


class ConvergentTranslation(TranslatedDefinition):

    @property
    def is_translated_definition(self):
        return len(self.languages) > 1


class FormOfTranslaton(TranslatedDefinition):
    def __init__(self, translation, languages: list = None):
        super().__init__(translation, languages)
        self.part_of_speech = None
        self.lemma = None

    def is_valid(self):
        return self.lemma != ""


__all__ = [
    "UntranslatedDefinition",
    "TranslatedDefinition",
    "ConvergentTranslation",
    "FormOfTranslaton",
]
