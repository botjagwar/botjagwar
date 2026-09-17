---
name: edit-api
description: Use when editing or reviewing shared Python backend code under api/, including services, processors, parsers, importers, renderers, storage, and database access. Do not use for the dedicated entry translator stack when edit-entry-translator-stack applies.
---

# Edit API

Follow `AGENTS.md`; this file adds only backend-specific boundaries.

## Scope

Use this skill for shared Python application code and its tests. If the task centers on `entry_translator_v2.py`, `api/services/entry_translator_service.py`, or `api/translation_v2/core.py`, use `skills/edit-entry-translator-stack/SKILL.md` instead. Load both only for a genuinely cross-stack change.

## Read Set

Start with the affected module and its nearest tests. Read a direct caller, model, or configuration file only when the change can alter that interface. Derive current signatures and payloads from source and tests; do not build a repository-wide stack map first.

## Invariants

- Keep module imports free of network connections, service startup, and live `pywikibot.Site` creation.
- Use `BotjagwarConfig` rather than adding configuration paths or environment parsing ad hoc.
- Keep unit tests offline. Inject or mock Redis, RabbitMQ, PostgreSQL, pywikibot, and HTTP dependencies.
- Put translation orchestration in `api/translation_v2`, parsing in the existing processor/parser package, rendering in `api/page_renderer`, and persistence in the existing storage/database layer.
- Add sequential migrations under `data/migrations/` for schema changes. Never apply a production migration automatically.
- Preserve public result and error shapes unless the request explicitly changes them; establish those shapes from their declarations and tests.

## Validation

Run the nearest test first:

```bash
TEST=1 PYWIKIBOT_NO_NETWORK=1 python -m pytest -q <relevant-test-path>
```

Run Ruff on changed Python paths. Run the full backend suite only when a changed contract is used across modules or services, or when configuration, import behavior, or test infrastructure changes:

```bash
TEST=1 PYWIKIBOT_NO_NETWORK=1 python -m pytest -q test/unit_tests
```

Use the entry translator skill's scoped coverage command instead when that stack is affected. For broad backend or pull-request validation, `SKIP_FRONTEND=1 bash test.sh` also runs the CI-equivalent aggregate 85% coverage gate; it requires `sudo` for the temporary install tree.
