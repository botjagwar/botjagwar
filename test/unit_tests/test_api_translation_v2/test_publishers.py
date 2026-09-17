"""Tests for translation publication boundaries."""

from unittest.mock import MagicMock

import pytest

from api.translation_v2.publishers import (
    Publisher,
    WiktionaryRabbitMqPublisher,
    WiktionaryRabbitMqPublisherError,
    WiktionaryRabbitMqPublisherOutcomeUnknown,
    WiktionaryRabbitMqPublisherRejectedError,
)


def test_reference_publication_uses_job_local_set_without_mutating_it() -> None:
    """Publish only template references while preserving caller-owned state."""
    translation = MagicMock()
    references = {
        ("{{R:source}}", "{{Tsiahy:source}}"),
        ("plain source", "plain target"),
    }

    Publisher.publish_translated_references(translation, references)("en", "mg")

    translation.create_or_rename_template_on_target_wiki.assert_called_once_with(
        source_language="en",
        source_name="{{R:source}}",
        target_language="mg",
        target_name="{{Tsiahy:source}}",
    )
    assert references == {
        ("{{R:source}}", "{{Tsiahy:source}}"),
        ("plain source", "plain target"),
    }


def test_rabbitmq_push_uses_confirmed_amqp_producer() -> None:
    """Queue publication should use the configured direct AMQP producer."""
    producer = MagicMock()
    producer_factory = MagicMock(return_value=producer)
    publisher = WiktionaryRabbitMqPublisher(
        "translated", producer_factory=producer_factory
    )
    message = {"content": "page"}

    publisher.push(message)

    producer_factory.assert_called_once_with("translated")
    producer.push_to_queue.assert_called_once_with(message)


def test_rabbitmq_push_reuses_the_producer() -> None:
    producer = MagicMock()
    producer_factory = MagicMock(return_value=producer)
    publisher = WiktionaryRabbitMqPublisher(
        "translated", producer_factory=producer_factory
    )

    publisher.push({"page": "first"})
    publisher.push({"page": "second"})

    producer_factory.assert_called_once_with("translated")
    assert producer.push_to_queue.call_count == 2


def test_generic_push_rejects_reviewed_metadata() -> None:
    publisher = WiktionaryRabbitMqPublisher(
        "translated", producer_factory=MagicMock()
    )

    with pytest.raises(WiktionaryRabbitMqPublisherError, match="does not accept"):
        publisher.push({"reviewed_fix": {}})


def test_rabbitmq_push_rejects_non_json_data_before_connecting() -> None:
    producer_factory = MagicMock()
    publisher = WiktionaryRabbitMqPublisher(
        "translated", producer_factory=producer_factory
    )

    with pytest.raises(WiktionaryRabbitMqPublisherRejectedError, match="JSON"):
        publisher.push({"content": object()})

    producer_factory.assert_not_called()


def test_rabbitmq_push_marks_producer_failure_unknown() -> None:
    producer = MagicMock()
    producer.push_to_queue.side_effect = RuntimeError("lost confirmation")
    publisher = WiktionaryRabbitMqPublisher(
        "translated", producer_factory=MagicMock(return_value=producer)
    )

    with pytest.raises(WiktionaryRabbitMqPublisherOutcomeUnknown):
        publisher.push({"content": "page"})
