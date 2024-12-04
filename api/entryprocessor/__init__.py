import inspect
import sys
import warnings

from . import wiki
from .wiki.base import WiktionaryProcessor
from .wiki.de import DEWiktionaryProcessor
from .wiki.en import ENWiktionaryProcessor
from .wiki.fr import FRWiktionaryProcessor
from .wiki.mg import MGWiktionaryProcessor
from .wiki.nl import NLWiktionaryProcessor
from .wiki.pl import PLWiktionaryProcessor
from .wiki.ru import RUWiktionaryProcessor
from .wiki.sv import SVWiktionaryProcessor
from .wiki.vo import VOWiktionaryProcessor
from .wiki.zh import ZHWiktionaryProcessor

data_file = "/opt/botjagwar/conf/entryprocessor/"
verbose = True


class WiktionaryProcessorFactory(object):
    def __init__(self):
        pass

    @staticmethod
    def create(language):
        assert type(language) in [str], type(language)
        ct_module = sys.modules[__name__]
        classes = inspect.getmembers(ct_module, inspect.isclass)
        processors = [x for x in classes if x[0].endswith("WiktionaryProcessor")]
        language_class_name = f"{language.upper()}WiktionaryProcessor"

        for current_class_name, processor_class in processors:
            if current_class_name == language_class_name:
                return processor_class

        warnings.warn("Tsy nahitana praosesera: '%s'" % language_class_name, Warning)
        return WiktionaryProcessor


__all__ = ["WiktionaryProcessorFactory"]
