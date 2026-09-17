import json
import time
from typing import Any, Callable, List, Optional, Set, Tuple

from api import entryprocessor
from api.decorator import reraise_exceptions
from api.model.word import Entry
from api.rabbitmq import RabbitMqProducer
from redis_wikicache import RedisPage as Page, RedisSite as Site
from .exceptions import TranslatedPagePushError


class PublisherError(Exception):
    pass


class WiktionaryPublisherError(PublisherError):
    pass


class WiktionaryRabbitMqPublisherError(PublisherError):
    pass


class WiktionaryRabbitMqPublisherRejectedError(WiktionaryRabbitMqPublisherError):
    """Raised when a message definitely did not reach RabbitMQ."""


class WiktionaryRabbitMqPublisherOutcomeUnknown(WiktionaryRabbitMqPublisherError):
    """Raised when broker acceptance cannot be determined safely."""


def _require_malagasy_target(translation: Any) -> None:
    """Fail closed before a publisher constructs a non-Malagasy target."""
    if translation.working_wiki_language != "mg":
        raise TranslatedPagePushError(
            "Botjagwar publication is restricted to Malagasy Wiktionary."
        )


class Publisher(object):
    @staticmethod
    def publish_translated_references(
        translation, reference_templates: Set[Tuple[str, str]]
    ):
        """Build a publisher for reference templates from one translation job."""
        def _publish_translated_references(source_wiki="en", target_wiki="mg"):
            for original_reference, translated_reference in reference_templates:
                # Check if it is a template reference, or a plain-text one
                if translated_reference.startswith(
                    "{{"
                ) or original_reference.startswith("{{"):
                    translation.create_or_rename_template_on_target_wiki(
                        source_language=source_wiki,
                        source_name=original_reference,
                        target_language=target_wiki,
                        target_name=translated_reference,
                    )

        return _publish_translated_references


class WiktionaryDirectPublisher(Publisher):

    def publish_to_wiktionary(
        self,
        translation,
        publication_guard: Optional[Callable[[], None]] = None,
    ):
        def _publish_to_wiktionary(page_title: str, entries: List[Entry]):
            """
            Push translated data and if possible avoid any information loss
            on target wiki if information is not filled in
            """
            _require_malagasy_target(translation)
            site = Site(translation.working_wiki_language, "wiktionary")
            target_page = Page(site, page_title, offline=False)

            if target_page.namespace().id != 0:
                raise TranslatedPagePushError(
                    f"Attempted to push translated page to {target_page.namespace().custom_name} "
                    f"namespace (ns:{target_page.namespace().id}). "
                    f"Can only push to ns:0 (main namespace)"
                )

            # The check below goes to the wiki and is considered expensive. Let it error out
            #   if it is ever the case, as it is not expected to happen often.

            # elif target_page.isRedirectPage():
            #     content = translation.output.wikipages(entries)
            #     target_page.put(
            #         content, translation.generate_summary(target_page, entries, content)
            #     )
            else:
                # Get entries to aggregate
                if target_page.exists():
                    wiktionary_processor_class = (
                        entryprocessor.WiktionaryProcessorFactory.create(
                            translation.working_wiki_language
                        )
                    )
                    wiktionary_processor = wiktionary_processor_class()
                    page_text = target_page.get()
                    wiktionary_processor.set_text(page_text)
                    wiktionary_processor.set_title(page_title)
                    content = page_text
                    for entry in entries:
                        content = translation.output.delete_section(
                            entry.language, content
                        )
                else:
                    content = ""

                content = content.strip()
                content += "\n"
                content += translation.output.wikipages(entries).strip()
                # Push aggregated content

                put_options = (
                    {"before_live_call": publication_guard}
                    if publication_guard is not None
                    else {}
                )
                target_page.put(
                    content,
                    translation.generate_summary(entries, target_page, content),
                    **put_options,
                )
                if translation.config.get("ninja_mode", "translator") == "1":
                    time.sleep(12)

        return _publish_to_wiktionary


class WiktionaryRabbitMqPublisher(Publisher):
    def __init__(
        self,
        queue: str = "botjagwar",
        *,
        producer_factory: Callable[[str], RabbitMqProducer] = RabbitMqProducer,
    ) -> None:
        self.queue_name = queue
        self._producer_factory = producer_factory
        self._producer: Optional[RabbitMqProducer] = None

    def push(self, message: dict[str, Any]) -> None:
        """Publish one persistent message through confirmed AMQP."""
        if "reviewed_fix" in message:
            raise WiktionaryRabbitMqPublisherRejectedError(
                "The translated queue does not accept reviewed transport metadata."
            )
        try:
            json.dumps(message)
        except (TypeError, ValueError) as exc:
            raise WiktionaryRabbitMqPublisherRejectedError(
                "The RabbitMQ message is not JSON serializable."
            ) from exc
        if self._producer is None:
            try:
                self._producer = self._producer_factory(self.queue_name)
            except Exception as exc:
                raise WiktionaryRabbitMqPublisherRejectedError(
                    "RabbitMQ rejected the connection before publication."
                ) from exc
        try:
            self._producer.push_to_queue(message)
        except Exception as exc:
            raise WiktionaryRabbitMqPublisherOutcomeUnknown(
                "RabbitMQ publication outcome is unknown."
            ) from exc

    def publish_wikipage(
        self,
        content: str,
        page_title: str,
        summary: str = "mamafa ny fihodinana",
        minor: bool = False,
        expected_content_sha256: Optional[str] = None,
        publication_guard: Optional[Callable[[], None]] = None,
    ) -> None:
        """Queue a complete page edit with an optional live-content guard."""
        message = {
            "language": "mg",  # Assuming Malagasy as the working language
            "site": "wiktionary",
            "page": page_title,
            "content": content,
            "summary": summary,
            "minor": minor,
        }
        if expected_content_sha256 is not None:
            message["expected_content_sha256"] = expected_content_sha256
        if publication_guard is not None:
            publication_guard()
        self.push(message)

    def publish_to_wiktionary(
        self,
        translation,
        publication_guard: Optional[Callable[[], None]] = None,
        publication_filter: Optional[Callable[[str, str], bool]] = None,
    ):
        @reraise_exceptions((Exception,), WiktionaryRabbitMqPublisherError)
        def _publish_to_wiktionary(page_title: str, entries: List[Entry]):
            """
            Push translated data and if possible avoid any information loss
            on target wiki if information is not filled in
            """
            _require_malagasy_target(translation)
            site = Site(translation.working_wiki_language, "wiktionary")
            target_page = Page(site, page_title, offline=False)

            if target_page.namespace().id != 0:
                raise TranslatedPagePushError(
                    f"Attempted to push translated page to {target_page.namespace().custom_name} "
                    f"namespace (ns:{target_page.namespace().id}). "
                    f"Can only push to ns:0 (main namespace)"
                )

            # The check below goes to the wiki and is considered expensive. Let it error out
            #   if it is ever the case, as it is not expected to happen often.

            # elif target_page.isRedirectPage():
            #     content = translation.output.wikipages(entries)
            #     message = {
            #         "language": translation.working_wiki_language,
            #         "site": "wiktionary",
            #         "page": page_title,
            #         "content": content,
            #         "summary": "mamafa ny fihodinana",
            #         "minor": False,
            #     }
            #     self.push(message)
            else:
                # Get entries to aggregate
                if target_page.exists():
                    wiktionary_processor_class = (
                        entryprocessor.WiktionaryProcessorFactory.create(
                            translation.working_wiki_language
                        )
                    )
                    wiktionary_processor = wiktionary_processor_class()
                    page_text = target_page.get()
                    wiktionary_processor.set_text(page_text)
                    wiktionary_processor.set_title(page_title)
                    content = page_text
                    for entry in entries:
                        content = translation.output.delete_section(
                            entry.language, content
                        )
                else:
                    content = ""

                content = content.strip()
                content += "\n"
                content += translation.output.wikipages(entries).strip()
                if publication_filter is not None and not publication_filter(
                    page_title, content
                ):
                    return False
                # Push aggregated content

                message = {
                    "language": translation.working_wiki_language,
                    "site": "wiktionary",
                    "page": page_title,
                    "content": content,
                    "summary": translation.generate_summary(
                        entries, target_page, content
                    ),
                    "minor": False,
                }
                if publication_guard is not None:
                    publication_guard()
                self.push(message)
                return True

        return _publish_to_wiktionary
