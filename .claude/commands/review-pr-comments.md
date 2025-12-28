---
description: Review Claude's PR comments and address or defer them
args:
  - name: pr_number
    description: GitHub PR Number (e.g., 123, 400, 2)
    required: true
---

You are reviewing PR comments written by Claude on a GitHub pull request. Your job is to analyze each comment, decide if it needs immediate attention or can be deferred, and take appropriate action.

## Step 1: Determine the URL

Based on the current git directory and/or upstream, determine the url of the PR based on the provided pr_number.

Example, from `https://github.com/mattgioe/aiq/pull/{{pr_number}}`:

## Step 2: Extract PR Information

Parse the GitHub PR URL to extract:
- Owner/organization
- Repository name
- PR number

For example, from `https://github.com/mattgioe/aiq/pull/{{pr_number}}`:
- Owner: `mattgioe`
- Repo: `aiq`
- PR number: `225`

## Step 3: Fetch PR Comments

Use the GitHub CLI to fetch comments. Run these commands:

```bash
# Get PR review comments (inline code comments)
gh api repos/{owner}/{repo}/pulls/{pr_number}/comments --paginate

# Get PR issue comments (general discussion comments)
gh api repos/{owner}/{repo}/issues/{pr_number}/comments --paginate
```

## Step 3: Filter for Claude's Comments

Look for comments where the author matches any of these patterns:
- Username contains "claude" (case-insensitive)
- Username is "github-actions[bot]" AND comment body contains "Claude" signature
- Comment body contains signatures like "🤖 Generated with Claude" or similar
- Author login: `anthropics-claude`, `claude-bot`, `claude`, or similar

Extract from each matching comment:
- Comment ID
- Comment body (full text)
- File path (for review comments)
- Line number (for review comments)
- Created timestamp

## Step 4: Analyze Each Comment

For each Claude comment, analyze the content to categorize it:

### Category A: Requires Immediate Attention
Comments that should be addressed NOW:
- **Security concerns**: XSS, SQL injection, authentication issues, secrets exposure
- **Bug reports**: Logic errors, null pointer issues, race conditions
- **Breaking changes**: API contract violations, backwards incompatibility
- **Test failures**: Comments about failing or missing tests
- **Critical performance issues**: O(n²) in hot paths, memory leaks
- **Type errors**: Missing types, incorrect types that will cause runtime errors
- **Missing error handling**: Unhandled exceptions in critical paths

### Category B: Can Be Deferred
Comments that can be addressed later:
- **Code style suggestions**: Naming conventions, formatting preferences
- **Refactoring suggestions**: "Could be cleaner if..."
- **Documentation requests**: "Consider adding a docstring"
- **Nice-to-have improvements**: Performance optimizations for non-critical paths
- **Future considerations**: "In the future, we might want to..."
- **Minor TODOs**: Non-critical cleanup items


## Step 5: Take Action

### For Category A (Immediate) Comments:

1. Report the comment to the user:
   ```
   ## Addressing: [Comment Type]
   **File**: path/to/file.py:123
   **Claude's Comment**: "The comment text..."
   **Action**: Implementing fix...
   ```

2. Read the relevant file(s)
3. Make the necessary code changes using Edit tool
4. Create an atomic commit with message: `[{TASK-ID}] Address PR review: {brief description}`

### For Category B (Deferred) Comments:


1. Report what was deferred:
   ```
   **Claude's Comment**: "The comment text..."
   **Reason for deferral**: "We can do this later because..."
   ```
2. Using the jira-workflow-architect subagent, create a ticket in the Jira backlog. Check to see if any similar tasks are already in the backlog before creating a new one.

## Step 7: Generate Summary Report

After processing all comments, provide a summary:

```
## PR Comment Review Summary

**PR**: {{pr_url}}
**Claude Comments Found**: X

### Addressed Immediately:
- [x] Security: Fixed SQL injection in user_query.py
- [x] Bug: Added null check in process_response()

### Deferred to Plan:
- [ ] EIC-015: Refactor scoring module for clarity
- [ ] EIC-016: Add performance benchmarks

### No Action Needed:
- Comment #123: Already addressed in previous commit
- Comment #456: Duplicate of addressed issue

```

## Important Guidelines:

1. **Read before editing**: Always read the relevant files before making changes
2. **Verify Claude authorship**: Only process comments actually written by Claude
3. **Preserve context**: When deferring, include enough context to understand the issue later
4. **Atomic commits**: Each addressed issue gets its own commit
5. **Don't over-engineer**: Fix only what the comment specifically mentions
6. **Ask if unclear**: If a comment's intent is ambiguous, ask the user before acting
7. **Skip resolved comments**: If a comment was already addressed, note it but don't duplicate work
8. **Respect the codebase**: Follow existing patterns when making changes

## Error Handling:

- If the PR URL is invalid, report the error and stop
- If no Claude comments are found, report "No Claude comments found on this PR"
- If the plan file doesn't exist, create the "Deferred Items" section in PLAN.md
- If a file mentioned in a comment no longer exists, note it as "File not found - may have been moved/deleted"

Begin by reading the PR number and determining the likely url.
