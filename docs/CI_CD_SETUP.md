# CI/CD Setup Guide

This document describes the CI/CD pipeline configuration for the AIQ project. All workflows live in `.github/workflows/` and trigger automatically on pull requests and pushes to `main`.

## Pipeline Overview

| Workflow | File | Trigger Paths | Runner |
|----------|------|---------------|--------|
| **Backend CI** | `backend-ci.yml` | `backend/**`, `libs/**` | ubuntu-latest |
| **Question Service CI** | `question-service-ci.yml` | `question-service/**` | ubuntu-latest |
| **iOS CI** | `ios-ci.yml` | `ios/**`, `backend/**`, `docs/api/**` | macos-15 |
| **Pre-commit Checks** | `pre-commit.yml` | All files | ubuntu-latest |
| **Close Jira on Merge** | `close-jira-on-merge.yml` | PR merge events | ubuntu-latest |
| **Claude Code** | `claude.yml` | `@claude` mentions in issues/PRs | ubuntu-latest |
| **Claude Code Review** | `claude-code-review.yml` | PR open/synchronize | ubuntu-latest |
| **Certificate Monitor** | `certificate-monitor.yml` | Weekly cron (Mon 9am UTC) | ubuntu-latest |
| **Model Availability** | `model-availability-check.yml` | Weekly cron (Mon 8am UTC) | ubuntu-latest |

## Backend CI

**File:** `.github/workflows/backend-ci.yml`

### Jobs

#### 1. `test`

Runs linting, type checking, database migrations, and tests against a PostgreSQL service container.

**Steps:**
1. Checkout code
2. Set up Python 3.13 (with pip cache)
3. Install dependencies from `backend/requirements.txt`
4. Run Black formatting check
5. Run Flake8 linting
6. Run MyPy type checking
7. Run Alembic database migrations
8. Run pytest

**Services:** PostgreSQL 14 (`postgres:14`) on port 5432

**Environment Variables:**
| Variable | Value |
|----------|-------|
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/iq_tracker_test` | <!-- pragma: allowlist secret -->
| `SECRET_KEY` | `test-secret-key` |
| `JWT_SECRET_KEY` | `test-jwt-secret-key` |
| `ADMIN_TOKEN` | `test-admin-token` |
| `SERVICE_API_KEY` | `test-service-key` |
| `PYTHONPATH` | `${{ github.workspace }}` |

#### 2. `export-openapi`

Exports the OpenAPI spec and auto-commits it on `main`. Only runs after `test` passes and only on pushes to `main`.

**Steps:**
1. Checkout code (full history)
2. Install dependencies
3. Export OpenAPI spec via `backend/scripts/export_openapi.py`
4. If `docs/api/openapi.json` changed, commit and push with retry logic

**Commit message:** `chore: Update OpenAPI spec [skip ci]`

## Question Service CI

**File:** `.github/workflows/question-service-ci.yml`

### Jobs

#### 1. `test`

Runs linting, type checking, and unit tests.

**Steps:**
1. Checkout code
2. Set up Python 3.13 (with pip cache)
3. Install dependencies from `question-service/requirements.txt`
4. Run Black formatting check
5. Run Flake8 linting
6. Run MyPy type checking
7. Run pytest

#### 2. `integration-tests`

Runs integration tests that call the Google Gemini API. Only runs on `main` after `test` passes.

**Timeout:** 10 minutes

**Required Secrets:**
| Secret | Purpose |
|--------|---------|
| `GOOGLE_API_KEY` | Authenticate with Google Gemini API |

If the secret is not configured, integration tests are skipped gracefully.

## iOS CI

**File:** `.github/workflows/ios-ci.yml`

**Note:** iOS CI also triggers on `backend/**` and `docs/api/**` changes because the iOS app depends on the OpenAPI spec generated from the backend.

### Jobs

#### 1. `lint-and-build`

Validates code quality, verifies the OpenAPI spec is in sync, and builds the project.

**Steps:**
1. Checkout code
2. Install SwiftLint and SwiftFormat via Homebrew
3. Run SwiftLint (strict mode)
4. Run SwiftFormat (lint mode)
5. List available simulators
6. Verify OpenAPI spec sync between `docs/api/openapi.json` and iOS package
7. Build iOS project
8. Run unit tests (AIQTests target)
9. Upload test results on failure

**Duration:** ~5-10 minutes

#### 2. `ui-tests`

Runs UI tests after `lint-and-build` passes.

**Steps:**
1. Checkout code
2. Boot iPhone 16 Pro simulator
3. Run UI tests with credentials from secrets
4. Upload test results (on both success and failure)

**Duration:** ~15-25 minutes (timeout: 30 minutes)

**Required Secrets:**
| Secret | Purpose |
|--------|---------|
| `AIQ_TEST_EMAIL` | Test account email |
| `AIQ_TEST_PASSWORD` | Test account password |

**Test Coverage:**
- Authentication flow (login/logout)
- Registration flow
- Test-taking flow
- Test abandonment handling
- Deep link navigation
- Error handling and recovery

### Test Result Artifacts

| Artifact | Uploaded | Retention |
|----------|----------|-----------|
| `ios-unit-test-results` | On failure | 7 days |
| `ui-test-results-failure` | On failure | 7 days |
| `ui-test-results-success` | On success | 3 days |

To view: download the xcresult bundle from the workflow run's Artifacts section and open in Xcode.

### Running iOS Tests Locally

```bash
cd ios

# Unit tests
xcodebuild test \
  -project AIQ.xcodeproj \
  -scheme AIQ \
  -sdk iphonesimulator \
  -destination 'platform=iOS Simulator,name=iPhone 16 Pro,OS=latest'

# UI tests (requires credentials)
export AIQ_TEST_EMAIL="your-test-email@example.com"
export AIQ_TEST_PASSWORD="your-test-password"
xcodebuild test \
  -project AIQ.xcodeproj \
  -scheme AIQ \
  -sdk iphonesimulator \
  -destination 'platform=iOS Simulator,name=iPhone 16 Pro,OS=latest' \
  -only-testing:AIQUITests
```

## Pre-commit Checks

**File:** `.github/workflows/pre-commit.yml`

Runs on all PRs and pushes to `main`. Executes pre-commit hooks for both `backend/` and `question-service/` directories.

**Note:** Currently configured with `|| true` so failures don't block PRs. This is informational only.

## Close Jira on Merge

**File:** `.github/workflows/close-jira-on-merge.yml`

Triggers when a PR is merged. Extracts a ticket ID from the PR title (format: `[TASK-123] Description` or any `[PREFIX-123]` pattern) and:
1. Finds the appropriate "Done" transition (matches Done, Closed, Complete, or Resolved)
2. Transitions the Jira ticket (skips gracefully if no matching transition is available)
3. Adds a comment with the PR link and merge author

**Required Secrets:**
| Secret | Purpose |
|--------|---------|
| `JIRA_EMAIL` | Jira service account email |
| `JIRA_API_TOKEN` | Jira API token |
| `JIRA_DOMAIN` | Jira domain (e.g., `gioematt.atlassian.net`) |

## Claude Code

**File:** `.github/workflows/claude.yml`

Invokes the Claude Code GitHub Action when `@claude` is mentioned in issue comments, PR review comments, or issue bodies.

**Required Secrets:**
| Secret | Purpose |
|--------|---------|
| `CLAUDE_CODE_OAUTH_TOKEN` | Authenticate with Claude Code |

## Claude Code Review

**File:** `.github/workflows/claude-code-review.yml`

Runs an automated Claude Code review on every PR when opened or updated. Reviews code quality, potential bugs, performance, security, and test coverage. Posts review feedback as a PR comment.

**Required Secrets:**
| Secret | Purpose |
|--------|---------|
| `CLAUDE_CODE_OAUTH_TOKEN` | Authenticate with Claude Code |

## Certificate Monitor

**File:** `.github/workflows/certificate-monitor.yml`

Runs weekly (Monday 9am UTC) and on manual dispatch. Checks the Railway backend SSL certificate against the TrustKit pinned hashes in `ios/AIQ/TrustKit.plist`. Creates a GitHub issue if:
- Certificate is expiring within 30 days (warning)
- Certificate has expired (critical)
- Certificate hash doesn't match pinned hashes (critical)

Deduplicates issues to avoid flooding.

## Model Availability Check

**File:** `.github/workflows/model-availability-check.yml`

Runs weekly (Monday 8am UTC) and on manual dispatch. Tests that the AI model APIs used by the question-service are still available and responding. Checks Google, OpenAI, xAI, and Anthropic providers (each conditional on its API key secret being configured).

**Required Secrets:**
| Secret | Purpose |
|--------|---------|
| `GOOGLE_API_KEY` | Google Gemini API access |
| `OPENAI_API_KEY` | OpenAI API access |
| `XAI_API_KEY` | xAI API access |
| `ANTHROPIC_API_KEY` | Anthropic API access |

## Required GitHub Secrets Summary

| Secret | Used By |
|--------|---------|
| `AIQ_TEST_EMAIL` | iOS CI (UI tests) |
| `AIQ_TEST_PASSWORD` | iOS CI (UI tests) |
| `GOOGLE_API_KEY` | Question Service CI, Model Availability Check |
| `JIRA_EMAIL` | Close Jira on Merge |
| `JIRA_API_TOKEN` | Close Jira on Merge |
| `JIRA_DOMAIN` | Close Jira on Merge |
| `CLAUDE_CODE_OAUTH_TOKEN` | Claude Code, Claude Code Review |
| `OPENAI_API_KEY` | Model Availability Check |
| `XAI_API_KEY` | Model Availability Check |
| `ANTHROPIC_API_KEY` | Model Availability Check |

To configure: Repository Settings > Secrets and variables > Actions > New repository secret.

## How Tests Block PRs

1. Each CI workflow runs checks specific to the changed files
2. If any check fails, the job fails and appears as a failed check on the PR
3. Failed jobs prevent merging (when branch protection is enabled)
4. Path-based triggering ensures only relevant pipelines run

## Troubleshooting

### Backend: Database Migration Failures

**Cause:** Alembic migration fails against the PostgreSQL service container.

**Solution:**
1. Run migrations locally: `cd backend && alembic upgrade head`
2. Check for conflicting migration heads: `alembic heads`
3. Ensure `DATABASE_URL` is set correctly in your environment

### Backend: MyPy Type Errors

**Cause:** New code has type annotation issues.

**Solution:**
1. Run locally: `cd backend && mypy app/`
2. Ensure `PYTHONPATH` includes the repo root (for `libs/` imports)

### Question Service: Integration Tests Skipped

**Cause:** `GOOGLE_API_KEY` secret not configured.

**Solution:** This is expected on PRs (secrets are only available on `main`). Integration tests run on merge to `main`.

### iOS: OpenAPI Spec Out of Sync

**Cause:** Backend OpenAPI spec was updated but iOS copy wasn't synced.

**Solution:**
1. Run: `cd ios && scripts/sync_openapi_spec.sh`
2. Commit the updated spec

### iOS: Simulator Boot Timeout

**Cause:** macOS runner issue.

**Solution:** Re-run the job. If persistent, check GitHub Actions status page.

### iOS: Tests Passing Locally but Failing in CI

**Solution:**
1. Download xcresult from CI artifacts
2. Check for timing issues (CI runners are slower)
3. Review wait timeouts in test helpers

### Pre-commit: Failures Not Blocking

**Note:** Pre-commit checks run with `|| true` and don't currently block PRs. Run `pre-commit run --all-files` locally before committing.

## Related Documentation

- [Dependabot Configuration](../docs/infrastructure/DEPENDABOT.md)
- [iOS Coding Standards](../ios/docs/CODING_STANDARDS.md)
- [UI Test Helpers](../ios/AIQUITests/Helpers/README.md)
- [Pull Request Template](PULL_REQUEST_TEMPLATE.md)
- [Backend Deployment](../backend/DEPLOYMENT.md)
