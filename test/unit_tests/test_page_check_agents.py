"""Tests for scheduled page-check issue and fix-agent automation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

import pytest
import requests

from scripts import page_check_agents as agents


class QueueApi:
    """Return queued values from the JSON API boundary and record requests."""

    def __init__(self, responses: Sequence[Any]) -> None:
        """Initialize the API with ordered responses or exceptions."""
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        payload: Mapping[str, Any] | None = None,
        expected_statuses: Sequence[int] = (200,),
    ) -> Any:
        """Record a request and return the next configured response."""
        self.calls.append(
            {
                "method": method,
                "path": path,
                "params": params,
                "payload": payload,
                "expected_statuses": expected_statuses,
            }
        )
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


class FakeResponse:
    """Minimal requests response test double."""

    def __init__(
        self,
        status_code: int,
        payload: Any = None,
        *,
        has_content: bool = True,
        invalid_json: bool = False,
    ) -> None:
        """Initialize a response with controlled JSON behavior."""
        self.status_code = status_code
        self._payload = payload
        self.content = b"json" if has_content else b""
        self._invalid_json = invalid_json

    def json(self) -> Any:
        """Return configured JSON or raise the requests decoder error."""
        if self._invalid_json:
            raise requests.exceptions.JSONDecodeError("invalid", "x", 0)
        return self._payload


class FakeSession:
    """Minimal requests session that records calls and returns queued responses."""

    def __init__(self, responses: Sequence[Any]) -> None:
        """Initialize a session with responses or request exceptions."""
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        """Record a request and return its queued response."""
        self.calls.append({"method": method, "url": url, **kwargs})
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


class FakePageCheckSource:
    """In-memory page-check source used by triage tests."""

    def __init__(
        self,
        summaries: Sequence[dict[str, Any]],
        jobs: Mapping[str, dict[str, Any]],
    ) -> None:
        """Initialize summaries and full jobs keyed by job ID."""
        self.summaries = list(summaries)
        self.jobs = dict(jobs)
        self.list_calls: list[tuple[str, int]] = []
        self.get_calls: list[tuple[str, str]] = []

    def list_jobs(self, language: str, limit: int) -> list[dict[str, Any]]:
        """Return configured summaries."""
        self.list_calls.append((language, limit))
        return self.summaries

    def get_job(self, language: str, job_id: str) -> dict[str, Any]:
        """Return a configured full job."""
        self.get_calls.append((language, job_id))
        return self.jobs[job_id]


class FakeIssueRepository:
    """In-memory issue repository used by triage and dispatch tests."""

    def __init__(
        self,
        *,
        existing: set[str] | None = None,
        queued: Sequence[dict[str, Any]] = (),
    ) -> None:
        """Initialize existing fingerprints and queued issues."""
        self.existing = existing or set()
        self.queued = list(queued)
        self.ensured: list[Mapping[str, tuple[str, str]]] = []
        self.created: list[tuple[str, str, tuple[str, ...]]] = []
        self.assignments: list[tuple[Any, ...]] = []
        self.added_labels: list[tuple[int, tuple[str, ...]]] = []
        self.removed_labels: list[tuple[int, str]] = []

    def existing_page_check_job_ids(self) -> set[str]:
        """Return configured existing job fingerprints."""
        return set(self.existing)

    def ensure_labels(self, definitions: Mapping[str, tuple[str, str]]) -> None:
        """Record label definitions."""
        self.ensured.append(definitions)

    def create_issue(self, title: str, body: str, labels: Sequence[str]) -> dict[str, Any]:
        """Record an issue and return a GitHub-shaped response."""
        self.created.append((title, body, tuple(labels)))
        number = len(self.created)
        return {
            "number": number,
            "html_url": f"https://github.com/example/repository/issues/{number}",
        }

    def queued_issues(self) -> list[dict[str, Any]]:
        """Return configured queued issues."""
        return self.queued

    def assign_copilot(
        self,
        issue_number: int,
        base_branch: str,
        custom_agent: str,
        custom_instructions: str,
        model: str | None = None,
    ) -> None:
        """Record one Copilot assignment."""
        self.assignments.append(
            (issue_number, base_branch, custom_agent, custom_instructions, model)
        )

    def add_labels(self, issue_number: int, labels: Sequence[str]) -> None:
        """Record labels added to an issue."""
        self.added_labels.append((issue_number, tuple(labels)))

    def remove_label(self, issue_number: int, label: str) -> None:
        """Record a removed issue label."""
        self.removed_labels.append((issue_number, label))


def job_summary(job_id: str, outcome: str, language: str = "mg") -> dict[str, Any]:
    """Build a page-check summary with one selected outcome."""
    counts = {"good": 0, "fixed": 0, "unverifiable": 0, "error": 0}
    status = outcome
    if outcome in counts:
        status = "done"
        counts[outcome] = 1
    return {
        "job_id": job_id,
        "language": language,
        "titles": [job_id],
        "status": status,
        "result_counts": counts,
    }


def full_job(
    job_id: str,
    outcome: str,
    *,
    title: str | None = None,
    language: str = "mg",
) -> dict[str, Any]:
    """Build one full completed page-check job."""
    word = title or job_id
    return {
        "job_id": job_id,
        "language": language,
        "titles": [word],
        "status": "done",
        "created_at": 1_700_000_000,
        "last_updated_at": 1_700_000_010,
        "attempts": 0,
        "stage": "completed",
        "message": "Page check completed.",
        "error": None,
        "results": [
            {
                "word": word,
                "status": outcome,
                "message": "Result message",
                "source_language": "en",
                "source_title": word,
                "issues": [{"type": "definition", "description": "Mismatch"}],
                "mg_entry": {"definitions": ["old"]},
                "fixed_entry": {"definitions": ["new"]} if outcome == "fixed" else None,
            }
        ],
    }


@pytest.mark.parametrize(
    ("job", "expected"),
    [
        ({"status": "pending"}, "pending"),
        ({"status": "running"}, "running"),
        ({"status": "error"}, "error"),
        (job_summary("good", "good"), "good"),
        (job_summary("fixed", "fixed"), "fixed"),
        (job_summary("unverifiable", "unverifiable"), "unverifiable"),
        (job_summary("error", "error"), "error"),
        ({"status": "done", "results": [{"status": "fixed"}]}, "fixed"),
        ({"status": "done", "results": [{"status": "unknown"}]}, "error"),
        (
            {"status": "done", "results": [{"status": "good"}, {"status": "unknown"}]},
            "error",
        ),
        ({"status": "done", "results": [{"status": ["bad"]}]}, "error"),
        ({"status": "done", "result_counts": {}}, "error"),
        ({"status": "done", "result_counts": {"good": -1}}, "error"),
        ({"status": "done", "result_counts": {"good": True}}, "error"),
        (
            {"status": "done", "result_counts": {"fixed": 1, "good": -1}},
            "error",
        ),
        (
            {"status": "done", "result_counts": {"good": 1, "unknown": 1}},
            "error",
        ),
    ],
)
def test_classify_job_uses_the_most_severe_valid_outcome(
    job: Mapping[str, Any], expected: str
) -> None:
    """Lifecycle failures and result severity map to stable outcomes."""
    assert agents.classify_job(job) == expected


def test_classify_job_prioritizes_errors_in_mixed_results() -> None:
    """A partially successful job is still surfaced when one result failed."""
    job = job_summary("mixed", "good")
    job["result_counts"]["fixed"] = 1
    job["result_counts"]["error"] = 1

    assert agents.classify_job(job) == "error"


def test_parse_issue_outcomes_normalizes_supported_values() -> None:
    """Outcome configuration accepts whitespace and case differences."""
    assert agents.parse_issue_outcomes(" FIXED, error ") == {"fixed", "error"}


@pytest.mark.parametrize("value", ["", "good", "fixed,unknown"])
def test_parse_issue_outcomes_rejects_unsupported_values(value: str) -> None:
    """Good jobs and unknown statuses cannot become maintenance issues."""
    with pytest.raises(ValueError, match="accepts"):
        agents.parse_issue_outcomes(value)


def test_build_issue_sanitizes_untrusted_content_and_adds_links() -> None:
    """Page data cannot escape its evidence block or mention a maintainer."""
    job = full_job("safe-id", "fixed", title="bad\n@maintainer [`page`]")
    job["results"][0]["message"] = "</pre>@maintainer"

    draft = agents.build_issue(job, "fixed", queue_fix=True)

    assert "@" not in draft.title
    assert "[page-check:fixed]" in draft.title
    assert "https://mg.wiktionary.org/wiki/bad%0A%40maintainer_%5B%60page%60%5D" in draft.body
    assert "https://en.wiktionary.org/wiki/bad%0A%40maintainer_%5B%60page%60%5D" in draft.body
    assert "&lt;/pre&gt;&#64;maintainer" in draft.body
    assert "<!-- botjagwar-page-check-job:safe-id -->" in draft.body
    assert draft.labels == ("page-check", "page-check:fixed", "agent:queued")


def test_build_issue_bounds_large_evidence_and_handles_unknown_time() -> None:
    """Oversized checker output stays below GitHub's issue body limit."""
    job = full_job("large", "error")
    job["created_at"] = "invalid"
    job["results"][0]["message"] = "x" * 100_000
    job["results"][0]["source_title"] = "界" * 100_000

    draft = agents.build_issue(job, "error", queue_fix=False)

    assert "Created: `unknown`" in draft.body
    assert "evidence truncated" in draft.body
    assert len(draft.body) <= agents.MAX_ISSUE_BODY_LENGTH
    assert draft.labels == ("page-check", "page-check:error")


def test_build_issue_falls_back_to_result_word_and_validates_job_id() -> None:
    """Legacy full jobs can use result words but never unsafe marker IDs."""
    job = full_job("fallback", "unverifiable", title="word")
    job["titles"] = None
    draft = agents.build_issue(job, "unverifiable", queue_fix=False)
    assert "word" in draft.title

    job["job_id"] = "bad/id"
    with pytest.raises(agents.ApiError, match="job_id"):
        agents.build_issue(job, "unverifiable", queue_fix=False)


def test_triage_creates_only_new_candidates_within_the_run_limit() -> None:
    """Triage counts all jobs, skips duplicates, and bounds issue creation."""
    summaries = [
        job_summary("good", "good"),
        job_summary("duplicate", "fixed"),
        job_summary("new", "unverifiable"),
        job_summary("later", "error"),
        job_summary("pending", "pending"),
    ]
    source = FakePageCheckSource(summaries, {"new": full_job("new", "unverifiable")})
    issues = FakeIssueRepository(existing={"duplicate"})

    report = agents.triage_page_checks(
        source,
        issues,
        agents.TriageConfig(max_issues=1, queue_fixes=True),
    )

    assert report.outcomes == {
        "good": 1,
        "fixed": 1,
        "unverifiable": 1,
        "error": 1,
        "pending": 1,
    }
    assert report.candidates == 3
    assert report.duplicates == 1
    assert report.deferred == 1
    assert len(report.created_urls) == 1
    assert source.list_calls == [("mg", 100)]
    assert source.get_calls == [("mg", "new")]
    assert issues.created[0][2] == (
        "page-check",
        "page-check:unverifiable",
        "agent:queued",
    )
    assert set(issues.ensured[0]) == {
        "page-check",
        "page-check:fixed",
        "page-check:unverifiable",
        "page-check:error",
        "agent:queued",
    }


def test_triage_dry_run_fetches_evidence_without_writing_github() -> None:
    """Dry-run mode reports prospective work but creates no labels or issues."""
    source = FakePageCheckSource(
        [job_summary("new", "fixed")],
        {"new": full_job("new", "fixed")},
    )
    issues = FakeIssueRepository()

    report = agents.triage_page_checks(
        source,
        issues,
        agents.TriageConfig(dry_run=True),
    )

    assert report.would_create == 1
    assert not issues.ensured
    assert not issues.created


def test_triage_creates_manual_approval_label_without_queueing_issue() -> None:
    """The safe default prepares the approval label but does not apply it."""
    source = FakePageCheckSource(
        [job_summary("new", "error")],
        {"new": full_job("new", "error")},
    )
    issues = FakeIssueRepository()

    agents.triage_page_checks(source, issues, agents.TriageConfig())

    assert agents.QUEUE_LABEL in issues.ensured[0]
    assert agents.QUEUE_LABEL not in issues.created[0][2]


def test_triage_rechecks_autonomy_before_queueing_each_issue() -> None:
    """Disabling Atlas during triage stops later issues from being auto-queued."""
    source = FakePageCheckSource(
        [job_summary("first", "error"), job_summary("second", "error")],
        {
            "first": full_job("first", "error"),
            "second": full_job("second", "error"),
        },
    )
    issues = FakeIssueRepository()
    settings = iter((True, False))

    agents.triage_page_checks(
        source,
        issues,
        agents.TriageConfig(queue_fixes=True),
        lambda: next(settings),
    )

    assert agents.QUEUE_LABEL in issues.created[0][2]
    assert agents.QUEUE_LABEL not in issues.created[1][2]


def test_triage_skips_a_job_that_resolved_before_full_fetch() -> None:
    """A summary/full-job race never opens a stale issue."""
    source = FakePageCheckSource(
        [job_summary("changed", "error")],
        {"changed": full_job("changed", "good")},
    )
    issues = FakeIssueRepository()

    report = agents.triage_page_checks(source, issues, agents.TriageConfig())

    assert report.resolved_before_issue == 1
    assert not issues.created


def test_triage_uses_configured_language_for_an_invalid_summary_language() -> None:
    """An invalid summary language cannot alter the API path used for details."""
    summary = job_summary("new", "error", language="bad/path")
    source = FakePageCheckSource([summary], {"new": full_job("new", "error")})

    agents.triage_page_checks(source, FakeIssueRepository(), agents.TriageConfig())

    assert source.get_calls == [("mg", "new")]


def test_triage_rejects_mismatched_summary_and_full_job_ids() -> None:
    """A malformed detail response cannot defeat issue deduplication."""
    source = FakePageCheckSource(
        [job_summary("summary", "error")],
        {"summary": full_job("different", "error")},
    )

    with pytest.raises(agents.ApiError, match="does not match"):
        agents.triage_page_checks(source, FakeIssueRepository(), agents.TriageConfig())


def test_dispatch_assigns_a_bounded_batch_and_cleans_up_labels() -> None:
    """Already assigned work is normalized and only one new task is started."""
    queued = [
        {
            "number": 1,
            "html_url": "https://github.com/example/repository/issues/1",
            "body": "<!-- botjagwar-page-check-job:first -->",
            "assignees": [{"login": "copilot-swe-agent"}],
        },
        {
            "number": 2,
            "html_url": "https://github.com/example/repository/issues/2",
            "body": "<!-- botjagwar-page-check-job:second -->",
            "assignees": [],
        },
        {
            "number": 3,
            "html_url": "https://github.com/example/repository/issues/3",
            "body": "<!-- botjagwar-page-check-job:third -->",
            "assignees": [],
        },
    ]
    issues = FakeIssueRepository(queued=queued)

    report = agents.dispatch_page_check_fixes(
        issues,
        agents.DispatchConfig(
            base_branch="dev",
            custom_agent="alternate-fixer",
            max_assignments=1,
            model="gpt-test",
        ),
    )

    assert report.queued == 3
    assert report.already_assigned == 1
    assert report.deferred == 1
    assert report.assigned_urls == ["https://github.com/example/repository/issues/2"]
    assert issues.assignments[0][0:3] == (2, "dev", "alternate-fixer")
    assert "issue #2" in issues.assignments[0][3]
    assert "alternate-fixer agent" in issues.assignments[0][3]
    assert issues.assignments[0][4] == "gpt-test"
    assert issues.added_labels == [
        (1, ("agent:assigned",)),
        (2, ("agent:assigned",)),
    ]
    assert issues.removed_labels == [
        (1, "agent:queued"),
        (2, "agent:queued"),
    ]


def test_dispatch_rejects_a_queued_issue_without_a_number() -> None:
    """Malformed GitHub issue data is skipped without blocking later work."""
    issues = FakeIssueRepository(
        queued=[
            {"assignees": []},
            {
                "number": 2,
                "body": "<!-- botjagwar-page-check-job:valid -->",
                "assignees": [],
            },
        ]
    )

    report = agents.dispatch_page_check_fixes(
        issues,
        agents.DispatchConfig(base_branch="dev"),
    )

    assert report.invalid == 1
    assert issues.assignments[0][0] == 2


def test_dispatch_rejects_an_issue_without_a_generated_fingerprint() -> None:
    """Controlled labels alone quarantine rather than dispatch a fabricated issue."""
    issues = FakeIssueRepository(queued=[{"number": 1, "body": "manual", "assignees": []}])

    report = agents.dispatch_page_check_fixes(
        issues,
        agents.DispatchConfig(base_branch="dev"),
    )

    assert report.invalid == 1
    assert issues.added_labels == [(1, (agents.INVALID_LABEL,))]
    assert issues.removed_labels == [(1, agents.QUEUE_LABEL)]
    assert not issues.assignments


def test_dispatch_rechecks_autonomy_before_each_assignment() -> None:
    """Disabling Atlas during a batch prevents every later assignment."""
    issues = FakeIssueRepository(
        queued=[
            {
                "number": 1,
                "body": "<!-- botjagwar-page-check-job:first -->",
                "assignees": [],
            },
            {
                "number": 2,
                "body": "<!-- botjagwar-page-check-job:second -->",
                "assignees": [],
            },
        ]
    )
    settings = iter((True, False))

    report = agents.dispatch_page_check_fixes(
        issues,
        agents.DispatchConfig(base_branch="dev"),
        lambda: next(settings),
    )

    assert [assignment[0] for assignment in issues.assignments] == [1]
    assert report.skipped_reason == "disabled by the server-managed Atlas setting"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"language": "MG"},
        {"job_limit": 0},
        {"max_issues": 101},
        {"issue_outcomes": frozenset({"good"})},
    ],
)
def test_triage_config_rejects_invalid_values(kwargs: Mapping[str, Any]) -> None:
    """Triage bounds API reads and accepted outcomes."""
    with pytest.raises(ValueError):
        agents.TriageConfig(**kwargs)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"base_branch": ""},
        {"base_branch": "bad branch"},
        {"base_branch": "dev", "custom_agent": ""},
        {"base_branch": "dev", "max_assignments": 21},
    ],
)
def test_dispatch_config_rejects_invalid_values(kwargs: Mapping[str, Any]) -> None:
    """Dispatch requires a bounded batch and valid agent target."""
    with pytest.raises(ValueError):
        agents.DispatchConfig(**kwargs)


def test_json_api_sends_bounded_authenticated_requests() -> None:
    """The HTTP adapter sets authentication, API version, and timeout headers."""
    session = FakeSession([FakeResponse(200, {"ok": True})])
    api = agents.JsonApi("https://api.example.test/root/", session, token="secret", timeout_seconds=4)

    assert api.request("POST", "/items", payload={"value": 1}, expected_statuses=(200,)) == {"ok": True}
    call = session.calls[0]
    assert call["url"] == "https://api.example.test/root/items"
    assert call["headers"]["Authorization"] == "Bearer secret"
    assert call["headers"]["X-GitHub-Api-Version"] == agents.GITHUB_API_VERSION
    assert call["timeout"] == 4


@pytest.mark.parametrize(
    "url",
    [
        "relative",
        "ftp://example.test",
        "https://user:password@example.test",
        "https://example.test?query=yes",
        "https://example.test#fragment",
    ],
)
def test_json_api_rejects_unsafe_base_urls(url: str) -> None:
    """Credentials and request-specific components never enter a base URL."""
    with pytest.raises(ValueError, match="API URLs"):
        agents.JsonApi(url, FakeSession([]))


def test_json_api_requires_https_when_sending_a_token() -> None:
    """Bearer credentials are never transmitted over plaintext HTTP."""
    with pytest.raises(ValueError, match="must use HTTPS"):
        agents.JsonApi("http://api.example.test", FakeSession([]), token="secret")

    agents.JsonApi("http://api.example.test", FakeSession([]))


def test_json_api_handles_empty_invalid_failed_and_unreachable_responses() -> None:
    """The HTTP adapter translates all transport and decoding failure modes."""
    api = agents.JsonApi(
        "https://api.example.test",
        FakeSession(
            [
                FakeResponse(204, has_content=False),
                FakeResponse(200, invalid_json=True),
                FakeResponse(422, {"message": " invalid   request "}),
                requests.ConnectionError("offline"),
            ]
        ),
    )

    assert api.request("DELETE", "/empty", expected_statuses=(204,)) is None
    with pytest.raises(agents.ApiError, match="invalid JSON"):
        api.request("GET", "/invalid")
    with pytest.raises(agents.ApiError, match="HTTP 422: invalid request") as error:
        api.request("POST", "/failed")
    assert error.value.status_code == 422
    with pytest.raises(agents.ApiError, match="Unable to reach"):
        api.request("GET", "/offline")


def test_json_api_omits_non_json_error_details() -> None:
    """A malformed error body does not obscure the HTTP status."""
    api = agents.JsonApi(
        "https://api.example.test",
        FakeSession([FakeResponse(500, invalid_json=True)]),
    )

    with pytest.raises(agents.ApiError, match=r"HTTP 500\."):
        api.request("GET", "/failed")


def test_page_check_api_validates_lists_and_builds_encoded_paths() -> None:
    """Page-check transport data is validated before triage consumes it."""
    summary = job_summary("job-id", "good")
    full = full_job("job-id", "good")
    api = QueueApi([{"jobs": [summary]}, full])
    client = agents.PageCheckApi(api)

    assert client.list_jobs("mg", 10) == [summary]
    assert client.get_job("mg", "job-id") == full
    assert api.calls[0]["path"] == "/wiktionary-pages/mg/check-jobs"
    assert api.calls[0]["params"] == {"limit": 10}
    assert api.calls[1]["path"] == "/wiktionary-pages/mg/check-jobs/job-id"


@pytest.mark.parametrize(
    "response",
    [{}, {"jobs": "bad"}, {"jobs": ["bad"]}],
)
def test_page_check_api_rejects_invalid_job_lists(response: Any) -> None:
    """Malformed list payloads fail with a stable API error."""
    with pytest.raises(agents.ApiError, match="job list"):
        agents.PageCheckApi(QueueApi([response])).list_jobs("mg", 10)


def test_page_check_api_rejects_an_invalid_full_job() -> None:
    """Full job responses must be JSON objects."""
    with pytest.raises(agents.ApiError, match="invalid shape"):
        agents.PageCheckApi(QueueApi([["bad"]])).get_job("mg", "job")


def test_page_check_api_reads_the_autonomous_agent_setting_strictly() -> None:
    """Automatic assignment uses only an explicit server boolean."""
    api = QueueApi([{"autonomous_agent_enabled": True}])

    assert agents.PageCheckApi(api).get_autonomous_agent_enabled() is True
    assert api.calls[0]["path"] == "/page-checker/settings"


@pytest.mark.parametrize(
    "response",
    [{}, [], {"autonomous_agent_enabled": 1}, {"autonomous_agent_enabled": "true"}],
)
def test_page_check_api_rejects_an_invalid_autonomous_agent_setting(
    response: Any,
) -> None:
    """Missing and coerced setting values fail closed."""
    with pytest.raises(agents.ApiError, match="automation flag"):
        agents.PageCheckApi(QueueApi([response])).get_autonomous_agent_enabled()


def test_github_api_lists_fingerprints_and_excludes_pull_requests() -> None:
    """Closed issue fingerprints deduplicate jobs while PR bodies are ignored."""
    api = QueueApi(
        [
            [
                {"body": "<!-- botjagwar-page-check-job:first -->"},
                {"body": "none"},
                {
                    "body": "<!-- botjagwar-page-check-job:pr-job -->",
                    "pull_request": {},
                },
            ]
        ]
    )
    github = agents.GitHubApi(api, "owner/repository")

    assert github.existing_page_check_job_ids() == {"first"}
    assert api.calls[0]["params"]["state"] == "all"
    assert api.calls[0]["params"]["labels"] == "page-check"


def test_github_api_paginates_full_pages() -> None:
    """A full GitHub page is followed until a short page terminates pagination."""
    first_page = [{"body": None} for _ in range(100)]
    second_page = [{"body": "<!-- botjagwar-page-check-job:last -->"}]
    api = QueueApi([first_page, second_page])

    assert agents.GitHubApi(api, "owner/repository").existing_page_check_job_ids() == {"last"}
    assert api.calls[1]["params"]["page"] == 2


def test_github_api_creates_missing_labels_and_ignores_label_races() -> None:
    """Known labels are retained and a concurrent create does not fail the run."""
    api = QueueApi(
        [
            [{"name": "existing"}],
            {"name": "new"},
            agents.ApiError("already exists", status_code=422),
        ]
    )
    github = agents.GitHubApi(api, "owner/repository")

    github.ensure_labels(
        {
            "existing": ("ffffff", "Existing"),
            "new": ("000000", "New"),
            "raced": ("111111", "Raced"),
        }
    )

    assert [call["payload"]["name"] for call in api.calls[1:]] == ["new", "raced"]


def test_github_api_propagates_non_conflict_label_errors() -> None:
    """Only the expected concurrent-label conflict is ignored."""
    api = QueueApi([[], agents.ApiError("forbidden", status_code=403)])

    with pytest.raises(agents.ApiError, match="forbidden"):
        agents.GitHubApi(api, "owner/repository").ensure_labels(
            {"new": ("000000", "New")}
        )


def test_github_api_creates_and_validates_issues() -> None:
    """Issue creation sends the exact title, body, and labels contract."""
    api = QueueApi([{"number": 7, "html_url": "https://github.com/owner/repository/issues/7"}])
    github = agents.GitHubApi(api, "owner/repository")

    issue = github.create_issue("Title", "Body", ("page-check",))

    assert issue["number"] == 7
    assert api.calls[0]["payload"] == {
        "title": "Title",
        "body": "Body",
        "labels": ["page-check"],
    }
    with pytest.raises(agents.ApiError, match="invalid created issue"):
        agents.GitHubApi(QueueApi([{}]), "owner/repository").create_issue(
            "Title", "Body", ()
        )


def test_github_api_lists_only_queued_issues() -> None:
    """The dispatcher requests open issues carrying both controlled labels."""
    api = QueueApi([[{"number": 1}, {"number": 2, "pull_request": {}}]])

    queued = agents.GitHubApi(api, "owner/repository").queued_issues()

    assert queued == [{"number": 1}]
    assert api.calls[0]["params"]["labels"] == "page-check,agent:queued"
    assert api.calls[0]["params"]["direction"] == "asc"


def test_github_api_assigns_the_custom_copilot_agent() -> None:
    """The REST assignment includes the custom agent, model, and base branch."""
    api = QueueApi(
        [
            {
                "number": 9,
                "assignees": [{"login": "copilot-swe-agent[bot]"}],
            }
        ]
    )
    github = agents.GitHubApi(api, "owner/repository")

    github.assign_copilot(9, "dev", "page-check-fixer", "Instructions", "gpt-test")

    assert api.calls[0]["payload"] == {
        "assignees": ["copilot-swe-agent[bot]"],
        "agent_assignment": {
            "target_repo": "owner/repository",
            "base_branch": "dev",
            "custom_instructions": "Instructions",
            "custom_agent": "page-check-fixer",
            "model": "gpt-test",
        },
    }


def test_github_api_rejects_a_silently_ignored_copilot_assignment() -> None:
    """A token or policy problem cannot be reported as a successful dispatch."""
    with pytest.raises(agents.ApiError, match="did not assign Copilot"):
        agents.GitHubApi(QueueApi([{"assignees": []}]), "owner/repository").assign_copilot(
            9, "dev", "page-check-fixer", "Instructions"
        )


def test_github_api_adds_and_removes_labels() -> None:
    """Dispatch label updates use additive and targeted REST endpoints."""
    api = QueueApi([[], None])
    github = agents.GitHubApi(api, "owner/repository")

    github.add_labels(3, ("agent:assigned",))
    github.remove_label(3, "agent:queued")

    assert api.calls[0]["payload"] == {"labels": ["agent:assigned"]}
    assert api.calls[1]["path"].endswith("/labels/agent%3Aqueued")


def test_github_api_ignores_removing_an_absent_label() -> None:
    """An already removed queue label leaves assignment successful."""
    github = agents.GitHubApi(
        QueueApi([agents.ApiError("missing", status_code=404)]),
        "owner/repository",
    )
    github.remove_label(3, "agent:queued")


def test_github_api_rejects_invalid_repository_and_list_shapes() -> None:
    """Repository paths and paginated data are validated before use."""
    with pytest.raises(ValueError, match="owner/name"):
        agents.GitHubApi(QueueApi([]), "invalid")
    with pytest.raises(agents.ApiError, match="invalid list"):
        agents.GitHubApi(QueueApi([{}]), "owner/repository").queued_issues()


def test_rendered_reports_include_counts_and_created_links() -> None:
    """Workflow summaries expose classifications, deduplication, and dispatch."""
    triage = agents.TriageReport(
        outcomes=agents.Counter({"good": 2, "fixed": 1}),
        candidates=1,
        duplicates=1,
        created_urls=["https://github.com/owner/repository/issues/1"],
        would_create=2,
        deferred=3,
        resolved_before_issue=4,
    )
    dispatch = agents.DispatchReport(
        queued=2,
        assigned_urls=["https://github.com/owner/repository/issues/1"],
        already_assigned=1,
        invalid=1,
        deferred=1,
        skipped_reason="disabled in Atlas",
    )

    assert "| `good` | 2 |" in agents.render_triage_report(triage)
    assert "Would create: 2" in agents.render_triage_report(triage)
    assert "Assigned: 1" in agents.render_dispatch_report(dispatch)
    assert "Rejected as malformed: 1" in agents.render_dispatch_report(dispatch)
    assert "Automatic dispatch skipped: disabled in Atlas" in agents.render_dispatch_report(
        dispatch
    )


def test_environment_integer_reader_accepts_defaults_and_rejects_bad_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Workflow integer overrides are parsed strictly."""
    monkeypatch.delenv("INTEGER", raising=False)
    assert agents._environment_int("INTEGER", 3) == 3

    monkeypatch.setenv("INTEGER", "4")
    assert agents._environment_int("INTEGER", 3) == 4

    monkeypatch.setenv("INTEGER", "four")
    with pytest.raises(ValueError, match="integer"):
        agents._environment_int("INTEGER", 3)


def test_run_triage_builds_environment_configuration(
    monkeypatch: pytest.MonkeyPatch,
    mocker: Any,
) -> None:
    """The triage CLI maps Actions settings into bounded domain configuration."""
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setenv("PAGE_CHECK_JOB_LIMIT", "20")
    monkeypatch.setenv("PAGE_CHECK_MAX_ISSUES", "4")
    autonomy = mocker.patch.object(
        agents.PageCheckApi,
        "get_autonomous_agent_enabled",
        return_value=False,
    )
    expected = agents.TriageReport()
    triage = mocker.patch("scripts.page_check_agents.triage_page_checks", return_value=expected)
    args = agents.build_parser().parse_args(
        [
            "triage",
            "--page-checker-url",
            "https://checker.example.test",
            "--github-repository",
            "owner/repository",
            "--issue-outcomes",
            "error",
        ]
    )

    assert agents._run_triage(args) is expected
    config = triage.call_args.args[2]
    assert config.job_limit == 20
    assert config.max_issues == 4
    assert config.issue_outcomes == {"error"}
    assert config.queue_fixes is False
    autonomy.assert_called_once_with()


def test_run_triage_queues_fixes_when_enabled_in_atlas(
    monkeypatch: pytest.MonkeyPatch,
    mocker: Any,
) -> None:
    """The server-managed Atlas setting replaces the Actions variable."""
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    mocker.patch.object(
        agents.PageCheckApi,
        "get_autonomous_agent_enabled",
        return_value=True,
    )
    triage = mocker.patch(
        "scripts.page_check_agents.triage_page_checks",
        return_value=agents.TriageReport(),
    )
    args = agents.build_parser().parse_args(
        [
            "triage",
            "--page-checker-url",
            "https://checker.example.test",
            "--github-repository",
            "owner/repository",
        ]
    )

    agents._run_triage(args)

    assert triage.call_args.args[2].queue_fixes is True


def test_run_dispatch_builds_environment_configuration(
    monkeypatch: pytest.MonkeyPatch,
    mocker: Any,
) -> None:
    """The dispatch CLI uses only the user token and configured batch."""
    monkeypatch.setenv("COPILOT_AGENT_TOKEN", "token")
    monkeypatch.setenv("PAGE_CHECK_FIX_BATCH", "2")
    expected = agents.DispatchReport()
    dispatch = mocker.patch(
        "scripts.page_check_agents.dispatch_page_check_fixes",
        return_value=expected,
    )
    args = agents.build_parser().parse_args(
        [
            "dispatch",
            "--github-repository",
            "owner/repository",
            "--base-branch",
            "dev",
        ]
    )

    assert agents._run_dispatch(args) is expected
    assert dispatch.call_args.args[1].max_assignments == 2


def test_automatic_dispatch_is_a_noop_when_disabled_in_atlas(
    monkeypatch: pytest.MonkeyPatch,
    mocker: Any,
) -> None:
    """A disabled server setting prevents assignment without requiring a token."""
    monkeypatch.delenv("COPILOT_AGENT_TOKEN", raising=False)
    mocker.patch.object(
        agents.PageCheckApi,
        "get_autonomous_agent_enabled",
        return_value=False,
    )
    dispatch = mocker.patch("scripts.page_check_agents.dispatch_page_check_fixes")
    args = agents.build_parser().parse_args(
        [
            "dispatch",
            "--page-checker-url",
            "https://checker.example.test",
            "--github-repository",
            "owner/repository",
            "--base-branch",
            "dev",
            "--require-autonomous-agent-enabled",
        ]
    )

    report = agents._run_dispatch(args)

    assert report.skipped_reason == "disabled by the server-managed Atlas setting"
    dispatch.assert_not_called()


def test_automatic_dispatch_proceeds_when_enabled_in_atlas(
    monkeypatch: pytest.MonkeyPatch,
    mocker: Any,
) -> None:
    """An enabled server setting permits the normal bounded assignment path."""
    monkeypatch.setenv("COPILOT_AGENT_TOKEN", "token")
    mocker.patch.object(
        agents.PageCheckApi,
        "get_autonomous_agent_enabled",
        return_value=True,
    )
    expected = agents.DispatchReport(queued=1)
    dispatch = mocker.patch(
        "scripts.page_check_agents.dispatch_page_check_fixes",
        return_value=expected,
    )
    args = agents.build_parser().parse_args(
        [
            "dispatch",
            "--page-checker-url",
            "https://checker.example.test",
            "--github-repository",
            "owner/repository",
            "--base-branch",
            "dev",
            "--require-autonomous-agent-enabled",
        ]
    )

    assert agents._run_dispatch(args) is expected
    dispatch.assert_called_once()


@pytest.mark.parametrize(
    ("command", "environment", "message"),
    [
        (["triage", "--github-repository", "owner/repository"], {"GITHUB_TOKEN": "token"}, "PAGE_CHECKER_URL"),
        (["triage", "--page-checker-url", "https://checker.test"], {"GITHUB_TOKEN": "token"}, "GITHUB_REPOSITORY"),
        (
            [
                "triage",
                "--page-checker-url",
                "https://checker.test",
                "--github-repository",
                "owner/repository",
            ],
            {},
            "GITHUB_TOKEN",
        ),
        (["dispatch", "--base-branch", "dev"], {"COPILOT_AGENT_TOKEN": "token"}, "GITHUB_REPOSITORY"),
        (["dispatch", "--github-repository", "owner/repository"], {"COPILOT_AGENT_TOKEN": "token"}, "BASE_BRANCH"),
        (
            [
                "dispatch",
                "--github-repository",
                "owner/repository",
                "--base-branch",
                "dev",
                "--require-autonomous-agent-enabled",
            ],
            {"COPILOT_AGENT_TOKEN": "token"},
            "PAGE_CHECKER_URL",
        ),
        (
            [
                "dispatch",
                "--github-repository",
                "owner/repository",
                "--base-branch",
                "dev",
            ],
            {},
            "COPILOT_AGENT_TOKEN",
        ),
    ],
)
def test_cli_commands_report_missing_configuration(
    command: list[str],
    environment: Mapping[str, str],
    message: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Missing endpoints, repositories, branches, and tokens fail clearly."""
    for name in (
        "GITHUB_TOKEN",
        "COPILOT_AGENT_TOKEN",
        "PAGE_CHECKER_URL",
        "GITHUB_REPOSITORY",
        "PAGE_CHECK_FIX_BASE_BRANCH",
    ):
        monkeypatch.delenv(name, raising=False)
    for name, value in environment.items():
        monkeypatch.setenv(name, value)

    assert agents.main(command) == 1
    assert message in capsys.readouterr().err


def test_main_renders_successful_triage_and_dispatch(
    mocker: Any,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The CLI prints Markdown summaries for both successful commands."""
    mocker.patch(
        "scripts.page_check_agents._run_triage",
        return_value=agents.TriageReport(outcomes=agents.Counter({"good": 1})),
    )
    assert agents.main(["triage"]) == 0
    assert "Page-check issue agent" in capsys.readouterr().out

    mocker.patch(
        "scripts.page_check_agents._run_dispatch",
        return_value=agents.DispatchReport(queued=1),
    )
    assert agents.main(["dispatch"]) == 0
    assert "Page-check fix agent" in capsys.readouterr().out


def test_workflows_use_the_server_setting_for_automatic_dispatch() -> None:
    """Actions no longer bypass Atlas through a repository auto-fix variable."""
    root = Path(__file__).resolve().parents[2]
    issue_workflow = (root / ".github/workflows/page-check-issue-agent.yml").read_text(
        encoding="utf-8"
    )
    fix_workflow = (root / ".github/workflows/page-check-fix-agent.yml").read_text(
        encoding="utf-8"
    )

    assert "PAGE_CHECK_AUTO_FIX" not in issue_workflow + fix_workflow
    assert "PAGE_CHECKER_URL" in fix_workflow
    assert "--require-autonomous-agent-enabled" in fix_workflow
    assert "vars.PAGE_CHECK_RUNNER" in fix_workflow


def test_issue_url_falls_back_when_github_url_is_untrusted() -> None:
    """Only canonical GitHub URLs are emitted into workflow summaries."""
    assert agents._issue_url({"number": 5, "html_url": "https://evil.test"}) == "issue #5"
    assert agents._issue_url({}) == "created issue"


def test_render_timestamp_handles_out_of_range_values() -> None:
    """Impossible timestamps cannot fail issue creation."""
    assert agents._render_timestamp(10**100) == "unknown"
