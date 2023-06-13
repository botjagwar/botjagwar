class UnhandledTypeError(TypeError):
    pass


class UnsupportedLanguageError(Exception):
    pass


class TranslationError(Exception):
    pass


class TranslatedPagePushError(TranslationError):
    pass
