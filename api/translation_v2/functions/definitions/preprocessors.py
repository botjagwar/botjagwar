import logging
import re

from api.entryprocessor.wiki.base import WiktionaryProcessorException

log = logging.getLogger(__name__)


def drop_definitions_with_labels(*labels):
    def _drop_definitions(definition) -> str:
        for label in labels:
            # labels (xxx, yy, zzzzz) using find:
            if definition.find(f'({label})') != -1:
                return ''
            elif definition.find(f', {label})') != -1:
                return ''
            elif definition.find(f'({label},') != -1:
                return ''
            elif definition.find(f', {label},') != -1:
                return ''

        return definition

    return _drop_definitions


def handle_gloss_templates(definition):
    refined = definition

    # Handle {{gloss}}
    gloss_template_begin = refined.find('{{gloss|')
    if gloss_template_begin != -1:
        gloss_template_begin += len('{{gloss|')
        gloss_template_end = refined.find('}}', gloss_template_begin)
        refined = refined[gloss_template_begin:gloss_template_end]

    # handle {{g|}} templates using re.sub
    if refined.find('{{g|') != -1:
        r_begin = refined.find('{{g|')
        r_end = refined.find('}}', r_begin)
        if r_end == -1:
            refined = refined.replace(refined[r_begin:], '')
        else:
            refined = refined.replace(refined[r_begin:r_end + 2], '')

    return refined


def handle_link(refined):
    # Handle [[]] links
    refined = re.sub(r'\[\[([\w ]+)\|[\w ]+\]\]', '\\1', refined)
    refined = re.sub(r'\[\[([\w ]+)#([\w ]+)\|([\w ]+)\]\]', '\\3', refined)
    refined = re.sub(r'\[\[([\w ]+)\]\]', '\\1', refined)
    return refined


def delete_all_templates(refined):
    while refined.find('{{') != -1:
        template_begin = refined.find('{{')
        template_end = refined.find('}}', template_begin)
        if template_end == -1:
            template_end = refined.find('}', template_begin)
            if template_end == -1:
                refined = refined[:template_begin] + refined[template_end + 2:]
            else:
                refined = refined[:template_begin]
        else:
            refined = refined[:template_begin] + refined[template_end + 2:]

    unwanted_character = False
    for character in "{}[]|":
        if character in refined:
            unwanted_character = True
            break

    if unwanted_character:
        raise WiktionaryProcessorException("Refined definition still has unwanted characters : '" + character + "'")

    return refined


def handle_label_templates(definition):
    if definition.startswith('{{label') or definition.startswith('{{lb|'):
        pipe_1 = definition.find('|')
        pipe_2 = definition.find('|', pipe_1 + 1)

        label_text_begin = pipe_2
        label_text_end = definition.find('}', label_text_begin)

        label_text = definition[label_text_begin:label_text_end]
        full_label_text = definition[:label_text_end + 2]
        reformatted_labels = '(' + label_text.lstrip('|').replace('|', ', ') + ') '
    else:
        reformatted_labels = ''
        full_label_text = ''

    refined = reformatted_labels + definition.replace(full_label_text, '')
    refined = refined.replace(', usually, ', ', usually ')
    refined = refined.replace(', _, ', ' ')

    # Handle {{l|en|}} links
    refined = re.sub(r'\{\{l\|en\|([\w ]+)\}\}', '\\1', refined)

    return refined


def refine_definition(definition, remove_all_templates=False) -> str:
    """
    Refine definition to remove unwanted characters, templates, etc.
    We also rename label templates into a more readable format.

    :param definition: definition to refine
    :param remove_all_templates: whether to delete all templates or not
    :return: refined definition.
    """
    # handle {{lb}} template calls
    definition = definition.strip()

    refined = handle_label_templates(definition)
    refined = handle_gloss_templates(refined)
    refined = handle_link(refined)

    # Remove all remaining templates using find,
    # cannot enable this as it has an impact on form-of definitions
    if remove_all_templates:
        refined = delete_all_templates(refined)

    refined = refined.replace('\t', '')
    refined = refined.replace('\n', ' ')
    refined = refined.strip()

    if refined.strip() and refined.strip('.'):
        return refined
    else:
        return ''


__all__ = ['refine_definition', 'drop_definitions_with_labels']