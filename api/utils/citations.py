import re
from datetime import date as calendar_date

from api.utils import to_malagasy_month


_ENGLISH_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}
_MONTH_PATTERN = "|".join(
    sorted(_ENGLISH_MONTHS, key=len, reverse=True)
)


def _format_full_date(year: str, month: int, day: str) -> str | None:
    """Format a valid calendar date in Malagasy."""
    try:
        parsed = calendar_date(int(year), month, int(day))
    except ValueError:
        return None
    return f"{parsed.day} {to_malagasy_month(parsed.month)} {parsed.year}"


def localize_citation_date(value: str) -> str:
    """Return a recognized English or ISO citation date in Malagasy."""
    date = value.strip()
    if not date:
        return date

    iso_match = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", date)
    if iso_match:
        year, month, day = iso_match.groups()
        localized = _format_full_date(year, int(month), day)
        return localized if localized is not None else date

    month_first_match = re.fullmatch(
        rf"({_MONTH_PATTERN})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?[,]?\s+(\d{{4}})",
        date,
        flags=re.IGNORECASE,
    )
    if month_first_match:
        month, day, year = month_first_match.groups()
        localized = _format_full_date(
            year, _ENGLISH_MONTHS[month.casefold()], day
        )
        return localized if localized is not None else date

    day_first_match = re.fullmatch(
        rf"(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MONTH_PATTERN})\.?[,]?\s+(\d{{4}})",
        date,
        flags=re.IGNORECASE,
    )
    if day_first_match:
        day, month, year = day_first_match.groups()
        localized = _format_full_date(
            year, _ENGLISH_MONTHS[month.casefold()], day
        )
        return localized if localized is not None else date

    month_year_match = re.fullmatch(
        rf"({_MONTH_PATTERN})\.?\s+(\d{{4}})", date, flags=re.IGNORECASE
    )
    if month_year_match:
        month, year = month_year_match.groups()
        return f"{to_malagasy_month(_ENGLISH_MONTHS[month.casefold()])} {year}"

    month_match = re.fullmatch(
        rf"({_MONTH_PATTERN})\.?", date, flags=re.IGNORECASE
    )
    if month_match:
        return to_malagasy_month(_ENGLISH_MONTHS[month_match.group(1).casefold()])

    return date
