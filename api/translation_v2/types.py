
class UntranslatedDefinition(str):

    def __repr__(self):
        return 'translated(' + self.__str__() + ')'


class TranslatedDefinition(str):
    @property
    def translation_path(self):
        return self.translation_path

    def __repr__(self):
        return 'untranslated(' + self.__str__() + ')'


__all__ = [UntranslatedDefinition, TranslatedDefinition]
