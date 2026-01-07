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

## Step 3: Fetch the Latest Claude Review

Claude's reviews appear as issue comments from `claude[bot]`. Fetch them and get only the most recent one:

```bash
# Get PR issue comments and filter for claude[bot], sorted by created_at descending
gh api repos/{owner}/{repo}/issues/{pr_number}/comments --paginate \
  --jq '[.[] | select(.user.login == "claude[bot]")] | sort_by(.created_at) | reverse | .[0]'
```

This command:
1. Fetches all issue comments
2. Filters for comments where the user is `claude[bot]`
3. Sorts by `created_at` descending
4. Returns only the most recent comment

If there are no Claude comments, the result will be `null`.

## Step 4: Extract Comment Details

From the latest Claude comment, extract:
- Comment ID
- Comment body (full text)
- Created timestamp
- HTML URL (for reference)

## Step 5: Analyze Each Comment

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

1. Report what was deferred:
   ```
   **Claude's Comment**: "The comment text..."
   **Reason for deferral**: "We can do this later because..."
   ```

2. Using the jira-workflow-architect subagent, create a ticket in the Jira backlog. Check to see if any similar tasks are already in the backlog before creating a new one. **Include the reason for deferral in the ticket description**

3. **Document for next PR**: Append the deferral to `.github/DEFERRED_REVIEW_ITEMS.md` so it can be included in the next PR's commit message. This file should be committed with the PR changes:

   ```markdown
   ## Deferred from PR #{{pr_number}} Review

   ### [Brief description of deferred item]
   - **Original comment**: "[Abbreviated comment text]"
   - **Reason deferred**: [Why this can wait]
   - **Jira ticket**: [TICKET-ID]
   ```

   When creating the final commit for this PR, include a summary of deferrals in the commit body:
   ```
   [TASK-ID] Address PR review feedback

   Addressed:
   - [List of items fixed]

   Deferred (see Jira):
   - [TICKET-ID]: [Brief description] - [Reason]
   ```

   This ensures the next reviewer can see why certain review comments weren't addressed in this PR.

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
- Refactor scoring module for clarity
- Add performance benchmarks

### No Action Needed:
- Comment #123: Already addressed in previous commit
- Comment #456: Duplicate of addressed issue

```

## Step 8: Review Report

Using the technical-product-manager subagent and any relevant technical subagents, determine why  the content of the review was not handled as part of the workflow.
- Does our CODING_STANDARDS.md doc need to be updated?
- Do we disagree with the review content?


## Important Guidelines:

1. **Read before editing**: Always read the relevant files before making changes
2. **Verify Claude authorship**: Only process comments actually written by Claude
3. **Preserve context**: When deferring, include enough context to understand the issue later
4. **Atomic commits**: Each addressed issue gets its own commit
5. **Don't over-engineer**: Fix only what the comment specifically mentions
6. **Ask if unclear**: If a comment's intent is ambiguous, ask the user before acting
7. **Skip resolved comments**: If a comment was already addressed, note it but don't duplicate work
8. **Respect the codebase**: Follow existing patterns when making changes
9. **Update your knowledge** in response to good comments. We don't want to keep making the same review mistakes.

## Error Handling:

- If the PR URL is invalid, report the error and stop
- If no Claude comments are found, report "No Claude comments found on this PR"

Begin by reading the PR number and determining the likely url.
