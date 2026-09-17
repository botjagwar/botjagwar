import inspect
import sys
import warnings

from . import wiki as wiki
from .wiki.base import WiktionaryProcessor
from .wiki.de import DEWiktionaryProcessor as DEWiktionaryProcessor
from .wiki.en import ENWiktionaryProcessor as ENWiktionaryProcessor
from .wiki.fr import FRWiktionaryProcessor as FRWiktionaryProcessor
from .wiki.mg import MGWiktionaryProcessor as MGWiktionaryProcessor
from .wiki.nl import NLWiktionaryProcessor as NLWiktionaryProcessor
from .wiki.pl import PLWiktionaryProcessor as PLWiktionaryProcessor
from .wiki.ru import RUWiktionaryProcessor as RUWiktionaryProcessor
from .wiki.sv import SVWiktionaryProcessor as SVWiktionaryProcessor
from .wiki.vo import VOWiktionaryProcessor as VOWiktionaryProcessor
from .wiki.zh import ZHWiktionaryProcessor as ZHWiktionaryProcessor

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

        warnings.warn(f"Tsy nahitana praosesera: '{language_class_name}'", Warning)
        return WiktionaryProcessor


__all__ = ["WiktionaryProcessorFactory"]
