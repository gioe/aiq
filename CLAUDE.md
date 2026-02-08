## Project Overview

AIQ tracks cognitive capacity over time, similar to how fitness apps track physical metrics. Users take periodic IQ-style tests with AI-generated questions, and the app visualizes their cognitive trends.

## Quick Reference

| Resource | Location |
|----------|----------|
| **Backend** | [backend/README.md](backend/README.md) |
| **Question Service** | [question-service/README.md](question-service/README.md) |
| **iOS App** | [ios/README.md](ios/README.md) |
| **Architecture** | [docs/architecture/OVERVIEW.md](docs/architecture/OVERVIEW.md) |
| **Methodology** | [docs/methodology/METHODOLOGY.md](docs/methodology/METHODOLOGY.md) |
| **Model Benchmarks** | [docs/MODEL_BENCHMARKS.md](docs/MODEL_BENCHMARKS.md) |
| **Deployment** | [backend/DEPLOYMENT.md](backend/DEPLOYMENT.md) |
| **Privacy Policy** | [website/PRIVACY_POLICY.md](website/PRIVACY_POLICY.md) |
| **Terms of Service** | [website/TERMS_OF_SERVICE.md](website/TERMS_OF_SERVICE.md) |

## External Services

### Railway (Production)
- **Backend API**: `https://aiq-backend-production.up.railway.app`
- **Health Check**: `https://aiq-backend-production.up.railway.app/v1/health`
- **API Docs**: `https://aiq-backend-production.up.railway.app/v1/docs`

#### Railway Service Topology

This is a monorepo with two independent Railway services sharing `libs/`. Both Dockerfiles build from the **repo root** to access `libs/`.

| | Backend | Question Service |
|---|---|---|
| **Railway root dir** | `/` | `/` |
| **railway.json** | `railway.json` (repo root) | `question-service/railway.json` |
| **Dockerfile** | `backend/Dockerfile` | `question-service/Dockerfile.trigger` |
| **Healthcheck** | `/v1/health` | None (cron/trigger service) |
| **Watch paths** | `/backend/**`, `/libs/**` | `/question-service/**`, `/libs/**` |
| **Restart policy** | `ON_FAILURE` (max 10) | `NEVER` |
| **PYTHONPATH** | `/app:/app/backend` | `/app:/app/question-service` |

**Critical rule**: The root `railway.json` belongs to the **backend**, not to the whole repo. Changing it affects the backend only. The question-service has its own `question-service/railway.json`. Never merge these or create conflicting configs.

### Atlassian (Jira/Confluence)
- **Cloud ID**: `db4de7e6-1840-4ba8-8e45-13fdf7ae9753`
- **Site URL**: https://gioematt.atlassian.net
- Always use this cloudId for all Atlassian MCP tool calls.

### GitHub
- **Repository**: `gioe/aiq`
- Use the `gh` CLI for all GitHub operations instead of WebSearch or manual API calls.

**Common Commands:**
| Task | Command |
|------|---------|
| View PR | `gh pr view <number>` |
| List PRs | `gh pr list` |
| Create PR | `gh pr create --title "..." --body "..."` |
| View issue | `gh issue view <number>` |
| List issues | `gh issue list` |
| Check CI status | `gh run list` / `gh run view <id>` |
| View PR comments | `gh api repos/{owner}/{repo}/pulls/<number>/comments` |

## Committing & Pre-commit

Before committing, run pre-commit hooks locally (`pre-commit run --all-files`) and fix any linting (e.g., E402 import order), mypy type errors, or float comparison issues. Do not assume pre-commit will pass — verify first.

## Task Queue

The project task database is the SQLite DB at the project root (`tasks.db`), not Claude Code's internal task list. Always use the project's SQLite database when working with the task queue.

## General Rules

If a test or command fails, do NOT re-run the exact same command more than twice. Instead, analyze the error output, change approach, or ask the user for guidance.

## Required Skills Usage

When performing these operations, always use the corresponding skill instead of running commands directly:

| Operation | Skill | Instead of |
|-----------|-------|------------|
| Building iOS project | `/build-ios-project` | `xcodebuild build` |
| Running iOS tests | `/run-ios-test` | `xcodebuild test` |
| Adding Swift files to Xcode | `/xcode-file-manager` | Manual project.pbxproj edits |
