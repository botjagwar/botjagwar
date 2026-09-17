---
name: edit-installation-deployment
description: Use when editing or reviewing install.sh, release and rollback tooling, deployment configuration, service templates, Supervisor control, remote provisioning, cron integration, or Atlas deployment scripts.
---

# Edit Installation and Deployment

Follow `AGENTS.md`; installation and deployment changes require the additional safety rules here.

## Read Set

Read the changed installer, helper, or template and its nearest test. Follow the values into the renderer or release manager only when that boundary changes. The scripts and templates are authoritative; do not infer current deployment state from checked-in rendered examples or copied inventories.

## Invariants

- Never test by installing into production paths. Use `test.sh`, which exports `TEST=1` and creates a temporary install tree.
- Preserve atomic activation, rollback, cleanup traps, protected configuration, persistent state, and cron restoration on every failure path.
- Treat production path, privilege, SSH, TLS, authentication, and Supervisor allow/deny changes as security-sensitive.
- Keep service-instance counts and network policy in `scripts/deployment_config.py`; keep rendering in `scripts/render_service_configs.py` and release lifecycle logic in the existing installer/release manager.
- Never commit live credentials, tokens, generated passwords, or operator configuration. Update sanitized examples for new settings.
- Update `readme.md` when an operator command, required setting, path, migration, or rollback procedure changes.

## Validation

Run focused unit tests and Ruff for changed Python helpers. Compile changed deployment Python when no focused import test covers it:

```bash
python -m compileall -q scripts supervisor_control_service.py configure_atlas_supervisor.py
```

Exercise installation, reinstall, and candidate rejection without running unrelated application suites:

```bash
NORUN=1 bash test.sh
```

Run the focused release-manager and installer-contract tests when rollback behavior changes. Run `bash test.sh` for cross-stack changes or release-candidate validation. It requires `sudo` for cleanup of its temporary tree; report an unavailable privilege rather than redirecting the test to production paths.
