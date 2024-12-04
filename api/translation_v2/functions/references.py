from api.servicemanager.pgrest import TemplateTranslation


def translate_reference_templates(
    ref, source="en", target="mg", use_postgrest="automatic"
):
    for citation in ["cite-web", "cite-book"]:
        if citation in ref:
            # Do not return any translation for the two references above
            return ""

    postgrest = TemplateTranslation(use_postgrest)
    if "|" in ref:
        title = ref[2 : ref.find("|", 3)]
    else:
        title = (
            ref[2 : ref.find("}}", 3)]
            if ref.find("}}", 3) != -1
            else ref[2:] + "}}"
        )
    translated_title = postgrest.get_mapped_template_in_database(
        title, target_language=target
    )
    if translated_title is None and "R:" in title[:3]:
        translated_title = title[:3].replace("R:", "Tsiahy:") + title[3:]

    if title != translated_title and translated_title is not None:
        postgrest.add_translated_title(
            title, translated_title, source_language=source, target_language=target
        )
        return ref.replace(title, translated_title)
    return title


def translate_references(
    references: list, source="en", target="mg", use_postgrest: [bool, str] = "automatic"
) -> list:
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
