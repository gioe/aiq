# Project Conventions

<!-- Append-only file for learned heuristics, coupling patterns, and decomposition rules.
     Written by /retro after each session. Do not reorder or delete entries — newest last. -->

## Extract repeated ASGI/lifespan setup into conftest.py
_Source: session 521 — 2026-02-21_

When a 2+ line ASGI/lifespan setup pattern (e.g. `app = create_application(); app.router.lifespan_context = _test_lifespan`) appears in 3 or more test files, extract it into a named factory in `conftest.py` alongside the existing `create_test_app()`. This keeps the private Starlette attribute assignment in one place, so a future framework upgrade only requires a single fix.

## Resolve detect-secrets stash conflict before committing reformatted files
_Source: session 523 — 2026-02-21_

When committing a large batch of reformatted Python files, `detect-secrets` updates `.secrets.baseline` line numbers during the pre-commit hook, which conflicts with the pre-commit stash (causing "Rolling back fixes"). Fix: before committing, run `~/.cache/pre-commit/repo*/py_env-python3.13/bin/detect-secrets scan --baseline .secrets.baseline` then `git add .secrets.baseline`. With the baseline staged and off the unstaged list, the stash pop succeeds and the hook returns exit 0.

## iOS ViewModels must use @Published + publisher subscriptions for manager-derived state
_Source: session 525 — 2026-02-21_

When a ViewModel exposes state sourced from a service/manager (e.g. `isBiometricAvailable`, `biometricType`), use `@Published var` properties driven by `.assign(to: &$prop)` subscriptions in `init`, not computed properties. Computed properties are evaluated only at render time — if the underlying manager updates (e.g. user disables Face ID in system Settings while the app is backgrounded), the View will never re-render. The pattern mirrors the existing `isAuthenticatedPublisher` subscription in `SettingsViewModel`.

## Pre-commit tool versions must match requirements.txt tool versions
_Source: session 526 — 2026-02-21_

When a tool (e.g. `black`) is pinned in `requirements.txt` (e.g. `black==24.3.0`), the corresponding pre-commit hook `rev:` in `.pre-commit-config.yaml` must use the same version. Mismatch causes a silent "pre-commit passes, CI fails" trap: the hook reformats files one way, CI reformats them a different way. Each service (backend, question-service) may have its own `requirements.txt` pin, so each may need its own pre-commit entry at the matching version.
