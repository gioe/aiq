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
| **Deployment** | [backend/DEPLOYMENT.md](backend/DEPLOYMENT.md) |
| **Privacy Policy** | [website/PRIVACY_POLICY.md](website/PRIVACY_POLICY.md) |
| **Terms of Service** | [website/TERMS_OF_SERVICE.md](website/TERMS_OF_SERVICE.md) |

## External Services

### Railway (Production)
- **Backend API**: `https://aiq-backend-production.up.railway.app`
- **Health Check**: `https://aiq-backend-production.up.railway.app/v1/health`
- **API Docs**: `https://aiq-backend-production.up.railway.app/v1/docs`

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

## Required Skills Usage

When performing these operations, always use the corresponding skill instead of running commands directly:

| Operation | Skill | Instead of |
|-----------|-------|------------|
| Building iOS project | `/build-ios-project` | `xcodebuild build` |
| Running iOS tests | `/run-ios-test` | `xcodebuild test` |
| Adding Swift files to Xcode | `/xcode-file-manager` | Manual project.pbxproj edits |
