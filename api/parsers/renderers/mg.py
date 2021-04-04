from api.parsers.constants.mg import GENDER, CASES, NUMBER, MOOD, TENSE, PERSONS, VOICE, DEFINITENESS, POSSESSIVENESS

def render_non_lemma(non_lemma_type):
    def wrapper(non_lemma) -> str:
        explanation = non_lemma_type
        ret = explanation + 'ny teny [[%s]]' % (non_lemma.lemma)
        return ret

    return wrapper

render_romanization = render_non_lemma('rômanizasiôna')
render_alternative_spelling = render_non_lemma('tsipelina hafa')


def render_noun_form(non_lemma) -> str:
    """
    :return: A malagasy language definition in unicode
    """
    explanation = ''
    if non_lemma.possessive in POSSESSIVENESS:
        explanation += POSSESSIVENESS[non_lemma.possessive] + ' '
    if non_lemma.case in CASES:
        explanation += CASES[non_lemma.case] + ' '
    if non_lemma.gender in GENDER:
        explanation += GENDER[non_lemma.gender] + ' '
    if non_lemma.number in NUMBER:
        explanation += NUMBER[non_lemma.number] + ' '
    if non_lemma.definite in DEFINITENESS:
        explanation += DEFINITENESS[non_lemma.definite] + ' '

    if not explanation.strip():
        explanation = 'endriky'

    ret = explanation + 'ny teny [[%s]]' % (non_lemma.lemma)
    return ret


def render_verb_form(non_lemma) -> str:
    """
    :return: A malagasy language definition in unicode
    """
    explanation = ''
    if non_lemma.person in PERSONS:
        explanation += PERSONS[non_lemma.person] + ' '
    if non_lemma.number in NUMBER:
        explanation += NUMBER[non_lemma.number] + ' '

    explanation += 'ny ' if len(explanation.strip()) != 0 else ''
    if non_lemma.mood in MOOD:
        explanation += MOOD[non_lemma.mood] + ' '

    if non_lemma.tense in TENSE:
        explanation += TENSE[non_lemma.tense] + ' '

    explanation += 'ny ' if len(explanation.strip()) != 0 else ''
    if non_lemma.voice in VOICE:
        explanation += VOICE[non_lemma.voice] + ' '

    if not explanation.strip():
        explanation = 'endriky'

    ret = explanation + 'ny matoanteny [[%s]]' % (non_lemma.lemma)
    return ret
