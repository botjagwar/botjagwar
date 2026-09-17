from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable, Dict, List

import pytest

import entry_translator_v2
from entry_translator_v2 import EntryTranslatorApplication
from api.services.entry_translator_service import ServiceError
from api.services.page_checker_settings import PageCheckerSettings


class DummyService:
    def __init__(self) -> None:
        self.calls: Dict[str, Any] = {}
        self.error: Exception | None = None

    def health_status(self) -> Dict[str, Any]:
        return {"status": "healthy", "jobs": 2}

    def job_count(self) -> int:
        return 2

    def recent_job_errors(self) -> List[Dict[str, Any]]:
        return [{"message": "boom"}]

    def get_page_checker_settings(self) -> Dict[str, Any]:
        """Return the current fake page-checker settings."""
        self.calls["settings_get"] = True
        if self.error:
            raise self.error
        return PageCheckerSettings().serialise()

    def update_page_checker_settings(self, payload: Any) -> Dict[str, Any]:
        """Validate and return fake page-checker settings."""
        self.calls["settings_update"] = payload
        if self.error:
            raise self.error
        return PageCheckerSettings.from_monitoring_payload(
            payload
        ).serialise_monitoring()

    def update_page_checker_autonomous_agent(self, payload: Any) -> Dict[str, bool]:
        """Validate and return the fake autonomous-agent setting."""
        self.calls["autonomous_agent_update"] = payload
        if self.error:
            raise self.error
        if (
            not isinstance(payload, dict)
            or set(payload) != {"enabled"}
            or not isinstance(payload["enabled"], bool)
        ):
            raise ServiceError("Invalid autonomous agent setting.", status_code=400)
        return {"autonomous_agent_enabled": payload["enabled"]}

    def update_translation_prefilter(self, payload: Any) -> Dict[str, bool]:
        """Validate and return the fake translation-prefilter setting."""
        self.calls["translation_prefilter_update"] = payload
        if (
            not isinstance(payload, dict)
            or set(payload) != {"enabled"}
            or not isinstance(payload["enabled"], bool)
        ):
            raise ServiceError(
                "Invalid translation prefilter setting.", status_code=400
            )
        return {"translation_prefilter_enabled": payload["enabled"]}

    def update_page_check_job_history_limit(self, payload: Any) -> Dict[str, int]:
        """Validate and return a fake page-check job history limit."""
        self.calls["job_history_limit_update"] = payload
        if (
            not isinstance(payload, dict)
            or set(payload) != {"limit"}
            or not isinstance(payload["limit"], int)
            or not 1 <= payload["limit"] <= 100_000
        ):
            raise ServiceError("Invalid job history limit.", status_code=400)
        return {"job_history_limit": payload["limit"]}

    def get_definition_translation_settings(self) -> Dict[str, bool]:
        """Return fake definition-translation settings."""
        self.calls["definition_settings_get"] = True
        return {
            "basic_english_gate_enabled": False,
            "nllb_roundtrip_validation_enabled": True,
        }

    def update_definition_translation_settings(self, payload: Any) -> Dict[str, bool]:
        """Validate and return fake definition-translation settings."""
        self.calls["definition_settings_update"] = payload
        if (
            set(payload)
            != {
                "basic_english_gate_enabled",
                "nllb_roundtrip_validation_enabled",
            }
            or any(not isinstance(value, bool) for value in payload.values())
        ):
            raise ServiceError("Invalid definition translation settings.", status_code=400)
        return payload

    def enqueue_translation_job(
        self,
        language: str,
        title: str,
        request_id: str | None = None,
    ) -> Dict[str, Any]:
        self.calls["queue"] = (language, title, request_id)
        if self.error:
            raise self.error
        return {
            "job_id": "translation-job-1",
            "language": language,
            "title": title,
            "status": "pending",
            "stage": "queued",
            "publication_state": "not_queued",
            "created_at": 1,
            "last_updated_at": 1,
            "result": None,
            "error": None,
            "message": "translation job queued",
        }

    def get_translation_job(self, language: str, job_id: str) -> Dict[str, Any]:
        self.calls["translation_job_get"] = (language, job_id)
        if self.error:
            raise self.error
        return {
            "job_id": job_id,
            "language": language,
            "title": "hello",
            "status": "done",
            "stage": "completed",
            "publication_state": "queued",
            "created_at": 1,
            "last_updated_at": 2,
            "result": {"status": "publication_queued", "published": False},
            "error": None,
            "message": "translation job queued",
        }

    def translate_page_sync(self, language: str, title: str) -> Dict[str, Any]:
        self.calls["sync"] = (language, title)
        if self.error:
            raise self.error
        return {
            "title": title,
            "language": language,
            "status": "published",
            "message": "Translated entries were published.",
            "entries_count": 2,
            "published": True,
            "error_type": None,
        }

    def get_translations(self, language: str, title: str) -> List[Dict[str, Any]]:
        self.calls["translations"] = (language, title)
        if self.error:
            raise self.error
        return [{"t": "one"}]

    def get_processed_page(self, language: str, title: str) -> List[Dict[str, Any]]:
        self.calls["processed"] = (language, title)
        if self.error:
            raise self.error
        return [{"entry": "data"}]

    def get_page_snapshot(self, language: str, title: str) -> Dict[str, Any]:
        """Return one fake live page snapshot."""
        self.calls["snapshot"] = (language, title)
        if self.error:
            raise self.error
        return {
            "language": language,
            "title": title,
            "namespace": 0,
            "content": "raw content",
            "content_sha256": "a" * 64,
            "entries": [],
            "content_trust": "untrusted_wiktionary_content",
        }

    def check_pages(self, language: str, titles: List[str]) -> List[Dict[str, Any]]:
        self.calls["check"] = (language, titles)
        if self.error:
            raise self.error
        return [
            {"word": title, "status": "good", "message": "ok"}
            for title in titles
        ]

    def enqueue_page_check(self, language: str, titles: List[str]) -> Dict[str, Any]:
        self.calls["check_job"] = (language, titles)
        if self.error:
            raise self.error
        return {
            "jobs": [
                {
                    "job_id": f"job-{index}",
                    "language": language,
                    "titles": [title],
                    "status": "pending",
                    "created_at": 1,
                    "last_updated_at": 1,
                    "attempts": 0,
                    "progress": 0,
                    "results": None,
                    "error": None,
                }
                for index, title in enumerate(titles, start=1)
            ]
        }

    def get_page_check_job(self, job_id: str) -> Dict[str, Any]:
        self.calls["check_job_get"] = job_id
        if self.error:
            raise self.error
        return {
            "job_id": job_id,
            "language": "mg",
            "titles": ["alika"],
            "status": "done",
            "created_at": 1,
            "last_updated_at": 1,
            "attempts": 0,
            "progress": 100,
            "results": [],
            "error": None,
        }

    def list_page_check_jobs(
        self, language: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        self.calls["check_job_list"] = (language, limit)
        if self.error:
            raise self.error
        return [
            {
                "job_id": "job-1",
                "language": language,
                "titles": ["alika"],
                "status": "done",
                "created_at": 1,
                "last_updated_at": 1,
                "attempts": 0,
                "progress": 100,
                "error": None,
                "result_counts": {"good": 1, "fixed": 0, "unverifiable": 0, "error": 0},
            }
        ]

    def get_page_check_statistics(self, language: str) -> Dict[str, Any]:
        """Return a fake retained-job statistics response."""
        self.calls["check_job_statistics"] = language
        if self.error:
            raise self.error
        return {
            "language": language,
            "generated_at": 10,
            "timezone": "UTC",
            "retention_limit": 200,
            "retained_job_count": 12,
            "statistics": [
                {
                    "period": "today",
                    "period_start": 0,
                    "period_end": 10,
                    "job_count": 4,
                    "checked_count": 4,
                    "assessable_count": 4,
                    "result_counts": {
                        "good": 3,
                        "fixed": 1,
                        "unverifiable": 0,
                        "error": 0,
                    },
                    "good_percentage": 75.0,
                    "grade": "C",
                }
            ],
        }


def test_app_health_and_jobs() -> None:
    service = DummyService()
    app = EntryTranslatorApplication.create_app(service)

    client = app.test_client()

    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "healthy", "jobs": 2}

    response = client.get("/jobs")
    assert response.status_code == 200
    assert response.get_json() == {"jobs": 2}

    response = client.get("/jobs/errors")
    assert response.status_code == 200
    assert response.get_json() == {"errors": [{"message": "boom"}]}


def test_swagger_spec() -> None:
    """Test the generated Swagger document describes the public v2 routes."""
    app = EntryTranslatorApplication.create_app(DummyService())

    response = app.test_client().get("/swagger.json")

    assert response.status_code == 200
    specification = response.get_json()
    assert specification["swagger"] == "2.0"
    assert specification["info"] == {
        "title": "Entry Translator V2",
        "version": "2.0",
    }
    assert specification["consumes"] == ["application/json"]
    assert specification["produces"] == ["application/json"]
    descendant_schema = specification["definitions"]["DescendantNode"]
    assert descendant_schema["required"] == ["lang_code", "lang"]
    assert descendant_schema["properties"]["descendants"]["items"] == {
        "$ref": "#/definitions/DescendantNode"
    }
    assert "get" in specification["paths"]["/health"]
    assert "post" in specification["paths"][
        "/wiktionary-pages/{language}/translations"
    ]
    translation_jobs_path = specification["paths"][
        "/wiktionary-pages/{language}/jobs"
    ]
    assert "202" in translation_jobs_path["post"]["responses"]
    assert "get" in specification["paths"][
        "/wiktionary-pages/{language}/jobs/{job_id}"
    ]
    processed_page_schema = specification["paths"][
        "/wiktionary-pages/{language}/{title}"
    ]["get"]["responses"]["200"]["schema"]
    assert processed_page_schema["items"]["properties"]["descendants"]["items"] == {
        "$ref": "#/definitions/DescendantNode"
    }
    snapshot_path = specification["paths"][
        "/wiktionary-page-snapshots/{language}"
    ]["get"]
    assert snapshot_path["parameters"][1]["name"] == "title"
    assert "413" in snapshot_path["responses"]
    settings_path = specification["paths"]["/page-checker/settings"]
    assert {"get", "put"}.issubset(settings_path)
    settings_schema = settings_path["put"]["parameters"][0]["schema"]
    assert set(settings_schema["required"]) == {
        "watched_users",
        "check_probability",
        "cooldown_seconds",
        "ignored_edit_summaries",
    }
    assert settings_schema["properties"]["check_probability"] == {
        "type": "number",
        "minimum": 0,
        "maximum": 100,
    }
    assert settings_schema["properties"]["cooldown_seconds"]["minimum"] == 0
    get_settings_schema = settings_path["get"]["responses"]["200"]["schema"]
    assert "autonomous_agent_enabled" in get_settings_schema["required"]
    assert get_settings_schema["properties"]["autonomous_agent_enabled"] == {
        "type": "boolean"
    }
    assert get_settings_schema["properties"]["translation_prefilter_enabled"] == {
        "type": "boolean"
    }
    assert get_settings_schema["properties"]["job_history_limit"] == {
        "type": "integer",
        "minimum": 1,
        "maximum": 100000,
    }
    autonomous_path = specification["paths"][
        "/page-checker/settings/autonomous-agent"
    ]
    assert autonomous_path["put"]["parameters"][0]["schema"]["properties"][
        "enabled"
    ] == {"type": "boolean"}
    prefilter_path = specification["paths"][
        "/page-checker/settings/translation-prefilter"
    ]
    assert prefilter_path["put"]["parameters"][0]["schema"]["properties"][
        "enabled"
    ] == {"type": "boolean"}
    job_history_path = specification["paths"][
        "/page-checker/settings/job-history"
    ]
    assert job_history_path["put"]["parameters"][0]["schema"]["properties"][
        "limit"
    ] == {"type": "integer", "minimum": 1, "maximum": 100000}
    definition_settings_path = specification["paths"][
        "/definition-translation/settings"
    ]
    assert {"get", "put"}.issubset(definition_settings_path)
    assert definition_settings_path["put"]["parameters"][0]["schema"][
        "properties"
    ]["basic_english_gate_enabled"] == {"type": "boolean"}
    assert definition_settings_path["put"]["parameters"][0]["schema"][
        "properties"
    ]["nllb_roundtrip_validation_enabled"] == {"type": "boolean"}
    assert "get" in specification["paths"][
        "/wiktionary-pages/{language}/check-jobs/statistics"
    ]


def test_page_checker_settings_routes_return_canonical_settings() -> None:
    """GET and PUT expose the service settings in canonical JSON form."""
    service = DummyService()
    client = EntryTranslatorApplication.create_app(service).test_client()

    response = client.get("/page-checker/settings")

    assert response.status_code == 200
    assert response.get_json() == {
        "watched_users": ["Bot-Jagwar"],
        "check_probability": 10,
        "cooldown_seconds": 5,
        "ignored_edit_summaries": [
            "fanitsiana famaritana",
            "Dikanteny: es",
        ],
        "job_history_limit": 2500,
        "autonomous_agent_enabled": False,
        "translation_prefilter_enabled": False,
    }
    assert service.calls["settings_get"] is True

    payload = {
        "watched_users": [" Bot_Jagwar ", "bot Jagwar"],
        "check_probability": 40,
        "cooldown_seconds": 2.5,
        "ignored_edit_summaries": [" skip ", "skip"],
    }
    response = client.put("/page-checker/settings", json=payload)

    assert response.status_code == 200
    assert response.get_json() == {
        "watched_users": ["Bot_Jagwar"],
        "check_probability": 40,
        "cooldown_seconds": 2.5,
        "ignored_edit_summaries": ["skip"],
    }
    assert service.calls["settings_update"] == payload

    response = client.put(
        "/page-checker/settings/autonomous-agent",
        json={"enabled": True},
    )

    assert response.status_code == 200
    assert response.get_json() == {"autonomous_agent_enabled": True}
    assert service.calls["autonomous_agent_update"] == {"enabled": True}

    response = client.put(
        "/page-checker/settings/translation-prefilter",
        json={"enabled": True},
    )

    assert response.status_code == 200
    assert response.get_json() == {"translation_prefilter_enabled": True}
    assert service.calls["translation_prefilter_update"] == {"enabled": True}

    response = client.put(
        "/page-checker/settings/job-history",
        json={"limit": 7500},
    )
    assert response.status_code == 200
    assert response.get_json() == {"job_history_limit": 7500}
    assert service.calls["job_history_limit_update"] == {"limit": 7500}

    response = client.put(
        "/page-checker/settings/job-history",
        json={"limit": 100001},
    )
    assert response.status_code == 400
    assert response.get_json()["message"] == "Invalid job history limit."

    response = client.put(
        "/page-checker/settings/autonomous-agent",
        json={"enabled": 1},
    )
    assert response.status_code == 400
    assert response.get_json()["message"] == "Invalid autonomous agent setting."

    response = client.put(
        "/page-checker/settings/translation-prefilter",
        json={"enabled": 1},
    )
    assert response.status_code == 400
    assert response.get_json()["message"] == "Invalid translation prefilter setting."


def test_update_page_checker_settings_requires_a_json_object() -> None:
    """PUT rejects non-JSON and non-object request bodies before the service."""
    service = DummyService()
    client = EntryTranslatorApplication.create_app(service).test_client()

    response = client.put("/page-checker/settings", data="not-json")
    assert response.status_code == 400
    assert response.get_json()["message"] == "Request body must be JSON."

    response = client.put(
        "/page-checker/settings",
        data="[]",
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.get_json()["message"] == "Invalid JSON payload."

    service.error = ServiceError("Invalid page checker settings.", status_code=400)
    response = client.put(
        "/page-checker/settings",
        json={
            "watched_users": [],
            "check_probability": 10,
            "cooldown_seconds": 5,
            "ignored_edit_summaries": [],
        },
    )
    assert response.status_code == 400
    assert response.get_json()["message"] == "Invalid page checker settings."


def test_definition_translation_settings_routes() -> None:
    """Definition settings routes expose and validate the gate flag."""
    service = DummyService()
    client = EntryTranslatorApplication.create_app(service).test_client()

    response = client.get("/definition-translation/settings")
    assert response.status_code == 200
    assert response.get_json() == {
        "basic_english_gate_enabled": False,
        "nllb_roundtrip_validation_enabled": True,
    }

    response = client.put(
        "/definition-translation/settings",
        json={
            "basic_english_gate_enabled": True,
            "nllb_roundtrip_validation_enabled": False,
        },
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "basic_english_gate_enabled": True,
        "nllb_roundtrip_validation_enabled": False,
    }
    assert service.calls["definition_settings_update"] == {
        "basic_english_gate_enabled": True,
        "nllb_roundtrip_validation_enabled": False,
    }

    response = client.put(
        "/definition-translation/settings",
        json={"basic_english_gate_enabled": 1},
    )
    assert response.status_code == 400


def test_queue_job_requires_json() -> None:
    service = DummyService()
    app = EntryTranslatorApplication.create_app(service)
    client = app.test_client()

    response = client.post("/wiktionary-pages/en/jobs", data="not-json")

    assert response.status_code == 400
    assert response.get_json()["message"] == "Request body must be JSON."


def test_queue_job_rejects_invalid_payloads() -> None:
    """Test title validation for malformed JSON request payloads."""
    service = DummyService()
    app = EntryTranslatorApplication.create_app(service)
    client = app.test_client()

    response = client.post(
        "/wiktionary-pages/en/jobs",
        data="[]",
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.get_json()["message"] == "Invalid JSON payload."

    response = client.post("/wiktionary-pages/en/jobs", json={"title": "  "})

    assert response.status_code == 400
    assert response.get_json()["message"] == "Field 'title' is required."


def test_queue_job_success() -> None:
    service = DummyService()
    app = EntryTranslatorApplication.create_app(service)
    client = app.test_client()

    response = client.post("/wiktionary-pages/en/jobs", json={"title": "hello"})

    assert response.status_code == 202
    assert response.get_json() == {
        "job_id": "translation-job-1",
        "language": "en",
        "title": "hello",
        "status": "pending",
        "stage": "queued",
        "publication_state": "not_queued",
        "created_at": 1,
        "last_updated_at": 1,
        "result": None,
        "error": None,
        "message": "translation job queued",
    }
    assert service.calls["queue"] == ("en", "hello", None)


def test_queue_job_forwards_client_request_id() -> None:
    service = DummyService()
    client = EntryTranslatorApplication.create_app(service).test_client()
    request_id = "9c9a6a48-2304-4505-9cfe-57fbddc88bb1"

    response = client.post(
        "/wiktionary-pages/fr/jobs",
        json={"title": "maison", "request_id": request_id},
    )

    assert response.status_code == 202
    assert service.calls["queue"] == ("fr", "maison", request_id)


def test_get_translation_job_success() -> None:
    service = DummyService()
    client = EntryTranslatorApplication.create_app(service).test_client()

    response = client.get(
        "/wiktionary-pages/en/jobs/translation-job-1"
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["job_id"] == "translation-job-1"
    assert payload["status"] == "done"
    assert payload["result"]["status"] == "publication_queued"
    assert service.calls["translation_job_get"] == (
        "en",
        "translation-job-1",
    )


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (ServiceError("Unknown translation job.", status_code=404), 404),
        (
            ServiceError(
                "Translation job history is temporarily unavailable.",
                status_code=503,
            ),
            503,
        ),
    ],
)
def test_get_translation_job_maps_service_errors(
    error: ServiceError, expected_status: int
) -> None:
    service = DummyService()
    service.error = error
    client = EntryTranslatorApplication.create_app(service).test_client()

    response = client.get("/wiktionary-pages/fr/jobs/translation-job-1")

    assert response.status_code == expected_status
    assert response.get_json()["message"] == error.message
    assert service.calls["translation_job_get"] == (
        "fr",
        "translation-job-1",
    )


def test_translate_sync_returns_structured_result() -> None:
    service = DummyService()
    app = EntryTranslatorApplication.create_app(service)
    client = app.test_client()

    response = client.post(
        "/wiktionary-pages/en/translations", json={"title": "hello"}
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "published"
    assert payload["entries_count"] == 2
    assert payload["published"] is True
    assert service.calls["sync"] == ("en", "hello")


def test_translate_sync_service_error() -> None:
    service = DummyService()
    service.error = ServiceError("boom", status_code=500, details={"info": "x"})
    app = EntryTranslatorApplication.create_app(service)
    client = app.test_client()

    response = client.post(
        "/wiktionary-pages/en/translations", json={"title": "hello"}
    )

    assert response.status_code == 500
    payload = response.get_json()
    assert payload["message"] == "boom"
    assert payload["details"] == {"info": "x"}


def test_service_error_includes_retry_after_header() -> None:
    service = DummyService()
    service.error = ServiceError(
        "slow down",
        status_code=429,
        headers={"Retry-After": "7"},
    )
    client = EntryTranslatorApplication.create_app(service).test_client()

    response = client.get("/wiktionary-pages/en/hello/translations")

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "7"


def test_get_translations_unexpected_error() -> None:
    service = DummyService()
    service.error = ValueError("fail")
    app = EntryTranslatorApplication.create_app(service)
    client = app.test_client()

    response = client.get("/wiktionary-pages/en/hello/translations")

    assert response.status_code == 500
    payload = response.get_json()
    assert payload["message"] == "An unexpected error occurred."
    assert payload["details"]["type"] == "ValueError"


def test_get_translations_success() -> None:
    """Test the translation preview endpoint response."""
    service = DummyService()
    app = EntryTranslatorApplication.create_app(service)
    client = app.test_client()

    response = client.get("/wiktionary-pages/en/hello/translations")

    assert response.status_code == 200
    assert response.get_json() == [{"t": "one"}]
    assert service.calls["translations"] == ("en", "hello")


def test_get_processed_page_success() -> None:
    service = DummyService()
    app = EntryTranslatorApplication.create_app(service)
    client = app.test_client()

    response = client.get("/wiktionary-pages/en/hello")

    assert response.status_code == 200
    assert response.get_json() == [{"entry": "data"}]


def test_get_page_snapshot_success_and_title_validation() -> None:
    """The snapshot route uses a query title so slash-containing titles remain valid."""
    service = DummyService()
    client = EntryTranslatorApplication.create_app(service).test_client()

    response = client.get("/wiktionary-page-snapshots/en?title=foo%2Fbar")

    assert response.status_code == 200
    assert response.get_json()["content_sha256"] == "a" * 64
    assert service.calls["snapshot"] == ("en", "foo/bar")

    missing = client.get("/wiktionary-page-snapshots/en")
    assert missing.status_code == 400
    assert missing.get_json()["message"] == "Query parameter 'title' is required."

    too_long = client.get(
        "/wiktionary-page-snapshots/en",
        query_string={"title": "x" * 513},
    )
    assert too_long.status_code == 400
    assert too_long.get_json()["message"] == "The requested page title is too long."


def test_check_pages_success() -> None:
    service = DummyService()
    app = EntryTranslatorApplication.create_app(service)
    client = app.test_client()

    response = client.post(
        "/wiktionary-pages/mg/check", json={"titles": ["alika", "soa"]}
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert [result["word"] for result in payload["results"]] == ["alika", "soa"]
    assert all(result["status"] == "good" for result in payload["results"])
    assert service.calls["check"] == ("mg", ["alika", "soa"])


def test_check_pages_rejects_invalid_payloads() -> None:
    service = DummyService()
    app = EntryTranslatorApplication.create_app(service)
    client = app.test_client()

    response = client.post("/wiktionary-pages/mg/check", data="not-json")
    assert response.status_code == 400
    assert response.get_json()["message"] == "Request body must be JSON."

    response = client.post("/wiktionary-pages/mg/check", data="[]", content_type="application/json")
    assert response.status_code == 400
    assert response.get_json()["message"] == "Invalid JSON payload."

    response = client.post("/wiktionary-pages/mg/check", json={"titles": []})
    assert response.status_code == 400
    assert response.get_json()["message"] == "Field 'titles' must be a non-empty array."

    response = client.post("/wiktionary-pages/mg/check", json={"titles": ["  "]})
    assert response.status_code == 400
    assert response.get_json()["message"] == "Field 'titles' must contain at least one title."


def test_check_pages_service_error() -> None:
    service = DummyService()
    service.error = ServiceError("boom", status_code=500, details={"info": "x"})
    app = EntryTranslatorApplication.create_app(service)
    client = app.test_client()

    response = client.post("/wiktionary-pages/mg/check", json={"titles": ["alika"]})

    assert response.status_code == 500
    payload = response.get_json()
    assert payload["message"] == "boom"
    assert payload["details"] == {"info": "x"}


def test_queue_page_check_success() -> None:
    service = DummyService()
    app = EntryTranslatorApplication.create_app(service)
    client = app.test_client()

    response = client.post(
        "/wiktionary-pages/mg/check-jobs", json={"titles": ["alika", "soa"]}
    )

    assert response.status_code == 202
    payload = response.get_json()
    assert [job["job_id"] for job in payload["jobs"]] == ["job-1", "job-2"]
    assert all(job["status"] == "pending" for job in payload["jobs"])
    assert service.calls["check_job"] == ("mg", ["alika", "soa"])


def test_queue_page_check_rejects_invalid_payloads() -> None:
    service = DummyService()
    app = EntryTranslatorApplication.create_app(service)
    client = app.test_client()

    response = client.post("/wiktionary-pages/mg/check-jobs", data="not-json")
    assert response.status_code == 400
    assert response.get_json()["message"] == "Request body must be JSON."

    response = client.post(
        "/wiktionary-pages/mg/check-jobs", json={"titles": []}
    )
    assert response.status_code == 400
    assert response.get_json()["message"] == "Field 'titles' must be a non-empty array."

    response = client.post(
        "/wiktionary-pages/mg/check-jobs", json={"titles": ["  "]}
    )
    assert response.status_code == 400
    assert response.get_json()["message"] == "Field 'titles' must contain at least one title."


def test_queue_page_check_service_error() -> None:
    service = DummyService()
    service.error = ServiceError("Page check capacity is currently full.", status_code=503)
    app = EntryTranslatorApplication.create_app(service)
    client = app.test_client()

    response = client.post(
        "/wiktionary-pages/mg/check-jobs", json={"titles": ["alika"]}
    )

    assert response.status_code == 503
    assert response.get_json()["message"] == "Page check capacity is currently full."


def test_get_page_check_job_success() -> None:
    service = DummyService()
    app = EntryTranslatorApplication.create_app(service)
    client = app.test_client()

    response = client.get("/wiktionary-pages/mg/check-jobs/job-1")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["job_id"] == "job-1"
    assert payload["status"] == "done"
    assert service.calls["check_job_get"] == "job-1"


def test_get_page_check_job_not_found() -> None:
    service = DummyService()
    service.error = ServiceError("Unknown page check job.", status_code=404)
    app = EntryTranslatorApplication.create_app(service)
    client = app.test_client()

    response = client.get("/wiktionary-pages/mg/check-jobs/unknown")

    assert response.status_code == 404
    assert response.get_json()["message"] == "Unknown page check job."


def test_list_page_check_jobs() -> None:
    service = DummyService()
    app = EntryTranslatorApplication.create_app(service)
    client = app.test_client()

    response = client.get("/wiktionary-pages/mg/check-jobs")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["jobs"][0]["job_id"] == "job-1"
    assert payload["jobs"][0]["result_counts"]["good"] == 1
    assert service.calls["check_job_list"] == ("mg", 20)


def test_list_page_check_jobs_accepts_limit() -> None:
    service = DummyService()
    app = EntryTranslatorApplication.create_app(service)
    client = app.test_client()

    response = client.get("/wiktionary-pages/mg/check-jobs?limit=5")

    assert response.status_code == 200
    assert service.calls["check_job_list"] == ("mg", 5)


def test_list_page_check_jobs_ignores_invalid_limit() -> None:
    service = DummyService()
    app = EntryTranslatorApplication.create_app(service)
    client = app.test_client()

    response = client.get("/wiktionary-pages/mg/check-jobs?limit=abc")

    assert response.status_code == 200
    assert service.calls["check_job_list"] == ("mg", 20)


def test_get_page_check_statistics() -> None:
    service = DummyService()
    app = EntryTranslatorApplication.create_app(service)
    client = app.test_client()

    response = client.get("/wiktionary-pages/mg/check-jobs/statistics")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["retention_limit"] == 200
    assert payload["statistics"][0]["result_counts"]["good"] == 3
    assert service.calls["check_job_statistics"] == "mg"


def test_parse_arguments_defaults() -> None:
    parser = entry_translator_v2.parse_arguments()
    args = parser.parse_args([])

    assert args.PORT == 8000
    assert args.QUEUE == "botjagwar"
    assert args.PAGE_CHECK_QUEUE is None
    assert args.PAGE_CHECK_REVIEW_QUEUE is None
    assert args.HOST == "127.0.0.1"
    assert args.MAX_ASYNC_WORKERS == 4
    assert args.MAX_PENDING_JOBS == 21
    assert args.MAX_CHECK_JOBS_KEPT == 100_000

    configured_args = parser.parse_args(["--max-check-jobs-kept", "350"])
    assert configured_args.MAX_CHECK_JOBS_KEPT == 350


def test_setup_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test logging configuration maps named levels to logging constants."""
    calls: Dict[str, Any] = {}

    def fake_basic_config(**kwargs: Any) -> None:
        calls.update(kwargs)

    monkeypatch.setattr(entry_translator_v2.logging, "basicConfig", fake_basic_config)

    entry_translator_v2.setup_logging("entry.log", "debug")

    assert calls["filename"] == "entry.log"
    assert calls["level"] == entry_translator_v2.logging.DEBUG


def test_missing_service_returns_error() -> None:
    """Test the app reports a configured error when no service is registered."""
    app = entry_translator_v2.Flask("missing-service")
    app.register_error_handler(ServiceError, EntryTranslatorApplication.handle_service_error)
    app.add_url_rule("/health", view_func=EntryTranslatorApplication.health_check, methods=["GET"])

    response = app.test_client().get("/health")

    assert response.status_code == 500
    assert response.get_json()["message"] == "Translator service is not configured."


def test_build_server(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyServer:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            self.served = False

        def serve_forever(self) -> None:
            self.served = True

    monkeypatch.setattr(entry_translator_v2, "WSGIServer", DummyServer)

    app = entry_translator_v2.Flask("test")
    server = entry_translator_v2.build_server(app, "0.0.0.0", 8000)
    server.serve_forever()


def test_blocking_service_work_uses_gevent_threadpool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: Dict[str, Any] = {}

    class DummyThreadPool:
        def apply(self, operation: Callable[..., Any], args: tuple[Any, ...]) -> Any:
            calls["operation"] = operation
            calls["args"] = args
            return operation(*args)

    class DummyHub:
        threadpool = DummyThreadPool()

    monkeypatch.setattr(entry_translator_v2, "get_hub", lambda: DummyHub())

    def add(left: int, right: int) -> int:
        return left + right

    assert entry_translator_v2._run_blocking(add, 2, 3) == 5
    assert calls == {"operation": add, "args": (2, 3)}


def test_build_service(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyTranslation:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    class DummyPublisher:
        def __init__(self, queue_name: str) -> None:
            self.queue_name = queue_name

    class DummyReviewQueue:
        def __init__(self, queue_name: str) -> None:
            self.queue_name = queue_name

    class DummyService:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.args = args
            self.kwargs = kwargs

    monkeypatch.setattr(entry_translator_v2, "Translation", DummyTranslation)
    monkeypatch.setattr(entry_translator_v2, "WiktionaryRabbitMqPublisher", DummyPublisher)
    monkeypatch.setattr(
        entry_translator_v2,
        "RabbitMqPageCheckReviewQueue",
        DummyReviewQueue,
    )
    monkeypatch.setattr(entry_translator_v2, "EntryTranslatorService", DummyService)

    class DummyDefinitionSettingsStore:
        pass

    monkeypatch.setattr(
        entry_translator_v2,
        "DefinitionTranslationSettingsStore",
        DummyDefinitionSettingsStore,
    )

    service = entry_translator_v2.build_service(
        "queue",
        max_async_workers=3,
        max_pending_jobs=7,
        page_check_queue_name="page-check-review",
        page_check_review_queue_name="unchecked-pages",
        max_check_jobs_kept=350,
    )

    assert isinstance(service, DummyService)
    assert service.kwargs["max_async_workers"] == 3
    assert service.kwargs["max_pending_jobs"] == 7
    assert service.kwargs["max_check_jobs_kept"] == 350
    assert service.kwargs["publisher"].queue_name == "queue"
    assert service.kwargs["page_check_publisher"].queue_name == "page-check-review"
    assert service.kwargs["page_check_review_queue"].queue_name == "unchecked-pages"
    definition_store = service.kwargs["definition_translation_settings_store"]
    assert isinstance(definition_store, DummyDefinitionSettingsStore)
    assert service.kwargs["translation"].kwargs["basic_english_gate_enabled"]
    assert service.kwargs["translation"].kwargs[
        "nllb_roundtrip_validation_enabled"
    ]

    class CollidingQueueConfig:
        values = {
            "queue": "unchecked-pages",
        }

        def get(self, key: str, _section: str) -> str:
            return self.values[key]

    monkeypatch.setattr(entry_translator_v2, "BotjagwarConfig", CollidingQueueConfig)
    with pytest.raises(ValueError, match="review queue must differ"):
        entry_translator_v2.build_service(
            "automatic-edits",
            page_check_queue_name="page-check-edits",
            page_check_review_queue_name="unchecked-pages",
        )


def test_page_check_queue_uses_config_and_safe_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Queue routing is configurable and defaults to translated when absent."""
    class ConfiguredQueue:
        def get(self, _key: str, _section: str) -> str:
            return "translated"

    monkeypatch.setattr(
        entry_translator_v2,
        "BotjagwarConfig",
        ConfiguredQueue,
    )
    assert entry_translator_v2._page_check_queue_name() == "translated"
    assert entry_translator_v2._page_check_queue_name(" review ") == "review"

    class MissingQueueConfig:
        def get(self, _key: str, _section: str) -> str:
            raise KeyError("missing")

    monkeypatch.setattr(
        entry_translator_v2,
        "BotjagwarConfig",
        MissingQueueConfig,
    )

    assert entry_translator_v2._page_check_queue_name() == "translated"


def test_page_check_review_queue_uses_config_and_safe_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Manual review uses its own queue and never falls back to translated."""

    class ConfiguredQueue:
        def get(self, _key: str, _section: str) -> str:
            return "manual-review"

    monkeypatch.setattr(entry_translator_v2, "BotjagwarConfig", ConfiguredQueue)
    assert entry_translator_v2._page_check_review_queue_name() == "manual-review"
    assert entry_translator_v2._page_check_review_queue_name(" unchecked ") == (
        "unchecked"
    )

    class MissingQueueConfig:
        def get(self, _key: str, _section: str) -> str:
            raise KeyError("missing")

    monkeypatch.setattr(entry_translator_v2, "BotjagwarConfig", MissingQueueConfig)

    assert entry_translator_v2._page_check_review_queue_name() == "page-check-review"


def test_shutdown_handler_stops_server() -> None:
    """Test shutdown stops the server and asynchronous service."""
    server = SimpleNamespace(stopped=False)
    service = SimpleNamespace(stopped=False)

    def stop() -> None:
        server.stopped = True

    server.stop = stop
    service.shutdown = lambda **_kwargs: setattr(service, "stopped", True)

    entry_translator_v2._shutdown_handler(server, service)
    entry_translator_v2._shutdown_handler(None)

    assert server.stopped is True
    assert service.stopped is True


def test_main(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy_args = SimpleNamespace(
        PORT=9000,
        QUEUE="queue",
        PAGE_CHECK_QUEUE=None,
        PAGE_CHECK_REVIEW_QUEUE=None,
        LOG="log.txt",
        HOST="0.0.0.0",
        LOG_LEVEL="INFO",
        STALE_JOB_TIMEOUT_SECONDS=300.0,
        MAX_ASYNC_WORKERS=4,
        MAX_PENDING_JOBS=21,
        MAX_CHECK_JOBS_KEPT=100_000,
    )

    class DummyParser:
        def parse_args(self) -> Any:
            return dummy_args

    class DummyServer:
        def serve_forever(self) -> None:
            return None
        def stop(self) -> None:
            return None

    service = SimpleNamespace(shutdown=lambda **_kwargs: None)

    monkeypatch.setattr(entry_translator_v2, "parse_arguments", lambda: DummyParser())
    monkeypatch.setattr(entry_translator_v2, "setup_logging", lambda *_args: None)
    monkeypatch.setattr(
        entry_translator_v2,
        "build_service",
        lambda *_args, **_kwargs: service,
    )
    monkeypatch.setattr(
        entry_translator_v2.EntryTranslatorApplication,
        "create_app",
        lambda _service: "app",
    )
    monkeypatch.setattr(entry_translator_v2, "build_server", lambda *_args: DummyServer())

    with pytest.raises(SystemExit):
        entry_translator_v2.main()
