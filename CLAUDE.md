## Project Overview

AIQ tracks cognitive capacity over time, similar to how fitness apps track physical metrics. Users take periodic IQ-style tests with AI-generated questions, and the app visualizes their cognitive trends.

## Quick Reference

| Resource | Location |
|----------|----------|
| **Backend** | [backend/README.md](backend/README.md) |
| **Question Service** | [question-service/README.md](question-service/README.md) |
| **iOS App** | [ios/README.md](ios/README.md) |
| **Architecture** | [docs/architecture/OVERVIEW.md](docs/architecture/OVERVIEW.md) |
| **Methodology** | [docs/methodology/](docs/methodology/) |
| **Deployment** | [docs/deployment/](docs/deployment/) |
| **Code Review Patterns** | [docs/code-review-patterns.md](docs/code-review-patterns.md) |
| **Privacy Policy** | [docs/PRIVACY_POLICY.md](docs/PRIVACY_POLICY.md) |
| **Terms of Service** | [docs/TERMS_OF_SERVICE.md](docs/TERMS_OF_SERVICE.md) |

## External Services

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
