import re
from logging import getLogger

import requests

from api.servicemanager.pgrest import StaticBackend

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


def _look_up_dictionary(w_language, w_part_of_speech, w_word):
    params = {
        'language': 'eq.' + w_language,
        'part_of_speech': 'eq.' + w_part_of_speech,
        'word': 'eq.' + w_word
    }
    resp = requests.get(backend.backend + '/json_dictionary', params=params)
    data = resp.json()
    return data


def _look_up_word(language, part_of_speech, word):
    params = {
        'language': 'eq.' + language,
        'part_of_speech': 'eq.' + part_of_speech,
        'word': 'eq.' + word
    }
    log.debug(params)
    resp = requests.get(backend.backend + '/word', params=params)
    data = resp.json()
    return data


def _generate_redirections(infos):
    redirection_target = infos.entry
    if infos.language in CYRILLIC_ALPHABET_LANGUAGES:
        for char in "́̀":
            if redirection_target.find(char) != -1:
                redirection_target = redirection_target.replace(char, "")
        if redirection_target.find("æ") != -1:
            redirection_target = redirection_target.replace("æ", "ӕ")
        if infos.entry != redirection_target:
            # page = pwbot.Page(pwbot.Site(WORKING_WIKI_LANGUAGE, 'wiktionary'), infos.entry)
            # if not page.exists():
            # page.put_async("#FIHODINANA [[%s]]" % redirection_target,
            # "fihodinana")
            infos.entry = redirection_target
