"""Flask entry translator service with Swagger-compatible docs."""
from __future__ import annotations

import atexit
import configparser
import logging
import signal
import sys
from argparse import ArgumentParser
from http import HTTPStatus
from typing import Any, Callable, Dict, List, Optional, TypeVar

from flask import Flask, current_app, jsonify, request
from flask_swagger import swagger
from gevent import get_hub
from gevent.pywsgi import WSGIServer

from api.config import BotjagwarConfig
from api.services.definition_translation_settings import DefinitionTranslationSettingsStore
from api.services.page_check_review_queue import (
    DEFAULT_PAGE_CHECK_REVIEW_QUEUE,
    RabbitMqPageCheckReviewQueue,
    validate_review_queue_separation,
)
from api.translation_v2.core import Translation
from api.translation_v2.publishers import WiktionaryRabbitMqPublisher
from api.services.entry_translator_service import EntryTranslatorService, ServiceError


_Result = TypeVar("_Result")


def _run_blocking(operation: Callable[..., _Result], *args: Any) -> _Result:
    """Run blocking service work without stalling gevent's request loop."""
    return get_hub().threadpool.apply(operation, args)


def parse_arguments() -> ArgumentParser:
    """Parse command line arguments."""
    parser = ArgumentParser(description="Entry translator v2 service")
    parser.add_argument("-p", "--port", dest="PORT", type=int, default=8000)
    parser.add_argument("-q", "--queue", dest="QUEUE", type=str, default="botjagwar")
    parser.add_argument(
        "--page-check-queue",
        dest="PAGE_CHECK_QUEUE",
        type=str,
        default=None,
        help="RabbitMQ queue for page-check fixes (default: configured value or translated)",
    )
    parser.add_argument(
        "--page-check-review-queue",
        dest="PAGE_CHECK_REVIEW_QUEUE",
        type=str,
        default=None,
        help="RabbitMQ queue for page checks requiring manual review",
    )
    parser.add_argument(
        "-l",
        "--log-file",
        dest="LOG",
        type=str,
        default="/opt/botjagwar/user_data/entry_translator_v2.log",
    )
    parser.add_argument("--host", dest="HOST", type=str, default="127.0.0.1")
    parser.add_argument(
        "--log-level",
        dest="LOG_LEVEL",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    )
    parser.add_argument(
        "--stale-job-timeout-seconds",
        dest="STALE_JOB_TIMEOUT_SECONDS",
        type=float,
        default=300.0,
    )
    parser.add_argument(
        "--max-async-workers",
        dest="MAX_ASYNC_WORKERS",
        type=int,
        default=4,
    )
    parser.add_argument(
        "--max-pending-jobs",
        dest="MAX_PENDING_JOBS",
        type=int,
        default=21,
    )
    parser.add_argument(
        "--max-check-jobs-kept",
        dest="MAX_CHECK_JOBS_KEPT",
        type=int,
        default=100_000,
        help="Maximum page-check jobs stored in Redis (default: 100000)",
    )
    return parser


def setup_logging(log_file: str, log_level: str) -> None:
    """Setup logging configuration."""
    level = logging._nameToLevel.get(log_level.upper(), logging.INFO)
    logging.basicConfig(
        filename=log_file,
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


class EntryTranslatorApplication:
    """Factory and handlers for the entry translator v2 Flask application."""

    _SERVICE_CONFIG_KEY = "translator_service"

    @staticmethod
    def create_app(service: EntryTranslatorService) -> Flask:
        """Create the Flask application."""
        app = Flask(__name__)
        app.config[EntryTranslatorApplication._SERVICE_CONFIG_KEY] = service

        app.register_error_handler(ServiceError, EntryTranslatorApplication.handle_service_error)
        app.register_error_handler(Exception, EntryTranslatorApplication.handle_unexpected_error)

        app.add_url_rule(
            "/swagger.json",
            view_func=EntryTranslatorApplication.swagger_spec,
            methods=["GET"],
        )
        app.add_url_rule("/health", view_func=EntryTranslatorApplication.health_check, methods=["GET"])
        app.add_url_rule("/jobs", view_func=EntryTranslatorApplication.jobs, methods=["GET"])
        app.add_url_rule("/jobs/errors", view_func=EntryTranslatorApplication.job_errors, methods=["GET"])
        app.add_url_rule(
            "/page-checker/settings",
            view_func=EntryTranslatorApplication.get_page_checker_settings,
            methods=["GET"],
        )
        app.add_url_rule(
            "/page-checker/settings",
            view_func=EntryTranslatorApplication.update_page_checker_settings,
            methods=["PUT"],
        )
        app.add_url_rule(
            "/page-checker/settings/autonomous-agent",
            view_func=EntryTranslatorApplication.update_page_checker_autonomous_agent,
            methods=["PUT"],
        )
        app.add_url_rule(
            "/page-checker/settings/translation-prefilter",
            view_func=EntryTranslatorApplication.update_translation_prefilter,
            methods=["PUT"],
        )
        app.add_url_rule(
            "/page-checker/settings/job-history",
            view_func=EntryTranslatorApplication.update_page_check_job_history_limit,
            methods=["PUT"],
        )
        app.add_url_rule(
            "/definition-translation/settings",
            view_func=EntryTranslatorApplication.get_definition_translation_settings,
            methods=["GET"],
        )
        app.add_url_rule(
            "/definition-translation/settings",
            view_func=EntryTranslatorApplication.update_definition_translation_settings,
            methods=["PUT"],
        )
        app.add_url_rule(
            "/wiktionary-pages/<string:language>/jobs",
            view_func=EntryTranslatorApplication.queue_job,
            methods=["POST"],
        )
        app.add_url_rule(
            "/wiktionary-pages/<string:language>/jobs/<string:job_id>",
            view_func=EntryTranslatorApplication.get_translation_job,
            methods=["GET"],
        )
        app.add_url_rule(
            "/wiktionary-pages/<string:language>/translations",
            view_func=EntryTranslatorApplication.translate_sync,
            methods=["POST"],
        )
        app.add_url_rule(
            "/wiktionary-pages/<string:language>/<string:title>/translations",
            view_func=EntryTranslatorApplication.get_translations,
            methods=["GET"],
        )
        app.add_url_rule(
            "/wiktionary-page-snapshots/<string:language>",
            view_func=EntryTranslatorApplication.get_page_snapshot,
            methods=["GET"],
        )
        app.add_url_rule(
            "/wiktionary-pages/<string:language>/check",
            view_func=EntryTranslatorApplication.check_pages,
            methods=["POST"],
        )
        app.add_url_rule(
            "/wiktionary-pages/<string:language>/check-jobs",
            view_func=EntryTranslatorApplication.queue_page_check,
            methods=["POST"],
        )
        app.add_url_rule(
            "/wiktionary-pages/<string:language>/check-jobs",
            view_func=EntryTranslatorApplication.list_page_check_jobs,
            methods=["GET"],
        )
        app.add_url_rule(
            "/wiktionary-pages/<string:language>/check-jobs/statistics",
            view_func=EntryTranslatorApplication.get_page_check_statistics,
            methods=["GET"],
        )
        app.add_url_rule(
            "/wiktionary-pages/<string:language>/check-jobs/<string:job_id>",
            view_func=EntryTranslatorApplication.get_page_check_job,
            methods=["GET"],
        )
        app.add_url_rule(
            "/wiktionary-pages/<string:language>/<string:title>",
            view_func=EntryTranslatorApplication.get_processed_page,
            methods=["GET"],
        )

        return app

    @staticmethod
    def swagger_spec() -> Any:
        """Return the Swagger 2.0 specification for the service."""
        specification = swagger(
            current_app,
            template={
                "info": {
                    "title": "Entry Translator V2",
                    "version": "2.0",
                },
                "consumes": ["application/json"],
                "produces": ["application/json"],
                "definitions": {
                    "DescendantNode": {
                        "type": "object",
                        "required": ["lang_code", "lang"],
                        "properties": {
                            "lang_code": {"type": "string"},
                            "lang": {"type": "string"},
                            "word": {"type": "string"},
                            "roman": {"type": "string"},
                            "tags": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "raw_tags": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "ruby": {
                                "type": "array",
                                "items": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                            "sense": {"type": "string"},
                            "descendants": {
                                "type": "array",
                                "items": {"$ref": "#/definitions/DescendantNode"},
                            },
                        },
                    }
                },
            },
        )
        return jsonify(specification)

    @staticmethod
    def _get_service() -> EntryTranslatorService:
        """Fetch the translator service from the current app context."""
        service = current_app.config.get(EntryTranslatorApplication._SERVICE_CONFIG_KEY)
        if service is None:
            raise ServiceError("Translator service is not configured.", status_code=500)
        return service

    @staticmethod
    def json_error(
        message: str, status: int, details: Optional[Dict[str, Any]] = None
    ) -> tuple[Any, int]:
        """Build a consistent JSON error response."""
        payload: Dict[str, Any] = {
            "type": "error",
            "message": message,
            "status": status,
        }
        if details:
            payload["details"] = details
        return jsonify(payload), status

    @staticmethod
    def parse_title() -> str:
        """Extract the required title field from the request JSON body."""
        if not request.is_json:
            raise ServiceError("Request body must be JSON.", status_code=400)
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ServiceError("Invalid JSON payload.", status_code=400)
        title = data.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ServiceError("Field 'title' is required.", status_code=400)
        return title

    @staticmethod
    def parse_titles() -> List[str]:
        """Extract the required titles field from the request JSON body.

        Returns:
            A non-empty list of trimmed titles.

        Raises:
            ServiceError: When the request body is invalid or has no titles.
        """
        if not request.is_json:
            raise ServiceError("Request body must be JSON.", status_code=400)
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ServiceError("Invalid JSON payload.", status_code=400)
        titles = data.get("titles")
        if not isinstance(titles, list) or not titles:
            raise ServiceError("Field 'titles' must be a non-empty array.", status_code=400)
        titles = [title.strip() for title in titles if isinstance(title, str) and title.strip()]
        if not titles:
            raise ServiceError("Field 'titles' must contain at least one title.", status_code=400)
        return titles

    @staticmethod
    def parse_json_object() -> Dict[str, Any]:
        """Return the JSON request body after requiring an object payload."""
        if not request.is_json:
            raise ServiceError("Request body must be JSON.", status_code=400)
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ServiceError("Invalid JSON payload.", status_code=400)
        return data

    @staticmethod
    def handle_service_error(error: ServiceError):
        """Handle service layer errors."""
        response, status = EntryTranslatorApplication.json_error(
            error.message, error.status_code, error.details
        )
        return response, status, error.headers or {}

    @staticmethod
    def handle_unexpected_error(error: Exception):
        """Handle unexpected errors gracefully."""
        logging.exception("Unexpected error: %s", error)
        return EntryTranslatorApplication.json_error(
            "An unexpected error occurred.",
            HTTPStatus.INTERNAL_SERVER_ERROR,
            {"type": type(error).__name__, "error": str(error)},
        )

    @staticmethod
    def health_check():
        """Health check endpoint.

        ---
        responses:
          200:
            description: Service is healthy
        """
        service = EntryTranslatorApplication._get_service()
        return jsonify(service.health_status())

    @staticmethod
    def jobs():
        """Get current job queue size.

        ---
        responses:
          200:
            description: Job count
        """
        service = EntryTranslatorApplication._get_service()
        return jsonify({"jobs": service.job_count()})

    @staticmethod
    def job_errors():
        """Get recent background job errors.

        ---
        responses:
          200:
            description: Recent job errors
        """
        service = EntryTranslatorApplication._get_service()
        return jsonify({"errors": service.recent_job_errors()})

    @staticmethod
    def get_page_checker_settings() -> Any:
        """Get page-checker automation settings.

        ---
        responses:
          200:
            description: Current page-checker automation settings
            schema:
              type: object
              required:
                - watched_users
                - check_probability
                - cooldown_seconds
                - ignored_edit_summaries
                - job_history_limit
                - autonomous_agent_enabled
                - translation_prefilter_enabled
              properties:
                watched_users:
                  type: array
                  items:
                    type: string
                check_probability:
                  type: number
                  minimum: 0
                  maximum: 100
                cooldown_seconds:
                  type: number
                  minimum: 0
                  maximum: 86400
                ignored_edit_summaries:
                  type: array
                  items:
                    type: string
                job_history_limit:
                  type: integer
                  minimum: 1
                  maximum: 100000
                autonomous_agent_enabled:
                  type: boolean
                translation_prefilter_enabled:
                  type: boolean
          503:
            description: Page-checker settings storage is unavailable
        """
        service = EntryTranslatorApplication._get_service()
        return jsonify(service.get_page_checker_settings())

    @staticmethod
    def update_page_checker_settings() -> Any:
        """Replace page-checker automation settings.

        ---
        parameters:
          - in: body
            name: body
            required: true
            schema:
              type: object
              additionalProperties: false
              required:
                - watched_users
                - check_probability
                - cooldown_seconds
                - ignored_edit_summaries
              properties:
                watched_users:
                  type: array
                  items:
                    type: string
                check_probability:
                  type: number
                  minimum: 0
                  maximum: 100
                cooldown_seconds:
                  type: number
                  minimum: 0
                  maximum: 86400
                ignored_edit_summaries:
                  type: array
                  items:
                    type: string
        responses:
          200:
            description: Updated page-checker automation settings
          400:
            description: Invalid page-checker automation settings
          503:
            description: Page-checker settings storage is unavailable
        """
        service = EntryTranslatorApplication._get_service()
        payload = EntryTranslatorApplication.parse_json_object()
        return jsonify(service.update_page_checker_settings(payload))

    @staticmethod
    def update_page_checker_autonomous_agent() -> Any:
        """Enable or disable automatic GitHub fix-agent assignment.

        ---
        parameters:
          - in: body
            name: body
            required: true
            schema:
              type: object
              additionalProperties: false
              required:
                - enabled
              properties:
                enabled:
                  type: boolean
        responses:
          200:
            description: Updated autonomous-agent setting
            schema:
              type: object
              required:
                - autonomous_agent_enabled
              properties:
                autonomous_agent_enabled:
                  type: boolean
          400:
            description: Invalid autonomous-agent setting
          503:
            description: Page-checker settings storage is unavailable
        """
        service = EntryTranslatorApplication._get_service()
        payload = EntryTranslatorApplication.parse_json_object()
        return jsonify(service.update_page_checker_autonomous_agent(payload))

    @staticmethod
    def update_translation_prefilter() -> Any:
        """Enable or disable page-check prefiltering for translated pages.

        ---
        parameters:
          - in: body
            name: body
            required: true
            schema:
              type: object
              additionalProperties: false
              required:
                - enabled
              properties:
                enabled:
                  type: boolean
        responses:
          200:
            description: Updated translation-prefilter setting
            schema:
              type: object
              required:
                - translation_prefilter_enabled
              properties:
                translation_prefilter_enabled:
                  type: boolean
          400:
            description: Invalid translation-prefilter setting
          503:
            description: Page-checker settings storage is unavailable
        """
        service = EntryTranslatorApplication._get_service()
        payload = EntryTranslatorApplication.parse_json_object()
        return jsonify(service.update_translation_prefilter(payload))

    @staticmethod
    def update_page_check_job_history_limit() -> Any:
        """Replace the number of page-check jobs exposed to Atlas.

        ---
        parameters:
          - in: body
            name: body
            required: true
            schema:
              type: object
              additionalProperties: false
              required:
                - limit
              properties:
                limit:
                  type: integer
                  minimum: 1
                  maximum: 100000
        responses:
          200:
            description: Updated page-check job history limit
          400:
            description: Invalid page-check job history limit
          503:
            description: Page-checker settings storage is unavailable
        """
        service = EntryTranslatorApplication._get_service()
        payload = EntryTranslatorApplication.parse_json_object()
        return jsonify(service.update_page_check_job_history_limit(payload))

    @staticmethod
    def get_definition_translation_settings() -> Any:
        """Get definition-translation settings.

        ---
        responses:
          200:
            description: Current definition-translation settings
            schema:
              type: object
              required:
                - basic_english_gate_enabled
                - nllb_roundtrip_validation_enabled
              properties:
                basic_english_gate_enabled:
                  type: boolean
                nllb_roundtrip_validation_enabled:
                  type: boolean
          503:
            description: Definition-translation settings storage is unavailable
        """
        service = EntryTranslatorApplication._get_service()
        return jsonify(service.get_definition_translation_settings())

    @staticmethod
    def update_definition_translation_settings() -> Any:
        """Replace definition-translation settings.

        ---
        parameters:
          - in: body
            name: body
            required: true
            schema:
              type: object
              additionalProperties: false
              required:
                - basic_english_gate_enabled
                - nllb_roundtrip_validation_enabled
              properties:
                basic_english_gate_enabled:
                  type: boolean
                nllb_roundtrip_validation_enabled:
                  type: boolean
        responses:
          200:
            description: Updated definition-translation settings
          400:
            description: Invalid definition-translation settings
          503:
            description: Definition-translation settings storage is unavailable
        """
        service = EntryTranslatorApplication._get_service()
        payload = EntryTranslatorApplication.parse_json_object()
        return jsonify(service.update_definition_translation_settings(payload))

    @staticmethod
    def queue_job(language: str):
        """Queue a Wiktionary translation job.

        ---
        parameters:
          - in: path
            name: language
            required: true
            type: string
          - in: body
            name: body
            required: true
            schema:
              type: object
              required:
                - title
              properties:
                title:
                  type: string
                request_id:
                  type: string
                  format: uuid
        responses:
          202:
            description: Job queued
        """
        service = EntryTranslatorApplication._get_service()
        payload = EntryTranslatorApplication.parse_json_object()
        title = payload.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ServiceError("Field 'title' is required.", status_code=400)
        result = _run_blocking(
            service.enqueue_translation_job,
            language,
            title,
            payload.get("request_id"),
        )
        return jsonify(result), 202

    @staticmethod
    def get_translation_job(language: str, job_id: str):
        """Get the current state of an asynchronous translation job.

        ---
        parameters:
          - in: path
            name: language
            required: true
            type: string
          - in: path
            name: job_id
            required: true
            type: string
        responses:
          200:
            description: Translation job state
          404:
            description: Unknown translation job
          503:
            description: Translation job storage is unavailable
        """
        service = EntryTranslatorApplication._get_service()
        job = _run_blocking(service.get_translation_job, language, job_id)
        return jsonify(job)

    @staticmethod
    def translate_sync(language: str):
        """Translate a Wiktionary page synchronously.

        ---
        parameters:
          - in: path
            name: language
            required: true
            type: string
          - in: body
            name: body
            required: true
            schema:
              type: object
              required:
                - title
              properties:
                title:
                  type: string
        responses:
          200:
            description: Translation complete
        """
        service = EntryTranslatorApplication._get_service()
        title = EntryTranslatorApplication.parse_title()
        result = _run_blocking(service.translate_page_sync, language, title)
        return jsonify(result)

    @staticmethod
    def get_translations(language: str, title: str):
        """Get translations for a Wiktionary page.

        ---
        parameters:
          - in: path
            name: language
            required: true
            type: string
          - in: path
            name: title
            required: true
            type: string
        responses:
          200:
            description: Translation data
        """
        service = EntryTranslatorApplication._get_service()
        translations = _run_blocking(service.get_translations, language, title)
        return jsonify(translations)

    @staticmethod
    def get_processed_page(language: str, title: str):
        """Get processed Wiktionary page data.

        ---
        parameters:
          - in: path
            name: language
            required: true
            type: string
          - in: path
            name: title
            required: true
            type: string
        responses:
          200:
            description: Processed page data with optional preview-only recursive descendants
            schema:
              type: array
              items:
                type: object
                properties:
                  descendants:
                    type: array
                    items:
                      $ref: '#/definitions/DescendantNode'
        """
        service = EntryTranslatorApplication._get_service()
        data = _run_blocking(service.get_processed_page, language, title)
        return jsonify(data)

    @staticmethod
    def get_page_snapshot(language: str):
        """Get live Wiktionary content and parsed entries from one snapshot.

        ---
        parameters:
          - in: path
            name: language
            required: true
            type: string
            enum:
              - en
              - mg
          - in: query
            name: title
            required: true
            type: string
        responses:
          200:
            description: Live page content, SHA-256, namespace, and parsed entries
          400:
            description: Invalid title or unsupported Wiktionary language
          404:
            description: Page not found
          413:
            description: Page is too large for review
        """
        title = request.args.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ServiceError("Query parameter 'title' is required.", status_code=400)
        title = title.strip()
        if len(title) > 512:
            raise ServiceError("The requested page title is too long.", status_code=400)
        service = EntryTranslatorApplication._get_service()
        snapshot = _run_blocking(service.get_page_snapshot, language, title)
        return jsonify(snapshot)

    @staticmethod
    def check_pages(language: str):
        """Check Malagasy Wiktionary pages against their source wiktionaries.

        ---
        parameters:
          - in: path
            name: language
            required: true
            type: string
          - in: body
            name: body
            required: true
            schema:
              type: object
              required:
                - titles
              properties:
                titles:
                  type: array
                  items:
                    type: string
        responses:
          200:
            description: Page check results
        """
        service = EntryTranslatorApplication._get_service()
        titles = EntryTranslatorApplication.parse_titles()
        results = _run_blocking(service.check_pages, language, titles)
        return jsonify({"results": results})

    @staticmethod
    def queue_page_check(language: str):
        """Queue an asynchronous page check job.

        ---
        parameters:
          - in: path
            name: language
            required: true
            type: string
          - in: body
            name: body
            required: true
            schema:
              type: object
              required:
                - titles
              properties:
                titles:
                  type: array
                  items:
                    type: string
        responses:
          202:
            description: Page check jobs queued (one per title)
        """
        service = EntryTranslatorApplication._get_service()
        titles = EntryTranslatorApplication.parse_titles()
        result = service.enqueue_page_check(language, titles)
        return jsonify(result), 202

    @staticmethod
    def get_page_check_job(language: str, job_id: str):
        """Get the current state of an asynchronous page check job.

        ---
        parameters:
          - in: path
            name: language
            required: true
            type: string
          - in: path
            name: job_id
            required: true
            type: string
        responses:
          200:
            description: Page check job state
          404:
            description: Unknown page check job
        """
        service = EntryTranslatorApplication._get_service()
        job = service.get_page_check_job(job_id)
        return jsonify(job)

    @staticmethod
    def list_page_check_jobs(language: str):
        """List recent asynchronous page check jobs.

        ---
        parameters:
          - in: path
            name: language
            required: true
            type: string
          - in: query
            name: limit
            required: false
            type: integer
        responses:
          200:
            description: Page check job summaries, newest first
        """
        service = EntryTranslatorApplication._get_service()
        try:
            limit = int(request.args.get("limit", "20"))
        except ValueError:
            limit = 20
        jobs = service.list_page_check_jobs(language=language, limit=limit)
        return jsonify({"jobs": jobs})

    @staticmethod
    def get_page_check_statistics(language: str):
        """Return aggregate statistics for retained page-check jobs.

        ---
        parameters:
          - in: path
            name: language
            required: true
            type: string
        responses:
          200:
            description: Page-check statistics for supported UTC periods
          503:
            description: Page-check history is temporarily unavailable
        """
        service = EntryTranslatorApplication._get_service()
        statistics = service.get_page_check_statistics(language)
        return jsonify(statistics)


def _page_check_queue_name(override: Optional[str] = None) -> str:
    """Resolve the page-check publication queue from CLI or configuration."""
    if override and override.strip():
        return override.strip()
    return _rabbitmq_queue_name("page_check_queue", "translated")


def _rabbitmq_queue_name(key: str, default: str) -> str:
    """Resolve one RabbitMQ queue role from configuration with a safe default."""
    try:
        configured_queue = BotjagwarConfig().get(key, "rabbitmq")
    except (configparser.Error, KeyError):
        return default
    return configured_queue.strip() or default


def _page_check_review_queue_name(override: Optional[str] = None) -> str:
    """Resolve the dedicated manual-review queue from CLI or configuration."""
    if override and override.strip():
        return override.strip()
    return _rabbitmq_queue_name(
        "page_check_review_queue",
        DEFAULT_PAGE_CHECK_REVIEW_QUEUE,
    )


def build_service(
    queue_name: str,
    stale_job_timeout_seconds: float = 300.0,
    max_async_workers: int = 4,
    max_pending_jobs: int = 21,
    page_check_queue_name: Optional[str] = None,
    max_check_jobs_kept: int = 100_000,
    page_check_review_queue_name: Optional[str] = None,
) -> EntryTranslatorService:
    """Build the translator service with dependencies."""
    definition_settings_store = DefinitionTranslationSettingsStore()
    translation = Translation(
        basic_english_gate_enabled=lambda: (
            definition_settings_store.get().basic_english_gate_enabled
        ),
        nllb_roundtrip_validation_enabled=lambda: (
            definition_settings_store.get().nllb_roundtrip_validation_enabled
        ),
    )
    resolved_page_check_queue = _page_check_queue_name(page_check_queue_name)
    resolved_review_queue = _page_check_review_queue_name(
        page_check_review_queue_name
    )
    generic_queue = _rabbitmq_queue_name("queue", "botjagwar")
    validate_review_queue_separation(
        resolved_review_queue,
        {
            queue_name,
            resolved_page_check_queue,
            generic_queue,
        },
    )
    publisher = WiktionaryRabbitMqPublisher(queue_name)
    page_check_publisher = WiktionaryRabbitMqPublisher(
        resolved_page_check_queue
    )
    page_check_review_queue = RabbitMqPageCheckReviewQueue(
        resolved_review_queue
    )
    return EntryTranslatorService(
        translation=translation,
        publisher=publisher,
        page_check_publisher=page_check_publisher,
        page_check_review_queue=page_check_review_queue,
        definition_translation_settings_store=definition_settings_store,
        stale_job_timeout_seconds=stale_job_timeout_seconds,
        max_async_workers=max_async_workers,
        max_pending_jobs=max_pending_jobs,
        max_check_jobs_kept=max_check_jobs_kept,
    )


def build_server(app: Flask, host: str, port: int) -> WSGIServer:
    """Build a gevent WSGI server instance."""
    return WSGIServer((host, port), app)


def _shutdown_handler(
    http_server: Optional[WSGIServer],
    service: Optional[EntryTranslatorService] = None,
) -> None:
    """Handle process shutdown."""
    logging.info("Entry translator v2 shutting down.")
    if http_server is not None:
        http_server.stop()
    if service is not None:
        service.shutdown(wait=False, cancel_futures=True)


def main() -> None:
    """Run the service entry point."""
    parser = parse_arguments()
    args = parser.parse_args()
    setup_logging(args.LOG, args.LOG_LEVEL)

    service = build_service(
        args.QUEUE,
        args.STALE_JOB_TIMEOUT_SECONDS,
        args.MAX_ASYNC_WORKERS,
        args.MAX_PENDING_JOBS,
        page_check_queue_name=args.PAGE_CHECK_QUEUE,
        max_check_jobs_kept=args.MAX_CHECK_JOBS_KEPT,
        page_check_review_queue_name=args.PAGE_CHECK_REVIEW_QUEUE,
    )
    app = EntryTranslatorApplication.create_app(service)
    http_server = build_server(app, args.HOST, args.PORT)

    atexit.register(_shutdown_handler, http_server, service)
    signal.signal(signal.SIGINT, lambda *_: _shutdown_handler(http_server, service))
    signal.signal(signal.SIGTERM, lambda *_: _shutdown_handler(http_server, service))

    try:
        http_server.serve_forever()
    finally:
        _shutdown_handler(http_server, service)
    sys.exit(0)


if __name__ == "__main__":
    main()
