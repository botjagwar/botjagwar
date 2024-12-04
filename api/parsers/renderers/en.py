from api.parsers.constants.en import (
    GENDER,
    CASES,
    NUMBER,
    MOOD,
    TENSE,
    PERSONS,
    VOICE,
    DEFINITENESS,
    POSSESSIVENESS,
)


def render_non_lemma(non_lemma_type):
    def wrapper(non_lemma) -> str:
        explanation = non_lemma_type
        ret = f"{explanation} of [[{non_lemma.lemma}]]"
        return ret

    return wrapper


render_romanization = render_non_lemma("romanization")
render_alternative_spelling = render_non_lemma("alternative spelling")


def render_noun_form(non_lemma) -> str:
    """
    :return: A malagasy language definition in unicode
    """
    explanation = ""
    if non_lemma.possessive in POSSESSIVENESS:
        explanation += f"{POSSESSIVENESS[non_lemma.possessive]} "
    if non_lemma.case in CASES:
        explanation += f"{CASES[non_lemma.case]} "
    if non_lemma.gender in GENDER:
        explanation += f"{GENDER[non_lemma.gender]} "
    if non_lemma.number in NUMBER:
        explanation += f"{NUMBER[non_lemma.number]} "
    if non_lemma.definite in DEFINITENESS:
        explanation += f"{DEFINITENESS[non_lemma.definite]} "

    return f"{explanation}of [[{non_lemma.lemma}]]"


def render_verb_form(non_lemma) -> str:
    """
    :return: A malagasy language definition in unicode
    """
    explanation = ""
    if non_lemma.person in PERSONS:
        explanation += f"{PERSONS[non_lemma.person]} "
    if non_lemma.number in NUMBER:
        explanation += f"{NUMBER[non_lemma.number]} "

    explanation += "of the " if explanation.strip() != "" else ""
    if non_lemma.mood in MOOD:
        explanation += f"{MOOD[non_lemma.mood]} "

    if non_lemma.tense in TENSE:
        explanation += f"{TENSE[non_lemma.tense]} "

    explanation += "of the " if explanation.strip() != "" else ""
    if non_lemma.voice in VOICE:
        explanation += f"{VOICE[non_lemma.voice]} "

    return f"{explanation}of [[{non_lemma.lemma}]]"
