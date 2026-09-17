import logging
import re
import regex
import mwparserfromhell
from mwparserfromhell.nodes import Template


log = logging.getLogger(__name__)
LANGUAGE_CODE_PATTERN = re.compile(r"[a-z]{2,3}(?:-[a-z0-9]+)*")
MAX_TEMPLATE_RENDER_DEPTH = 20

EDITORIAL_TEMPLATES = {
    "rfv-sense", "rfd-sense", "rfclarify", "rfd-redundant", "tea room sense",
    "rfc-sense", "rfm-sense", "rfdef", "rfquotek", "rfdatek", "rfquote-sense",
    "rfeq", "def-uncertain", "senseid", "color panel", "inline images",
    "translation only", "descendant only", "transclude",
}
CONTENT_TEMPLATES = {
    "latn-def", "cyrl-def", "arab-def", "brai-def", "letter def", "si-unit",
    "si-unit-np",
}
EXAMPLE_TEMPLATES = {
    "suffixusex", "prefixusex", "affixusex", "ux", "uxi", "uxa", "ux-lite",
    "coa", "coi", "quotei",
}
RELATION_TEMPLATES = {
    "altform": "alternative form of",
    "alt form": "alternative form of",
    "alternative form of": "alternative form of",
    "alternative spelling of": "alternative spelling of",
    "t-v distinction": "distinguishes informal and formal second-person forms",
    "middle-voice": "middle voice",
    "horse name": "a horse name",
    "iata": "IATA code for",
    "geochronology": "geochronological period",
    "def-see": "see",
    "gender-neutral neologism for": "a gender-neutral neologism for",
    "in full": "in full",
    "rune name": "the name of the rune",
    "only used in": "only used in",
    "nickname": "a nickname for",
    "fo-myt": "form of",
    "&lit": "and literally",
    "+aux": "auxiliary form of",
    "+plural": "plural of",
    "judeo-berber spelling of": "Judeo-Berber spelling of",
    "ajami spelling of": "Ajami spelling of",
    "construed with": "construed with",
    "used in phrasal verbs": "used in phrasal verbs",
    "collocation": "collocation with",
    "wtorw": "alternative form of",
}


def _template_values(template: Template, depth: int) -> list[str]:
    """Return recursively rendered positional values from a template."""
    values: list[str] = []
    for parameter in template.params:
        parameter_name = str(parameter.name).strip()
        if parameter_name.isdigit():
            value = render_definition_templates(str(parameter.value).strip(), depth + 1)
            values.append(value)
    return values


def _without_language_code(values: list[str]) -> list[str]:
    """Remove the leading language code from template positional values."""
    if values and LANGUAGE_CODE_PATTERN.fullmatch(values[0]):
        return values[1:]
    return values


def _render_template(template: Template, depth: int) -> str:
    """Render definition templates without discarding their semantic content."""
    name = str(template.name).strip().lower().replace("_", " ")
    values = _template_values(template, depth)
    content = _without_language_code(values)

    if name in EDITORIAL_TEMPLATES or name in {"label", "term-label"}:
        return ""
    if name in CONTENT_TEMPLATES:
        return " ".join(content)
    if name in EXAMPLE_TEMPLATES:
        return " ".join(content[:1])
    if name in RELATION_TEMPLATES:
        target = ", ".join(content)
        return f"{RELATION_TEMPLATES[name]} {target}".strip()
    return str(template)


def render_definition_templates(definition: str, depth: int = 0) -> str:
    """Render supported definition templates while preserving their content.

    Editorial and label templates are removed, while content, example, and
    relation templates are replaced with readable wikitext. Nested template
    parameters are rendered recursively up to ``MAX_TEMPLATE_RENDER_DEPTH``;
    remaining deeper markup is preserved unchanged.
    """
    if depth >= MAX_TEMPLATE_RENDER_DEPTH:
        return definition

    wikicode = mwparserfromhell.parse(definition)
    for template in wikicode.filter_templates(recursive=False):
        wikicode.replace(template, _render_template(template, depth))
    return str(wikicode)


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


def unlink_definition(definition: str) -> str:
    """
    Unlink definition by removing all links.
    """
    # Resolve piped links first so the generic pattern cannot expose their raw target.
    definition = re.sub(r"\[\[([^\]]+?)\|([^\]]+?)\]\]", "\\2", definition)
    definition = re.sub(r"\[\[([^\]]+?)\]\]", "\\1", definition)

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


def handle_gloss_templates(definition):
    """
    Handle {{gloss|...}}, {{gl|...}} templates in definitions by putting them between parentheses.
    """
    refined = definition
    for template_name in ["gl", "gloss"]:
        t_head = "{{" + template_name + "|"
        if refined.find(t_head) != -1:
            r_begin = refined.find(t_head)
            r_end = refined.find("}}", r_begin)
            gloss = refined[r_begin + len(t_head): r_end]
            if r_end == -1:
                refined = refined.replace(refined[r_begin:], f"({gloss})")
            else:
                refined = refined.replace(refined[r_begin: r_end + 2], f"({gloss})")

    return refined


def handle_nongloss_templates(definition):
    refined = definition
    for template_name in ["w", "pedlink", "vern", "gloss", "n-g", "g", "non-gloss", 'q']:
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
        regex.compile(r"\{\{plural of\|en\|(\p{L}+)\}\}", flags=regex.UNICODE),
        "plural of '\\1'", definition)


def handle_obsolete_form_of_template(definition):
    """
    Remove plural obsolete_form_of from definition.
    """
    return regex.sub(
        regex.compile(r"\{\{obsolete form of\|en\|(\p{L}+)\|[a-zA-Z0-9#\|\-\+=]+\}\}", flags=regex.UNICODE),
        "obsolete form of '\\1'", definition
    )


def handle_given_name_template(definition):
    """
    Remove given name template from definition.
    """
    return regex.sub(
        regex.compile(r"\{\{given name\|[a-zA-Z]+\|(\p{L}+)\|[a-zA-Z0-9#\|\-\+=]+\}\}", flags=regex.UNICODE),
        "\\1 given name", definition
    )


def handle_foreign_name_template(definition):
    """
    Remove foreign name template from definition.
    """
    return regex.sub(
        regex.compile(r"\{\{foreign name\|[a-zA-Z]+\|[a-zA-Z]+\|type=(\p{L}+)\|[a-zA-Z0-9#\|\-\+=]+\}\}",
                      flags=regex.UNICODE),
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

    refined = render_definition_templates(definition)
    refined = handle_label_templates(refined)
    refined = handle_gloss_templates(refined)
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
