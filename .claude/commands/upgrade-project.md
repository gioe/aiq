---
description: Check latest Claude Code release notes and upgrade configuration to leverage new features
---

# Claude Code Upgrade Check

You are checking for new Claude Code features and comparing them against our current configuration to identify opportunities for improvement.

## Step 1: Fetch Latest Release Notes

Use WebFetch to get the latest Claude Code changelog from the official documentation:

```
https://docs.anthropic.com/en/docs/claude-code/changelog
```

Extract and summarize:
- Latest version number
- New features and capabilities
- New settings or configuration options
- New tools or plugins available
- Deprecated features or breaking changes

## Step 2: Review Current Configuration

Read and analyze our current Claude Code setup:

1. **Project settings**: `.claude/settings.json`
2. **Local settings**: `.claude/settings.local.json`
3. **Custom commands**: `.claude/commands/*.md`
4. **Custom agents**: `.claude/agents/*.md`
5. **Skills**: `.claude/skills/*/SKILL.md`
6. **Project instructions**: `CLAUDE.md`

## Step 3: Gap Analysis

Compare the release notes against our configuration to identify:

### New Features We Could Adopt
- New plugins or integrations that would benefit our workflow
- New configuration options that improve our setup
- New tools that could replace or enhance existing commands/agents

### Configuration Updates Needed
- Settings that should be updated for new features
- Deprecated settings that need migration
- New best practices we should follow

### Our Custom Extensions
- Which of our custom commands/agents might be replaced by built-in features
- Which remain valuable and unique to our workflow

## Step 4: Present Findings

Create a structured report:

```
## Claude Code Upgrade Report

### Current Version
[If detectable from claude --version or similar]

### Latest Version Features
[Summary of new capabilities from changelog]

### Recommended Changes

#### High Priority (Do Now)
- [ ] Change 1: [description and why]
- [ ] Change 2: [description and why]

#### Medium Priority (Consider Soon)
- [ ] Change 1: [description and why]

#### Low Priority (Nice to Have)
- [ ] Change 1: [description and why]

### No Action Needed
- Feature X: [why it's not useful for us]
- Feature Y: [why we already have equivalent]

### Custom Extensions Status
- Command/agent that could be deprecated: [name] - [reason]
- Command/agent still valuable: [name] - [reason]
```

## Step 5: Implement Changes (with approval)

For each recommended change:

1. Ask the user if they want to proceed with the change
2. If approved, make the configuration update
3. Verify the change works as expected
4. Document what was changed

## Important Notes

- Do NOT automatically make changes without user approval
- Preserve any custom configurations that are working well
- Consider backward compatibility with existing workflows
- Test any new features before fully adopting them
- Keep a record of what version we last upgraded from

## Common Upgrade Patterns

### Adding a new plugin
```json
// In settings.json
{
  "enabledPlugins": {
    "new-plugin@claude-plugins-official": true
  }
}
```

### Adding new permission
```json
// In settings.local.json permissions.allow array
"Bash(new-command:*)"
```

### Creating a new agent for new capability
Create `.claude/agents/new-agent.md` following existing patterns.
