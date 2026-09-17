import configparser
import re
from pathlib import Path
from typing import Dict, Set


def fix_repeated_subsentence(sentence: str) -> str:
    """Remove repeated subsentences from a sentence."""
    words = sentence.split()
    n = len(words)

    for size in range(n // 2, 0, -1):
        for i in range(n - size * 3 + 1):
            subsentence = " ".join(words[i: i + size])
            pattern = rf"({re.escape(subsentence)})(?:\s+\1){{2,}}"

            if re.search(pattern, sentence):
                sentence = re.sub(pattern, r"\1 ", sentence)
                sentence = re.sub(r"\s{2,}", " ", sentence)
                words = sentence.split()
                n = len(words)
                break

    return sentence.strip()


class ExcessForeignWords(Exception):
    """Raised when too many English or French words remain in the definition."""


BASE_DIR = Path(__file__).resolve().parent
EN_WHITELIST: Set[str]
FR_WHITELIST: Set[str]
CONFIG_PATH = BASE_DIR.parents[3] / "conf" / "config.ini"


def _load_whitelist(path: Path) -> Set[str]:
    return {
        line.strip().split(" -> ")[0].replace('-', '')
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    } if path.exists() else set()


def _load_translation_dict(path: Path) -> Dict[str, str]:
    translations: Dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "->" in line:
                src, tgt = [part.strip() for part in line.split("->", 1)]
                if src == tgt:
                    continue
                translations[src.lower()] = tgt
    return translations


EN_WHITELIST = set(_load_whitelist(BASE_DIR / "en-whitelist"))
FR_WHITELIST = set(_load_whitelist(BASE_DIR / "fr-whitelist"))
TRANSLATION_DICT_auto = set(_load_whitelist(BASE_DIR / "mg-whitelist"))
TRANSLATION_DICT_override = set(_load_whitelist(BASE_DIR / "mg-whitelist-override"))
TRANSLATION_DICT_auto.update(TRANSLATION_DICT_override)
TRANSLATION_DICT_mg = TRANSLATION_DICT_auto

def remove_empty_translations(definition: str):
    """Remove empty translations from a definition string."""
    if definition in ['ny', 'hoe']:
        return None

    return definition

def remove_definition_if_too_many_foreign_words(definition: str):
    if not definition:
        return None

    split_defn = re.findall(
        r"\b[\w+]+\b",
        definition
        .replace("'", "' ")
        .replace("-", "- ")
        .lower()
    )
    remaining = [
        w
        for w in split_defn
        if w not in TRANSLATION_DICT_mg
    ]

    config = configparser.ConfigParser(interpolation=None)
    config.read(CONFIG_PATH)
    threshold = config.getint("nllb", "remaining_words_threshold", fallback=0)

    if len(remaining) > threshold:
        return None

    # A translation in which most words are foreign is an untranslated
    # definition (e.g. the model echoed the source text); never publish it.
    if split_defn and len(remaining) > len(split_defn) / 2:
        return None

    return definition


__all__ = ["fix_repeated_subsentence", "remove_definition_if_too_many_foreign_words", "remove_empty_translations", "ExcessForeignWords"]
