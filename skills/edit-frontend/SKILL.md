---
name: edit-frontend
description: Use when editing or reviewing the Atlas React/TypeScript/Vite frontend under frontend/, including components, API calls, schema, runtime configuration, bilingual copy, and frontend tests.
---

# Edit Frontend

Follow `AGENTS.md`; this file adds only Atlas-specific boundaries.

## Read Set

Read the affected component or module and its co-located test. Follow only the imported API, type, schema, or configuration symbols needed by the change. Current routes, request shapes, and configuration fields come from `frontend/src` and tests, not copied lists.

## Invariants

- Keep TypeScript strict and reuse the existing component, state, API, and styling patterns.
- New or changed user-facing copy must use `useI18n` and complete `t(malagasy, english)` phrases.
- Direct database, dictionary, and translator writes use `auditedMutation` in `frontend/src/api.ts`.
- Supervisor and maintenance writes retain gateway-owned auditing; do not wrap them in a second browser-side audit record.
- Mutating failover must not duplicate writes. Preserve the existing single-target behavior unless the service contract explicitly changes.
- Treat `frontend/src/config.ts`, `frontend/public/config.json`, `frontend/install.sh`, `frontend/configure-atlas.sh`, and their tests as one runtime-configuration contract.
- Treat `definition_linking_contract.json` and its backend/frontend contract tests as the authority for shared definition linking.
- Co-locate component and utility tests, mock `fetch`, and do not call live services.
- Update `package-lock.json` whenever dependency metadata changes.

## Validation

Run a focused Vitest target while iterating when practical, then run all three required checks from the repository root:

```bash
npm run lint --prefix frontend
npm test --prefix frontend
npm run build --prefix frontend
```

Do not substitute a successful test run for the TypeScript build.
