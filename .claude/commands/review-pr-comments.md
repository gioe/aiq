---
description: Review Claude's PR comments and address or defer them
args:
  - name: pr_url
    description: GitHub PR URL (e.g., https://github.com/owner/repo/pull/123)
    required: true
---

You are reviewing PR comments written by Claude on a GitHub pull request. Your job is to analyze each comment, decide if it needs immediate attention or can be deferred, and take appropriate action.

**PR URL**: {{pr_url}}

## Step 1: Extract PR Information

Parse the GitHub PR URL to extract:
- Owner/organization
- Repository name
- PR number

For example, from `https://github.com/mattgioe/aiq/pull/225`:
- Owner: `mattgioe`
- Repo: `aiq`
- PR number: `225`

## Step 2: Fetch PR Comments

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

### Category B: Can Be Deferred (Add to Plan)
Comments that can be addressed later:
- **Code style suggestions**: Naming conventions, formatting preferences
- **Refactoring suggestions**: "Could be cleaner if..."
- **Documentation requests**: "Consider adding a docstring"
- **Nice-to-have improvements**: Performance optimizations for non-critical paths
- **Future considerations**: "In the future, we might want to..."
- **Minor TODOs**: Non-critical cleanup items

## Step 5: Determine Current Plan File

1. Get the current branch name: `git branch --show-current`
2. Extract the task prefix from the branch (e.g., `feature/IDA-008-...` → `IDA`)
3. Map the prefix to a plan file:
   - `IDA` → `docs/psychometric-methodology/plans/PLAN-ITEM-DISCRIMINATION-ANALYSIS.md`
   - `EIC` → `docs/psychometric-methodology/plans/PLAN-EMPIRICAL-ITEM-CALIBRATION.md`
   - `DA` → `docs/psychometric-methodology/plans/PLAN-DISTRACTOR-ANALYSIS.md`
   - `P#` → `PLAN.md` (main project plan)
   - If unclear, check `docs/psychometric-methodology/plans/` for relevant files

4. If no plan file exists for the current work, use `PLAN.md` as the fallback

## Step 6: Take Action

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

1. Read the current plan file
2. Add a new task entry under a "## Future Improvements" or "## Deferred Items" section:
   ```markdown
   ### {PREFIX}-XXX: [Brief title from comment]
   **Status:** [ ] Not Started
   **Source:** PR #{{pr_number}} comment
   **Files:** `path/to/file.py`
   **Description:** [Summarize Claude's suggestion]
   **Original Comment:** "[Quote the relevant part]"
   ```

3. Report what was deferred:
   ```
   ## Deferred to Plan: [Brief description]
   **File**: path/to/file.py:123
   **Claude's Comment**: "The comment text..."
   **Added as**: {PREFIX}-XXX in {plan_file}
   ```

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

### Files Modified:
- backend/app/core/scoring.py
- docs/psychometric-methodology/plans/PLAN-EMPIRICAL-ITEM-CALIBRATION.md
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

Begin by parsing the PR URL and fetching the comments.
