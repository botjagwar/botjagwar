
class UntranslatedDefinition(str):
    pass


class TranslatedDefinition(str):
    @property
    def translation_path:
        return []
