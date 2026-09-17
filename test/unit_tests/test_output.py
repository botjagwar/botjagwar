from unittest.case import TestCase
from unittest.mock import MagicMock, call, patch

from api.http_client import DEFAULT_HTTP_TIMEOUT
from api.model.word import Entry
from api.output import Output


class TestOutput(TestCase):
    @patch("api.output.StaticBackend")
    @patch("api.output.requests.post")
    @patch("api.output.requests.get")
    def test_postgrest_add_translation_method(self, requests_get, requests_post, static_backend):
        """Persist translation methods for a realistic PostgREST list response."""
        static_backend.return_value.backend = "http://postgrest"
        requests_get.side_effect = [
            MagicMock(json=MagicMock(return_value=[{"id": 10}])),
            MagicMock(json=MagicMock(return_value=[{"id": 20}])),
        ]
        entry = MagicMock(
            entry="word",
            language="en",
            part_of_speech="ana",
            translation_methods={"definition": ["nllb", "dictionary"]},
        )

        Output.postgrest_add_translation_method(entry)

        requests_post.assert_has_calls(
            [
                call(
                    "http://postgrest/translation_method",
                    json={"word": 10, "definition": 20, "translation_method": "nllb"},
                    timeout=DEFAULT_HTTP_TIMEOUT,
                ),
                call(
                    "http://postgrest/translation_method",
                    json={"word": 10, "definition": 20, "translation_method": "dictionary"},
                    timeout=DEFAULT_HTTP_TIMEOUT,
                ),
            ]
        )

    def test_wikipage_one_page(self):
        entry1 = MagicMock(
            entry="test1", language="l1", part_of_speech="ana", definitions=["def1-1"]
        )
        expected = (
            "\n=={{=l1=}}==\n\n{{-ana-|l1}}\n'''{{subst:BASEPAGENAME}}''' \n# [[def1-1]]\n"
        )
        output = Output()
        rendered = output.wikipage(entry1)
        self.assertEqual(rendered.strip(), expected.strip())

    def test_wikipage_many_pages(self):
        entry1 = MagicMock(
            entry="test1", language="l1", part_of_speech="ana", definitions=["def1-1"]
        )
        entry1_1 = MagicMock(
            entry="test1", language="l1", part_of_speech="mpam", definitions=["def1-2"]
        )
        entry2 = MagicMock(
            entry="test2",
            language="l2",
            part_of_speech="ana",
            definitions=["def2-1", "def2-2"],
        )
        entry3 = MagicMock(
            entry="test3",
            language="l3",
            part_of_speech="ana",
            definitions=["def3-1", "def3-2", "def3-3"],
        )

        expected = (
            "\n=={{=l1=}}==\n\n{{-mpam-|l1}}\n'''{{subst:BASEPAGENAME}}''' \n# [[def1-2]]"
            "\n\n{{-ana-|l1}}\n'''{{subst:BASEPAGENAME}}''' \n# [[def1-1]]"
            "\n\n=={{=l2=}}==\n\n{{-ana-|l2}}\n'''{{subst:BASEPAGENAME}}''' \n# [[def2-1]]"
            "\n# [[def2-2]]"
            "\n=={{=l3=}}==\n\n{{-ana-|l3}}\n'''{{subst:BASEPAGENAME}}''' \n# [[def3-1]]"
            "\n# [[def3-2]]\n# [[def3-3]]\n"
        )

        output = Output()
        rendered = output.wikipages([entry1, entry1_1, entry2, entry3])
        print(rendered)
        self.assertEqual(rendered.strip(), expected.strip())

    def test_wikipages_renders_shared_etymology_once(self):
        """Emit one language-level etymology section for multiple entries."""
        entries = [
            Entry(
                entry="word",
                part_of_speech=part_of_speech,
                definitions=[f"[[definition-{part_of_speech}]]"],
                language="en",
                additional_data={"etymology": ["Avy amin'ny loharano."]},
            )
            for part_of_speech in ("ana", "mpam")
        ]

        rendered = Output().wikipages(entries)

        self.assertEqual(rendered.count("{{-etim-}}"), 1)
        self.assertLess(rendered.index("{{-etim-}}"), rendered.index("{{-ana-|en}}"))
        self.assertLess(rendered.index("{{-etim-}}"), rendered.index("{{-mpam-|en}}"))

    def test_wikipages_combines_distinct_etymologies(self):
        """Retain canonical etymologies contributed by later entries."""
        entries = [
            Entry(
                entry="word",
                part_of_speech="ana",
                definitions=["[[first]]"],
                language="en",
                additional_data={"etymology": ["First origin."]},
            ),
            Entry(
                entry="word",
                part_of_speech="mpam",
                definitions=["[[second]]"],
                language="en",
                additional_data={"etymology": ["Second origin."]},
            ),
        ]

        rendered = Output().wikipages(entries)

        self.assertEqual(rendered.count("{{-etim-}}"), 1)
        self.assertIn(":First origin. Second origin.", rendered)
