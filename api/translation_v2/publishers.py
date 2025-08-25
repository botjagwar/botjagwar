import time
from typing import List
from copy import deepcopy

import requests

from api import entryprocessor
from api.config import BotjagwarConfig
from api.decorator import reraise_exceptions
from api.model.word import Entry
from redis_wikicache import RedisPage as Page, RedisSite as Site
from .exceptions import TranslatedPagePushError


class PublisherError(Exception):
    pass


class WiktionaryPublisherError(PublisherError):
    pass


class WiktionaryRabbitMqPublisherError(PublisherError):
    pass


class Publisher(object):
    def __init__(self):
        # Load service from BotjagwarConfig
        self.config = BotjagwarConfig()
        self.service = self.config.get("service", "rabbitmq")

    @staticmethod
    def publish_translated_references(translation):
        def _publish_translated_references(source_wiki="en", target_wiki="mg"):
            reference_template_queue = deepcopy(translation.reference_template_queue)
            for original_reference, translated_reference in reference_template_queue:
                # Check if it is a template reference, or a plain-text one
                if translated_reference.startswith(
                    "{{"
                ) or original_reference.startswith("{{"):
                    translation.create_or_rename_template_on_target_wiki(
                        source_wiki,
                        original_reference,
                        target_wiki,
                        translated_reference,
                    )

            translation.reference_template_queue = set()

        return _publish_translated_references


class WiktionaryDirectPublisher(Publisher):

    def publish_to_wiktionary(self, translation):
        def _publish_to_wiktionary(page_title: str, entries: List[Entry]):
            """
            Push translated data and if possible avoid any information loss
            on target wiki if information is not filled in
            """
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
                    wiktionary_processor.set_text(target_page.get())
                    wiktionary_processor.set_title(page_title)
                    content = target_page.get()
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

                target_page.put(
                    content, translation.generate_summary(entries, target_page, content)
                )
                if translation.config.get("ninja_mode", "translator") == "1":
                    time.sleep(12)

        return _publish_to_wiktionary


class WiktionaryRabbitMqPublisher(Publisher):
    def __init__(self, queue="botjagwar"):
        super(WiktionaryRabbitMqPublisher, self).__init__()
        self.queue_name = queue

    def push(self, message: dict):
        # Publish using a REST service
        response = requests.post(
            f"http://{self.service}:8443/{self.queue_name}", json=message
        )
        if response.status_code != 204:
            if response.status_code == 400:
                raise WiktionaryRabbitMqPublisherError(
                    "Data error: " + str(response.json()["error"])
                )
            else:
                raise WiktionaryRabbitMqPublisherError(f"Unknown error: {response.text}")

    def publish_wikipage(self, content: str, page_title: str, summary: str = "mamafa ny fihodinana", minor: bool = False):
        message = {
            "language": "mg",  # Assuming Malagasy as the working language
            "site": "wiktionary",
            "page": page_title,
            "content": content,
            "summary": summary,
            "minor": minor,
        }
        self.push(message)

    def publish_to_wiktionary(self, translation):
        @reraise_exceptions((Exception,), WiktionaryRabbitMqPublisherError)
        def _publish_to_wiktionary(page_title: str, entries: List[Entry]):
            """
            Push translated data and if possible avoid any information loss
            on target wiki if information is not filled in
            """
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
                    wiktionary_processor.set_text(target_page.get())
                    wiktionary_processor.set_title(page_title)
                    content = target_page.get()
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
                self.push(message)

        return _publish_to_wiktionary
