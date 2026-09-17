import datetime as dt
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock

from api.speedy_deletion import EN_SPEEDY_DELETION_CATEGORY, SpeedyDeletionSectionSynchronizer


class FakeCategory:
    def __init__(self, title: str):
        self._title = title

    def title(self, with_ns: bool = False):
        return self._title


class FakePage:
    def __init__(
        self,
        title: str,
        content: str,
        exists: bool = True,
        namespace_id: int = 0,
        categories=None,
        revisions=None,
    ):
        self._title = title
        self._content = content
        self._exists = exists
        self._namespace_id = namespace_id
        self._categories = categories or []
        self._revisions = revisions or []
        self.put = MagicMock()

    def exists(self):
        return self._exists

    def namespace(self):
        return SimpleNamespace(id=self._namespace_id)

    def categories(self):
        return iter(self._categories)

    def revisions(self, content=True, reverse=True):
        return iter(self._revisions)

    def get(self):
        return self._content


class TestSpeedyDeletionSectionSynchronizer(TestCase):
    def setUp(self):
        self.output = MagicMock()
        self.sync = SpeedyDeletionSectionSynchronizer(output=self.output)

    def test_extract_language_codes(self):
        content = "==English==\nfoo\n==French==\nbar\n==Unknown Language=="
        self.assertEqual(self.sync.extract_language_codes(content), {"en", "fr"})


    def test_contains_speedy_template_ignores_inactive_markup(self):
        self.assertFalse(self.sync.contains_speedy_template("<!-- {{d}} -->"))
        self.assertFalse(self.sync.contains_speedy_template("<nowiki>{{delete|test}}</nowiki>"))
        self.assertTrue(self.sync.contains_speedy_template("{{d}}"))

    def test_get_latest_speedy_template_added_at_ignores_commented_template(self):
        revisions = [
            {"timestamp": dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc), "text": "<!-- {{d}} -->"},
            {"timestamp": dt.datetime(2024, 1, 20, tzinfo=dt.timezone.utc), "text": "{{d}}"},
        ]
        page = FakePage("x", "", revisions=revisions)

        self.assertEqual(
            self.sync.get_latest_speedy_template_added_at(page),
            dt.datetime(2024, 1, 20, tzinfo=dt.timezone.utc),
        )
    def test_get_latest_speedy_template_added_at_returns_last_transition(self):
        revisions = [
            {"timestamp": dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc), "text": "no template"},
            {"timestamp": dt.datetime(2024, 1, 2, tzinfo=dt.timezone.utc), "text": "{{d}}"},
            {"timestamp": dt.datetime(2024, 1, 3, tzinfo=dt.timezone.utc), "text": "removed"},
            {"timestamp": dt.datetime(2024, 1, 4, tzinfo=dt.timezone.utc), "text": "{{delete|reason}}"},
        ]
        page = FakePage("x", "", revisions=revisions)

        self.assertEqual(
            self.sync.get_latest_speedy_template_added_at(page),
            dt.datetime(2024, 1, 4, tzinfo=dt.timezone.utc),
        )

    def test_sync_page_skips_recent_template(self):
        now = dt.datetime(2024, 1, 10, tzinfo=dt.timezone.utc)
        revisions = [
            {"timestamp": dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc), "text": "no template"},
            {"timestamp": dt.datetime(2024, 1, 5, tzinfo=dt.timezone.utc), "text": "{{d}}"},
        ]

        en_page = FakePage(
            "word",
            "==English==",
            categories=[FakeCategory(EN_SPEEDY_DELETION_CATEGORY)],
            revisions=revisions,
        )
        mg_page = FakePage("word", "=={{=en=}}==\ncontent")

        def factory(site, title):
            return en_page if site.code == "en" else mg_page

        sync = SpeedyDeletionSectionSynchronizer(output=self.output, page_factory=factory)
        result = sync.sync_page("word", now=now)

        self.assertFalse(result.updated)
        self.assertEqual(result.reason, "template-too-recent")
        mg_page.put.assert_not_called()

    def test_sync_page_deletes_matching_sections_when_old_enough(self):
        now = dt.datetime(2024, 2, 1, tzinfo=dt.timezone.utc)
        revisions = [
            {"timestamp": dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc), "text": "{{delete|reason}}"},
        ]

        en_page = FakePage(
            "word",
            "==English==\ntext\n==French==\ntext",
            categories=[FakeCategory(EN_SPEEDY_DELETION_CATEGORY)],
            revisions=revisions,
        )
        mg_page = FakePage("word", "original")

        def factory(site, title):
            return en_page if site.code == "en" else mg_page

        self.output.delete_section.side_effect = ["after-en", "after-fr"]
        sync = SpeedyDeletionSectionSynchronizer(output=self.output, page_factory=factory)
        result = sync.sync_page("word", now=now)

        self.assertTrue(result.updated)
        self.assertEqual(result.deleted_sections, ["en", "fr"])
        mg_page.put.assert_called_once()
        args, kwargs = mg_page.put.call_args
        self.assertEqual(args[0], "after-fr")
        self.assertIn("Nesorina", kwargs["summary"])

    def test_sync_page_skips_if_not_in_speedy_category(self):
        en_page = FakePage("word", "==English==", categories=[], revisions=[])
        mg_page = FakePage("word", "anything")

        def factory(site, title):
            return en_page if site.code == "en" else mg_page

        sync = SpeedyDeletionSectionSynchronizer(output=self.output, page_factory=factory)
        result = sync.sync_page("word")

        self.assertFalse(result.updated)
        self.assertEqual(result.reason, "not-speedy-candidate")
        mg_page.put.assert_not_called()
