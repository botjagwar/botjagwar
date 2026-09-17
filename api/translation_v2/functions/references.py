import mwparserfromhell
from mwparserfromhell.nodes import Template

from api.servicemanager.pgrest import TemplateTranslation
from api.utils.citations import localize_citation_date


_DATE_PARAMETERS = {
    "access-date",
    "accessdate",
    "archive-date",
    "archivedate",
    "date",
    "month",
    "orig-date",
    "origdate",
    "publication-date",
    "publicationdate",
}


def _localize_template_dates(template: Template) -> None:
    """Localize citation date values without changing other parameters."""
    for parameter in template.params:
        name = str(parameter.name).strip().casefold().rstrip("0123456789")
        if name not in _DATE_PARAMETERS:
            continue

        raw_value = str(parameter.value)
        value = raw_value.strip()
        localized = localize_citation_date(value)
        if localized != value:
            leading = raw_value[: len(raw_value) - len(raw_value.lstrip())]
            trailing = raw_value[len(raw_value.rstrip()) :]
            parameter.value = f"{leading}{localized}{trailing}"


def translate_reference_templates(
    ref: str,
    source: str = "en",
    target: str = "mg",
    use_postgrest: bool | str = "automatic",
) -> str:
    """Translate a reference template name and localize Malagasy dates."""
    wikicode = mwparserfromhell.parse(ref)
    templates = wikicode.filter_templates(recursive=False)
    if not templates:
        return ref

    template = templates[0]
    title = str(template.name).strip()
    if target == "mg":
        _localize_template_dates(template)

    if title.casefold() in {"cite-web", "cite-book"}:
        return str(wikicode)

    postgrest = TemplateTranslation(use_postgrest)
    translated_title = postgrest.get_mapped_template_in_database(
        title, target_language=target
    )
    if translated_title is None and "R:" in title[:3]:
        translated_title = title[:3].replace("R:", "Tsiahy:") + title[3:]

    if title != translated_title and translated_title is not None:
        postgrest.add_translated_title(
            title, translated_title, source_language=source, target_language=target
        )
        template.name = translated_title
    return str(wikicode)


def translate_references(
    references: list[str],
    source: str = "en",
    target: str = "mg",
    use_postgrest: bool | str = "automatic",
) -> list[str]:
    """Translates reference templates"""
    translated_references = []

    for ref in references:
        if ref.strip().startswith("{{"):
            translated_reference = translate_reference_templates(
                ref, source, target, use_postgrest
            )
        elif ref.strip().startswith("|"):
            continue
        elif "<references" in ref.lower():
            continue
        elif "[[category:" in ref.lower():
            continue
        else:
            translated_reference = ref

        if translated_reference:
            translated_references.append(translated_reference)
        else:
            translated_references.append(ref)

    return translated_references
