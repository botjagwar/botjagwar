import re
from logging import getLogger

from api.servicemanager.pgrest import StaticBackend
from ..types import TranslatedDefinition

regexesrep = [
    (r'\{\{l\|en\|(.*)\}\}', '\\1'),
    (r'\{\{vern\|(.*)\}\}', '\\1'),
    (r"\[\[(.*)#(.*)\|?[.*]?\]?\]?", "\\1"),
    (r"\{\{(.*)\}\}", ""),
    (r'\[\[(.*)\|(.*)\]\]', '\\1'),
    (r"\((.*)\)", "")
]
CYRILLIC_ALPHABET_LANGUAGES = 'be,bg,mk,ru,uk'.split(',')
MAX_DEPTH = 1
form_of_part_of_speech_mapper = {
    'ana': 'e-ana',
    'mat': 'e-mat',
    'mpam-ana': 'e-mpam-ana',
    'mpam': 'e-mpam',
}

backend = StaticBackend()
log = getLogger(__file__)


def _delink(line):
    # change link e.g. [[xyz|XYZ#en]] --> xyz
    for link, link_name in re.findall('\\[\\[(\\w+)\\|(\\w+)\\]\\]', line):
        line = line.replace(f'[[{link}|{link_name}]]', link)

    # remove remaining wiki markup
    for c in '{}[]':
        line = line.replace(c, '')

    return line


def _generate_redirections(infos):
    redirection_target = infos.entry
    if infos.language in CYRILLIC_ALPHABET_LANGUAGES:
        for char in "́̀":
            if redirection_target.find(char) != -1:
                redirection_target = redirection_target.replace(char, "")

        if redirection_target.find("æ") != -1:
            redirection_target = redirection_target.replace("æ", "ӕ")

        if infos.entry != redirection_target:
            infos.entry = redirection_target


def try_methods_until_translated(*functions):
    """
    Try one method after another until a translation is provided.
    :param functions: functions to be tried
    :return:
    """

    def _try_methods_until_translated(*args, **kw):
        for function in functions:
            result = function(*args, **kw)
            if isinstance(result, TranslatedDefinition):
                _try_methods_until_translated.__name__ = function.__name__
                return result

    return _try_methods_until_translated
