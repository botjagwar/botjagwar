"""Synchronize speedy deletion candidates from English to Malagasy Wiktionary pages."""

from __future__ import annotations

import datetime as dt
import os
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Iterable, Optional, Set

import mwparserfromhell
import pywikibot

from conf.entryprocessor.languagecodes.en import LANGUAGE_NAMES

if TYPE_CHECKING:
    from api.output import Output

EN_SPEEDY_DELETION_CATEGORY = "Candidates for speedy deletion"


@dataclass
class OfflineSite:
    """Minimal site object used when tests run without Pywikibot network access."""

    language: str
    wiki: str

    @property
    def lang(self) -> str:
        """Return the language code expected by page mocks."""
        return self.language

    @property
    def code(self) -> str:
        """Return the language code expected by Pywikibot-style callers."""
        return self.language


@dataclass
class SyncResult:
    """Represents the result of a page synchronization run."""

    page_title: str
    updated: bool
    deleted_sections: list[str]
    reason: str


class SpeedyDeletionSectionSynchronizer:
    """Delete Malagasy language sections when matching English sections are old speedy-deletion candidates."""

    def __init__(
        self,
        output: Optional["Output"] = None,
        page_factory: Callable[[pywikibot.Site, str], pywikibot.Page] = pywikibot.Page,
    ) -> None:
        if output is None:
            from api.output import Output

            output = Output("mg")

        self.output = output
        self.page_factory = page_factory
        if os.environ.get("PYWIKIBOT_NO_NETWORK"):
            self.en_site = OfflineSite("en", "wiktionary")
            self.mg_site = OfflineSite("mg", "wiktionary")
        else:
            self.en_site = pywikibot.Site("en", "wiktionary")
            self.mg_site = pywikibot.Site("mg", "wiktionary")

    @staticmethod
    def contains_speedy_template(content: str) -> bool:
        """Return whether a page contains an active English speedy deletion template."""

        try:
            wikicode = mwparserfromhell.parse(content)
            for template in wikicode.ifilter_templates(recursive=True):
                template_name = str(template.name).strip().lower()
                if template_name in {"d", "delete"}:
                    return True
            return False
        except Exception:
            # Fallback for malformed markup: ignore commented/nowiki content before regex scan.
            content_without_comments = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL)
            content_without_nowiki = re.sub(
                r"<nowiki[^>]*>.*?</nowiki>",
                "",
                content_without_comments,
                flags=re.IGNORECASE | re.DOTALL,
            )
            return (
                re.search(
                    r"\{\{\s*(?:d|delete)(?:\||\}\})",
                    content_without_nowiki,
                    flags=re.IGNORECASE,
                )
                is not None
            )

    @staticmethod
    def extract_language_codes(content: str) -> Set[str]:
        """Extract ISO language codes from English Wiktionary language section headers."""

        language_codes: Set[str] = set()
        for line in content.split("\n"):
            matched = re.match(r"^==\s*([^=]+?)\s*==$", line)
            if not matched:
                continue

            language_name = matched.group(1)
            language_code = LANGUAGE_NAMES.get(language_name)
            if language_code:
                language_codes.add(language_code)

        return language_codes

    @staticmethod
    def _revision_text(revision: Any) -> str:
        """Extract revision text from a pywikibot revision object or mapping."""

        if hasattr(revision, "text"):
            return getattr(revision, "text") or ""

        if isinstance(revision, dict):
            return revision.get("text") or revision.get("*") or ""

        return ""

    @staticmethod
    def _revision_timestamp(revision: Any) -> Optional[dt.datetime]:
        """Extract revision timestamp from a pywikibot revision object or mapping."""

        timestamp = getattr(revision, "timestamp", None)
        if timestamp is None and isinstance(revision, dict):
            timestamp = revision.get("timestamp")

        if isinstance(timestamp, str):
            return dt.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

        return timestamp

    def get_latest_speedy_template_added_at(self, page: pywikibot.Page) -> Optional[dt.datetime]:
        """Return the timestamp where the currently-visible speedy template was last added."""

        latest_added_at: Optional[dt.datetime] = None
        had_template = False

        for revision in page.revisions(content=True, reverse=True):
            revision_text = self._revision_text(revision)
            has_template = self.contains_speedy_template(revision_text)
            if has_template and not had_template:
                latest_added_at = self._revision_timestamp(revision)
            had_template = has_template

        if not had_template:
            return None

        return latest_added_at

    @staticmethod
    def is_older_than_two_weeks(
        timestamp: dt.datetime,
        now: Optional[dt.datetime] = None,
    ) -> bool:
        """Return whether a timestamp is at least 14 days old."""

        now = now or dt.datetime.now(dt.timezone.utc)
        return now - timestamp >= dt.timedelta(days=14)

    @staticmethod
    def _is_in_speedy_deletion_category(page: pywikibot.Page) -> bool:
        """Return whether the page belongs to the English speedy deletion candidate category."""

        for category in page.categories():
            if category.title(with_ns=False) == EN_SPEEDY_DELETION_CATEGORY:
                return True
        return False

    def _delete_matching_sections(self, mg_page_text: str, language_codes: Iterable[str]) -> tuple[str, list[str]]:
        """Delete Malagasy sections matching provided language codes and return updated content with deleted codes."""

        updated_text = mg_page_text
        deleted_codes: list[str] = []

        for language_code in sorted(set(language_codes)):
            new_text = self.output.delete_section(language_code, updated_text)
            if new_text != updated_text:
                deleted_codes.append(language_code)
                updated_text = new_text

        return updated_text, deleted_codes

    def sync_page(self, page_title: str, now: Optional[dt.datetime] = None) -> SyncResult:
        """Synchronize one page between English and Malagasy Wiktionary according to speedy deletion rules."""

        en_page = self.page_factory(self.en_site, page_title)
        mg_page = self.page_factory(self.mg_site, page_title)

        if not en_page.exists() or not mg_page.exists():
            return SyncResult(page_title=page_title, updated=False, deleted_sections=[], reason="page-missing")

        if en_page.namespace().id != 0 or mg_page.namespace().id != 0:
            return SyncResult(page_title=page_title, updated=False, deleted_sections=[], reason="wrong-namespace")

        if not self._is_in_speedy_deletion_category(en_page):
            return SyncResult(page_title=page_title, updated=False, deleted_sections=[], reason="not-speedy-candidate")

        added_at = self.get_latest_speedy_template_added_at(en_page)
        if added_at is None:
            return SyncResult(page_title=page_title, updated=False, deleted_sections=[], reason="no-template-timestamp")

        if not self.is_older_than_two_weeks(added_at, now=now):
            return SyncResult(page_title=page_title, updated=False, deleted_sections=[], reason="template-too-recent")

        en_content = en_page.get()
        mg_content = mg_page.get()
        language_codes = self.extract_language_codes(en_content)
        updated_content, deleted_sections = self._delete_matching_sections(mg_content, language_codes)

        if updated_content == mg_content:
            return SyncResult(page_title=page_title, updated=False, deleted_sections=[], reason="no-matching-sections")

        summary = (
            "Nesorina ireo fizarana mifanaraka amin'ny fiteny hita ao amin'ny en.wiktionary, "
            "pejy natolotra hofafana efa mihoatra ny 14 andro"
        )
        mg_page.put(updated_content, summary=summary)
        return SyncResult(page_title=page_title, updated=True, deleted_sections=deleted_sections, reason="updated")


def main() -> None:
    """CLI entrypoint for syncing a single page by title."""

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("title", help="Wiktionary page title")
    args = parser.parse_args()

    result = SpeedyDeletionSectionSynchronizer().sync_page(args.title)
    print(result)


if __name__ == "__main__":
    main()
