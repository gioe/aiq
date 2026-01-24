# Dependabot Configuration

GitHub Dependabot is configured for automated dependency vulnerability scanning and version updates across all package ecosystems in the AIQ project.

## Enabled Features

### Security Alerts
- **Dependabot Alerts**: Enabled - notifies about vulnerable dependencies
- **Dependabot Security Updates**: Enabled - auto-creates PRs for security fixes

### Version Updates
Configured in `.github/dependabot.yml` for:

| Ecosystem | Directory | Schedule |
|-----------|-----------|----------|
| pip (Python) | `/backend` | Weekly (Monday 9am ET) |
| pip (Python) | `/question-service` | Weekly (Monday 9am ET) |
| swift | `/ios/Packages/AIQAPIClient` | Weekly (Monday 9am ET) |
| github-actions | `/` | Weekly (Monday 9am ET) |

## Viewing Alerts

### Via GitHub CLI
```bash
# List all alerts
gh api repos/gioe/aiq/dependabot/alerts --jq '.[] | {number, state, severity: .security_advisory.severity, package: .dependency.package.name}'

# Count open alerts
gh api repos/gioe/aiq/dependabot/alerts --jq '[.[] | select(.state == "open")] | length'

# Filter by severity
gh api repos/gioe/aiq/dependabot/alerts --jq '[.[] | select(.security_advisory.severity == "critical")]'
```

### Via GitHub Web UI
Navigate to: https://github.com/gioe/aiq/security/dependabot

## Handling Alerts

### Automatic PRs
Dependabot will automatically create PRs for:
- Security vulnerabilities with available fixes
- Version updates according to the schedule

### Manual Resolution
For alerts without automatic fixes:
1. Review the alert details in GitHub Security tab
2. Check if a newer version of the package resolves the issue
3. If no fix available, consider:
   - Alternative packages
   - Applying workarounds documented in the CVE
   - Accepting the risk with documented justification

### PR Labels
Dependabot PRs are labeled by ecosystem:
- `dependencies` - All dependency PRs
- `python`, `swift`, `github-actions` - Ecosystem-specific
- `backend`, `question-service`, `ios` - Service-specific

## Configuration Reference

The configuration file is at `.github/dependabot.yml`. Key settings:

- `open-pull-requests-limit`: 5 for Python, 3 for Swift/Actions
- `schedule.interval`: Weekly on Mondays
- `commit-message.prefix`: `[deps]` for easy filtering

## Notifications

Alerts are sent to:
- Repository administrators via GitHub notifications
- Configured reviewers on auto-created PRs (@gioe)

To adjust notification preferences, see [GitHub notification settings](https://docs.github.com/en/account-and-profile/managing-subscriptions-and-notifications-on-github/setting-up-notifications/configuring-notifications).
