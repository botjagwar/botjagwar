"""Behavioral tests for translation publishers with external boundaries mocked."""

from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest

from api.model.word import Entry
from api.translation_v2 import publishers
from api.translation_v2.exceptions import TranslatedPagePushError


def _translation(*, ninja_mode: str = "0", rendered: str = "  ==new==  ") -> SimpleNamespace:
    """Build the minimal translation collaborator used by publisher closures."""
    output = MagicMock()
    output.wikipages.return_value = rendered
    config = MagicMock()
    config.get.return_value = ninja_mode
    return SimpleNamespace(
        working_wiki_language="mg",
        output=output,
        config=config,
        generate_summary=MagicMock(return_value="summary"),
    )


def _entry(language: str) -> Entry:
    """Create an entry whose language section can be replaced during publication."""
    return Entry(
        entry=f"word-{language}",
        part_of_speech="ana",
        definitions=["definition"],
        language=language,
    )


def _page(*, namespace_id: int = 0, exists: bool = False, text: str = "") -> MagicMock:
    """Build an offline page double with a stable namespace response."""
    page = MagicMock()
    page.namespace.return_value = SimpleNamespace(id=namespace_id, custom_name="Template")
    page.exists.return_value = exists
    page.get.return_value = text
    return page


def _direct_publisher() -> publishers.WiktionaryDirectPublisher:
    """Construct a direct publisher."""
    return publishers.WiktionaryDirectPublisher()


def _rabbitmq_publisher(queue: str = "botjagwar") -> publishers.WiktionaryRabbitMqPublisher:
    """Construct a queue publisher with an offline producer factory."""
    return publishers.WiktionaryRabbitMqPublisher(
        queue,
        producer_factory=MagicMock(),
    )


def test_reference_publisher_handles_templates_on_either_side() -> None:
    """A template marker in either reference should trigger target-wiki publication."""
    translation = MagicMock()
    references = {
        ("plain original", "{{translated template}}"),
        ("{{original template}}", "plain translation"),
        ("plain original", "plain translation"),
    }

    publish = publishers.Publisher.publish_translated_references(translation, references)
    publish(source_wiki="fr", target_wiki="mg")

    translation.create_or_rename_template_on_target_wiki.assert_has_calls(
        [
            call(
                source_language="fr",
                source_name="plain original",
                target_language="mg",
                target_name="{{translated template}}",
            ),
            call(
                source_language="fr",
                source_name="{{original template}}",
                target_language="mg",
                target_name="plain translation",
            ),
        ],
        any_order=True,
    )
    assert translation.create_or_rename_template_on_target_wiki.call_count == 2


@pytest.mark.parametrize("publisher_factory", [_direct_publisher, _rabbitmq_publisher])
def test_publishers_reject_non_malagasy_target_before_page_creation(
    publisher_factory,
) -> None:
    translation = _translation()
    translation.working_wiki_language = "en"
    publisher = publisher_factory()

    with patch.object(publishers, "Site") as site_class, patch.object(
        publishers, "Page"
    ) as page_class:
        expected_error = (
            publishers.WiktionaryRabbitMqPublisherError
            if isinstance(publisher, publishers.WiktionaryRabbitMqPublisher)
            else TranslatedPagePushError
        )
        with pytest.raises(expected_error) as exc_info:
            publisher.publish_to_wiktionary(translation)("unsafe", [_entry("en")])

    underlying_error = exc_info.value.__cause__ or exc_info.value
    assert isinstance(underlying_error, TranslatedPagePushError)
    assert "Malagasy Wiktionary" in str(underlying_error)
    site_class.assert_not_called()
    page_class.assert_not_called()


def test_direct_publisher_rejects_non_article_namespaces() -> None:
    """Direct publication must reject pages outside the main namespace before reading them."""
    translation = _translation()
    page = _page(namespace_id=10)
    publisher = _direct_publisher()

    with patch.object(publishers, "Site") as site_class, patch.object(
        publishers, "Page", return_value=page
    ) as page_class:
        with pytest.raises(TranslatedPagePushError, match=r"Template namespace \(ns:10\)"):
            publisher.publish_to_wiktionary(translation)("unsafe", [_entry("en")])

    site_class.assert_called_once_with("mg", "wiktionary")
    page_class.assert_called_once_with(site_class.return_value, "unsafe", offline=False)
    page.exists.assert_not_called()
    page.put.assert_not_called()


def test_direct_publisher_replaces_existing_language_sections_and_throttles() -> None:
    """Existing text should be retained except for sections represented by new entries."""
    translation = _translation(ninja_mode="1")
    entries = [_entry("en"), _entry("fr")]
    page = _page(exists=True, text="  legacy page  ")
    translation.output.delete_section.side_effect = [
        " legacy without English ",
        " legacy without English or French ",
    ]
    processor = MagicMock()
    processor_class = MagicMock(return_value=processor)
    publisher = _direct_publisher()

    with patch.object(publishers, "Site") as site_class, patch.object(
        publishers, "Page", return_value=page
    ), patch.object(
        publishers.entryprocessor.WiktionaryProcessorFactory,
        "create",
        return_value=processor_class,
    ) as create_processor, patch.object(publishers.time, "sleep") as sleep:
        publisher.publish_to_wiktionary(translation)("entry", entries)

    create_processor.assert_called_once_with("mg")
    processor_class.assert_called_once_with()
    processor.set_text.assert_called_once_with("  legacy page  ")
    processor.set_title.assert_called_once_with("entry")
    translation.output.delete_section.assert_has_calls(
        [
            call("en", "  legacy page  "),
            call("fr", " legacy without English "),
        ]
    )
    content = "legacy without English or French\n==new=="
    translation.generate_summary.assert_called_once_with(entries, page, content)
    page.put.assert_called_once_with(content, "summary")
    translation.config.get.assert_called_once_with("ninja_mode", "translator")
    sleep.assert_called_once_with(12)
    site_class.assert_called_once_with("mg", "wiktionary")


def test_direct_publisher_creates_a_new_page_without_processor_or_sleep() -> None:
    """A missing target page should contain only rendered entries and skip aggregation work."""
    translation = _translation(rendered="  fresh page  ")
    entries = [_entry("en")]
    page = _page(exists=False)
    publisher = _direct_publisher()

    with patch.object(publishers, "Site"), patch.object(
        publishers, "Page", return_value=page
    ), patch.object(
        publishers.entryprocessor.WiktionaryProcessorFactory, "create"
    ) as create_processor, patch.object(publishers.time, "sleep") as sleep:
        publisher.publish_to_wiktionary(translation)("new-entry", entries)

    create_processor.assert_not_called()
    page.get.assert_not_called()
    translation.output.delete_section.assert_not_called()
    content = "\nfresh page"
    translation.generate_summary.assert_called_once_with(entries, page, content)
    page.put.assert_called_once_with(content, "summary")
    sleep.assert_not_called()


def test_rabbitmq_push_reports_connection_rejection() -> None:
    """A failed producer construction cannot have published the message."""
    publisher = publishers.WiktionaryRabbitMqPublisher(
        "translated",
        producer_factory=MagicMock(side_effect=RuntimeError("offline")),
    )

    with pytest.raises(
        publishers.WiktionaryRabbitMqPublisherRejectedError,
        match="before publication",
    ):
        publisher.push({"page": "entry"})


def test_rabbitmq_push_reports_unknown_publish_outcome() -> None:
    """A producer error after connection must be reconciled conservatively."""
    producer = MagicMock()
    producer.push_to_queue.side_effect = RuntimeError("confirm lost")
    publisher = publishers.WiktionaryRabbitMqPublisher(
        "translated",
        producer_factory=MagicMock(return_value=producer),
    )

    with pytest.raises(
        publishers.WiktionaryRabbitMqPublisherOutcomeUnknown,
        match="outcome is unknown",
    ):
        publisher.push({"page": "entry"})


def test_publish_wikipage_builds_the_queue_contract() -> None:
    """The convenience method should send a complete Malagasy Wiktionary message."""
    publisher = _rabbitmq_publisher()
    publisher.push = MagicMock()

    publisher.publish_wikipage("content", "title", summary="summary", minor=True)

    publisher.push.assert_called_once_with(
        {
            "language": "mg",
            "site": "wiktionary",
            "page": "title",
            "content": "content",
            "summary": "summary",
            "minor": True,
        }
    )


def test_publish_wikipage_includes_an_optional_content_precondition() -> None:
    """Page-check messages can guard against stale full-page replacement."""
    publisher = _rabbitmq_publisher()
    publisher.push = MagicMock()

    publisher.publish_wikipage(
        "content",
        "title",
        expected_content_sha256="a" * 64,
    )

    publisher.push.assert_called_once_with(
        {
            "language": "mg",
            "site": "wiktionary",
            "page": "title",
            "content": "content",
            "summary": "mamafa ny fihodinana",
            "minor": False,
            "expected_content_sha256": "a" * 64,
        }
    )


def test_publish_wikipage_checks_guard_immediately_before_push() -> None:
    """A lost execution lease prevents the external queue side effect."""
    publisher = _rabbitmq_publisher()
    publisher.push = MagicMock()
    guard = MagicMock(side_effect=RuntimeError("superseded"))

    with pytest.raises(RuntimeError, match="superseded"):
        publisher.publish_wikipage("content", "title", publication_guard=guard)

    guard.assert_called_once_with()
    publisher.push.assert_not_called()


def test_rabbitmq_publisher_aggregates_existing_page_into_message() -> None:
    """Queue publication should replace represented sections and preserve other target text."""
    translation = _translation(rendered=" rendered ")
    entries = [_entry("en")]
    page = _page(exists=True, text=" old content ")
    translation.output.delete_section.return_value = " retained content "
    processor = MagicMock()
    processor_class = MagicMock(return_value=processor)
    publisher = _rabbitmq_publisher()
    publisher.push = MagicMock()

    with patch.object(publishers, "Site"), patch.object(
        publishers, "Page", return_value=page
    ), patch.object(
        publishers.entryprocessor.WiktionaryProcessorFactory,
        "create",
        return_value=processor_class,
    ) as create_processor:
        publisher.publish_to_wiktionary(translation)("entry", entries)

    create_processor.assert_called_once_with("mg")
    processor.set_text.assert_called_once_with(" old content ")
    processor.set_title.assert_called_once_with("entry")
    translation.output.delete_section.assert_called_once_with("en", " old content ")
    content = "retained content\nrendered"
    translation.generate_summary.assert_called_once_with(entries, page, content)
    publisher.push.assert_called_once_with(
        {
            "language": "mg",
            "site": "wiktionary",
            "page": "entry",
            "content": content,
            "summary": "summary",
            "minor": False,
        }
    )


def test_rabbitmq_publisher_builds_message_for_missing_page() -> None:
    """A missing target should produce a queue message without wiki parsing calls."""
    translation = _translation(rendered=" rendered ")
    entries = [_entry("fr")]
    page = _page(exists=False)
    publisher = _rabbitmq_publisher()
    publisher.push = MagicMock()

    with patch.object(publishers, "Site"), patch.object(
        publishers, "Page", return_value=page
    ), patch.object(
        publishers.entryprocessor.WiktionaryProcessorFactory, "create"
    ) as create_processor:
        publisher.publish_to_wiktionary(translation)("new-entry", entries)

    create_processor.assert_not_called()
    page.get.assert_not_called()
    publisher.push.assert_called_once_with(
        {
            "language": "mg",
            "site": "wiktionary",
            "page": "new-entry",
            "content": "\nrendered",
            "summary": "summary",
            "minor": False,
        }
    )


def test_rabbitmq_publisher_discards_candidate_rejected_by_prefilter() -> None:
    """The exact assembled page is filtered before the lease guard and queue push."""
    translation = _translation(rendered=" rendered ")
    entries = [_entry("fr")]
    page = _page(exists=False)
    publisher = _rabbitmq_publisher()
    publisher.push = MagicMock()
    publication_filter = MagicMock(return_value=False)
    publication_guard = MagicMock()

    with patch.object(publishers, "Site"), patch.object(
        publishers, "Page", return_value=page
    ):
        queued = publisher.publish_to_wiktionary(
            translation,
            publication_guard=publication_guard,
            publication_filter=publication_filter,
        )("new-entry", entries)

    assert queued is False
    publication_filter.assert_called_once_with("new-entry", "\nrendered")
    publication_guard.assert_not_called()
    publisher.push.assert_not_called()


def test_rabbitmq_publisher_wraps_namespace_error_with_original_cause() -> None:
    """Closure failures should use the queue-specific error while retaining their cause."""
    translation = _translation()
    page = _page(namespace_id=2)
    publisher = _rabbitmq_publisher()

    with patch.object(publishers, "Site"), patch.object(publishers, "Page", return_value=page):
        with pytest.raises(publishers.WiktionaryRabbitMqPublisherError) as exc_info:
            publisher.publish_to_wiktionary(translation)("user-page", [_entry("en")])

    assert isinstance(exc_info.value.__cause__, TranslatedPagePushError)
    assert "Template namespace (ns:2)" in str(exc_info.value.__cause__)
    page.exists.assert_not_called()
