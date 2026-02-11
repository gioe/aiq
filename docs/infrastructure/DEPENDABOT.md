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
| swift | `/ios` | Weekly (Monday 9am ET) |
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

## Severity-Based SLA

Dependabot alerts should be addressed within the following timeframes based on severity:

| Severity | Response Time | Resolution Time | Action |
|----------|---------------|-----------------|--------|
| **Critical** | Same day | 48 hours | Drop current work. Merge security update or apply mitigation immediately. |
| **High** | 1 business day | 1 week | Prioritize in current sprint. Review and merge Dependabot PR or upgrade manually. |
| **Medium** | 1 week | 2 weeks | Schedule for next sprint. Merge Dependabot PR during regular dependency maintenance. |
| **Low** | 2 weeks | 1 month | Address during routine maintenance windows. Batch with other low-priority updates. |

**Response time** = acknowledge the alert and begin investigation.
**Resolution time** = merge a fix, apply a workaround, or document an accepted risk.

### Escalation

- If a Critical/High alert cannot be resolved within its SLA, document the blocker and notify the team.
- If a dependency has no fix available, check for alternative packages or apply the workaround documented in the CVE/advisory.
- Accepted risks must be documented with justification (e.g., the vulnerable code path is not reachable in our usage).

## Testing Dependabot PRs

Dependabot PRs go through the same CI pipeline as regular PRs. Here's how to verify them:

### Automated Checks

All Dependabot PRs are validated by the existing CI workflows:

| Ecosystem | CI Workflow | What's Checked |
|-----------|-------------|----------------|
| pip (backend) | Backend CI | Black, Flake8, MyPy, Alembic migrations, pytest |
| pip (question-service) | Question Service CI | Black, Flake8, MyPy, pytest |
| swift | iOS CI | SwiftLint, SwiftFormat, OpenAPI sync, build, unit tests, UI tests |
| github-actions | All workflows | Updated actions are validated indirectly by all CI workflows that use them |

### Manual Review Checklist

Before merging a Dependabot PR:

1. **CI passes** - All status checks are green
2. **Changelog review** - Open the dependency's changelog/release notes (linked in the PR body) and check for:
   - Breaking changes that could affect our usage
   - Deprecation notices for APIs we use
   - Behavioral changes (especially for testing/linting tools)
3. **Version jump** - For major version bumps, verify compatibility locally:
   ```bash
   # Python (backend or question-service)
   cd backend  # or question-service
   pip install <package>==<new-version>
   pytest -v

   # Swift
   cd ios
   xcodebuild build -project AIQ.xcodeproj -scheme AIQ -sdk iphonesimulator \
     -destination 'platform=iOS Simulator,name=iPhone 16 Pro,OS=latest'
   ```
4. **Security PRs** - For security updates, verify the CVE/advisory is addressed by checking the advisory link in the PR body

### When to Reject

- The update introduces a known regression (check the dependency's issue tracker)
- A major version bump requires code changes that are not yet ready
- The update conflicts with another pinned dependency

If rejecting, close the PR with a comment explaining why, and add an `ignore` rule in `dependabot.yml` for that specific version if needed.

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

### Schedule & Limits
- `open-pull-requests-limit`: 5 for Python, 3 for Swift/Actions
- `schedule.interval`: Weekly on Mondays at 9am ET
- `commit-message.prefix`: `[deps]` for easy filtering

### Versioning Strategy

The `versioning-strategy` controls how Dependabot proposes version changes. We use the default (`auto`) which selects the best strategy per ecosystem:

| Ecosystem | Default Strategy | Behavior |
|-----------|-----------------|----------|
| pip | `increase` | Bumps the version constraint to include the new version |
| swift | `increase` | Bumps the minimum version in `Package.swift` |
| github-actions | `increase` | Updates action version tags |

The default `auto` strategy is appropriate for this project because:
- Our Python services use unpinned requirements (`>=` style), so `increase` correctly bumps minimums
- Swift Package Manager handles resolution through `Package.resolved`
- GitHub Actions use tag-based versioning where `increase` updates the tag reference

### Allow/Ignore Restrictions

Currently no `allow` or `ignore` rules are configured. All dependencies are eligible for updates. This is intentional because:
- The project is in active development and benefits from staying current
- CI pipelines catch breaking changes before merge
- The `open-pull-requests-limit` prevents PR flooding

Add `ignore` rules only when a specific version is known to be incompatible:
```yaml
# Example: skip a breaking major version until migration is ready
ignore:
  - dependency-name: "some-package"
    versions: [">=3.0.0"]
```

### Grouping Strategy

Related dependency updates are grouped into fewer PRs to reduce review overhead:

| Group | Ecosystems | What's Included |
|-------|-----------|-----------------|
| `python-minor-patch` | pip (backend, question-service) | All minor and patch updates |
| `swift-all` | swift (iOS) | All Swift package updates |
| `github-actions-all` | github-actions | All GitHub Actions updates |

This means instead of receiving individual PRs for each dependency, related updates are batched:
- Python minor/patch updates for each service come in a single PR
- Swift dependency updates for each package location come in a single PR (up to 2 Swift PRs: one for the API Client package, one for the main Xcode project)
- All GitHub Actions updates come in a single PR

Major version updates are excluded from groups and arrive as individual PRs, since they are more likely to require careful review and code changes.

## Notifications

Alerts are sent to:
- Repository administrators via GitHub notifications
- Configured reviewers on auto-created PRs (@gioe)

To adjust notification preferences, see [GitHub notification settings](https://docs.github.com/en/account-and-profile/managing-subscriptions-and-notifications-on-github/setting-up-notifications/configuring-notifications).

## Related Documentation

- [CI/CD Setup Guide](../../.github/CI_CD_SETUP.md)
- [Dependabot options reference (GitHub Docs)](https://docs.github.com/en/code-security/dependabot/working-with-dependabot/dependabot-options-reference)
