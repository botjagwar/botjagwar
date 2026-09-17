---
name: edit-entry-translator-stack
description: Use when editing or reviewing entry_translator_v2.py, api/services/entry_translator_service.py, api/translation_v2/core.py, their callers, publication safeguards, asynchronous jobs, route behavior, or the scoped 95% coverage gate.
---

# Edit Entry Translator Stack

Follow `AGENTS.md`; this skill takes precedence over `skills/edit-api/SKILL.md` for the files and behavior below.

## Scope

- `entry_translator_v2.py`: HTTP routes, request parsing, response and error handling.
- `api/services/entry_translator_service.py`: service behavior, jobs, backpressure, health, and dependency boundaries.
- `api/translation_v2/core.py`: page processing, outcomes, and publication orchestration.
- Direct callers and the nearest tests when their contract is affected.

Read only the affected owner file, its nearest tests, and the direct boundary being changed. Route registration, protocols/dataclasses, and tests are the authority for current endpoints and payloads; do not rely on copied inventories in prose.

## Invariants

- Keep v2 as the supported entry translator API. Do not restore removed legacy routes or silently add aliases.
- Preserve source revalidation, stale-page checks, locked publication paths, and other safeguards that prevent publishing obsolete or unintended content.
- Keep asynchronous execution bounded. Account for every job on success, rejection, failure, recovery, and shutdown without leaking capacity or active-job records.
- Keep expected service failures in `ServiceError` and preserve structured translation outcomes unless the requested API contract changes.
- Inject page access, publishers, counters/stores, executors, and external services in unit tests; never require live Wiktionary, Redis, RabbitMQ, PostgreSQL, or HTTP.
- Add focused route, service, or core tests at the layer where behavior changes.

## Validation

Run the nearest affected test while iterating, then run Ruff on every changed Python path and this exact scoped gate:

```bash
TEST=1 PYWIKIBOT_NO_NETWORK=1 python -m pytest -q \
  --cov-report=term-missing \
  --cov=api.services.entry_translator_service \
  --cov=api.translation_v2.core \
  --cov=entry_translator_v2 \
  --cov-fail-under=95 \
  test/unit_tests/test_entry_translator_service.py \
  test/unit_tests/test_entry_translator_v2.py \
  test/unit_tests/test_api_translation_v2/test_core.py
```

Report the measured coverage and any environment blocker. Run the full backend suite as required by `AGENTS.md` only when shared code or test infrastructure also changes; do not replace this gate with whole-`api` coverage.
