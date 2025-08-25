import logging
import re, regex

from api.entryprocessor.wiki.base import WiktionaryProcessorException

log = logging.getLogger(__name__)


def drop_definitions_with_labels(*labels):
    def _drop_definitions(definition) -> str:
        for label in labels:
            # labels (xxx, yy, zzzzz) using find:
            if definition.find(f"({label})") != -1:
                return ""
            elif definition.find(f", {label})") != -1:
                return ""
            elif definition.find(f"({label},") != -1:
                return ""
            elif definition.find(f", {label},") != -1:
                return ""

        return definition

    return _drop_definitions


def unlink_definition(definition):
    """
    Unlink definition by removing all links.
    """
    # Remove all links of the form [[...]] and [[...|...]]
    definition = re.sub(r"\[\[([^\]]+?)\]\]", "\\1", definition)
    definition = re.sub(r"\[\[([^\]]+?)\|([^\]]+?)\]\]", "\\2", definition)

    # Remove all links of the form {{l|en|...}}
    definition = re.sub(r"\{\{l\|en\|([^\}]+)\}\}", "\\1", definition)

    return definition.strip()


def drop_all_labels(definition):
    """
    Drop all labels from the definition.
    """
    out_str = re.sub(r"^[Nn]y \(.*?\)", "", definition)
    out_str = re.sub(r"^[Ii]zay \(.*?\)", "", out_str)
    out_str = re.sub(r"^[ ]?\(.*?\)", "", out_str)

    return out_str.strip()


def handle_nongloss_templates(definition):
    refined = definition
    for template_name in ["pedlink", "vern", "gloss", "n-g", "g", "non-gloss"]:
        t_head = "{{" + template_name + "|"
        if refined.find(t_head) != -1:
            r_begin = refined.find(t_head)
            r_end = refined.find("}}", r_begin)
            nongloss = refined[r_begin + len(t_head): r_end]
            if r_end == -1:
                refined = refined.replace(refined[r_begin:], f"''{nongloss}''")
            else:
                refined = refined.replace(refined[r_begin: r_end + 2], f"''{nongloss}''")

    return refined


def handle_taxfmt_templates(definition):
    """handle {{taxfmt| as in # The {{vern|big-scaled redfin}}, {{taxfmt|Tribolodon hakonensis|species}}
       expected output: The ''big-scaled redfin'', ''Tribolodon hakonensis'' (species)"""
    refined = definition
    t_head = "{{taxfmt|"
    if refined.find(t_head) != -1:
        r_begin = refined.find(t_head)
        r_end = refined.find("}}", r_begin)
        taxfmt = refined[r_begin + len(t_head): r_end]
        if r_end == -1:
            refined = refined.replace(refined[r_begin:], f"''{taxfmt}''")
        else:
            refined = refined.replace(refined[r_begin: r_end + 2], f"''{taxfmt}''")

    taxfmt_categories = [
        "class", "domain", "family", "genus", "infraorder" "infraorder", "infraspecies", "kingdom", "order", "phylum",
        "species", "subclass", "subfamily", "subgenus", "subkingdom", "suborder", "subphylum", "subspecies",
        "superkingdom", "tribe"
    ]

    for category in taxfmt_categories:
        refined = refined.replace(f"|{category}", f" ({category})")

    return refined


def handle_link(refined):
    # Handle [[]] links
    refined = re.sub(r"\[\[([\w ]+)\|[\w ]+\]\]", "\\1", refined)
    refined = re.sub(r"\[\[([\w ]+)#([\w ]+)\|([\w ]+)\]\]", "\\3", refined)
    refined = re.sub(r"\[\[([\w ]+)\]\]", "\\1", refined)
    return refined


def delete_all_templates(refined):
    """
    Deletes all templates of the form {{ ... }} from `refined` (including nested ones).
    If a template never closes, deletes from the opening {{ up to the end of the string.
    Raises WiktionaryProcessorException if unwanted characters remain.
    """
    while True:
        # Find the first opening braces
        template_begin = refined.find("{{")
        if template_begin == -1:
            # No more templates to remove
            break

        # We have an opening '{{'. Find the matching '}}' (accounting for nesting).
        depth = 0
        pos = template_begin
        while pos < len(refined):
            # Check for another '{{' (going deeper into nested templates)
            if refined.startswith("{{", pos):
                depth += 1
                pos += 2
            # Check for '}}' (closing one level of nesting)
            elif refined.startswith("}}", pos):
                depth -= 1
                pos += 2
                if depth == 0:
                    # Found the matching end
                    break
            else:
                pos += 1

        if depth != 0:
            # We never closed the template. Remove from template_begin to the end.
            refined = refined[:template_begin]
        else:
            # Remove everything from '{{' through the matching '}}'.
            refined = refined[:template_begin] + refined[pos:]

    # Final check: if any of these characters remain, raise exception
    for character in "{}[]|":
        while character in refined:
            refined = refined.replace(character, '')
            # raise WiktionaryProcessorException(
            #     f"Refined definition still has unwanted characters: '{character}'"
            # )

    return refined


def delete_html_comments(definition):
    """
    Deletes all HTML comments from `definition`.
    Raises WiktionaryProcessorException if unwanted characters remain.
    """
    while True:
        # Find the first opening '<!--'
        comment_begin = definition.find("<!--")
        if comment_begin == -1:
            # No more comments to remove
            break

        # Find the matching '-->'
        comment_end = definition.find("-->", comment_begin)
        if comment_end == -1:
            # We never closed the comment. Remove from comment_begin to the end.
            definition = definition[:comment_begin]
        else:
            # Remove everything from '<!--' through the matching '-->'.
            definition = definition[:comment_begin] + definition[comment_end + 3:]

    return definition.strip()


def handle_label_templates(definition):
    if definition.startswith("{{label") or definition.startswith("{{lb|"):
        pipe_1 = definition.find("|")
        pipe_2 = definition.find("|", pipe_1 + 1)

        label_text_begin = pipe_2
        label_text_end = definition.find("}", label_text_begin)

        label_text = definition[label_text_begin:label_text_end]
        full_label_text = definition[: label_text_end + 2]
        reformatted_labels = "(" + label_text.lstrip("|").replace("|", ", ") + ") "
    else:
        reformatted_labels = ""
        full_label_text = ""

    refined = reformatted_labels + definition.replace(full_label_text, "")
    refined = refined.replace(", usually, ", ", usually ")
    refined = refined.replace(", _, ", " ")

    # Handle {{l|en|}} links
    refined = re.sub(r"\{\{l\|en\|([\w ]+)\}\}", "\\1", refined)

    return refined


def handle_surrounding_string(surrounding_string, definition):
    """
    Remove surrounding string from definition.
    """
    while surrounding_string in definition:
        shift = len(surrounding_string)
        begin = definition.find(surrounding_string)
        if begin != -1:
            end = definition.find(surrounding_string, begin + shift)
            if end != -1:
                surrounding_text = definition[begin:end + shift]
                print(surrounding_text)
                definition = definition.replace(
                    surrounding_text, surrounding_text.replace(surrounding_string, ''))

    return definition


def handle_bold_text(definition):
    """
    Remove bold formatting from definition.
    """
    return handle_surrounding_string("'''", definition)


def handle_italic_text(definition):
    """
    Remove italic formatting from definition.
    """
    return handle_surrounding_string("''", definition)


def handle_plural_template(definition):
    """
    Remove plural template from definition.
    """

    return regex.sub(
        regex.compile("\{\{plural of\|en\|(\p{L}+)\}\}", flags=regex.UNICODE),
        "plural of '\\1'", definition)

def handle_obsolete_form_of_template(definition):
    """
    Remove plural obsolete_form_of from definition.
    """
    return regex.sub(
        regex.compile("\{\{obsolete form of\|en\|(\p{L}+)\|[a-zA-Z0-9#\|\-\+=]+\}\}", flags=regex.UNICODE),
        "obsolete form of '\\1'", definition
    )

def handle_given_name_template(definition):
    """
    Remove given name template from definition.
    """
    return regex.sub(
        regex.compile("\{\{given name\|[a-zA-Z]+\|(\p{L}+)\|[a-zA-Z0-9#\|\-\+=]+\}\}", flags=regex.UNICODE),
        "\\1 given name", definition
    )

def handle_foreign_name_template(definition):
    """
    Remove foreign name template from definition.
    """
    return regex.sub(
        regex.compile("\{\{foreign name\|[a-zA-Z]+\|[a-zA-Z]+\|type=(\p{L}+)\|[a-zA-Z0-9#\|\-\+=]+\}\}", flags=regex.UNICODE),
        "\\1", definition
    )

def handle_semicolon_replacement(definition):
    """
    Replace semicolons with commas in definitions.
    This is useful for definitions that use semicolons to separate items.
    """
    # Replace semicolons with commas
    definition = definition.replace(";", ", ")

    # Remove any trailing commas
    definition = definition.rstrip(", ")

    return definition.strip()



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
    refined = handle_nongloss_templates(refined)
    refined = handle_taxfmt_templates(refined)
    refined = delete_html_comments(refined)
    refined = handle_link(refined)
    refined = handle_bold_text(refined)
    refined = handle_italic_text(refined)

    refined = handle_plural_template(refined)
    refined = handle_obsolete_form_of_template(refined)
    refined = handle_given_name_template(refined)
    refined = handle_foreign_name_template(refined)
    refined = unlink_definition(refined)
    refined = handle_semicolon_replacement(refined)

    # Remove all remaining templates using find,
    # cannot enable this as it has an impact on form-of definitions
    if remove_all_templates:
        refined = delete_all_templates(refined)

    refined = refined.replace("\t", "")
    refined = refined.replace("\n", " ")
    refined = refined.strip()
    refined = refined.replace("  ", " ")

    return refined if refined.strip() and refined.strip(".") else ""


__all__ = ["refine_definition", "drop_definitions_with_labels"]
