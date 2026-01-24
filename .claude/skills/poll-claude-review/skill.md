---
name: poll-claude-review
description: Poll a GitHub PR for Claude's review comments. Waits for Claude to post a review and returns the content. Use after creating a PR to wait for automated review.
allowed-tools: Bash
---

# Poll Claude Review

Polls a GitHub PR for Claude's review comments. Useful after creating a PR when you need to wait for Claude's automated code review.

## Usage

```
/poll-claude-review <pr_number> [mode]
```

## Arguments

- `pr_number` (required): The PR number to poll
- `mode` (optional): `initial` (default) or `follow-up`
  - `initial`: Wait for the first Claude review
  - `follow-up`: Wait for a new review after you've pushed fixes

## Behavior

1. Polls `gh pr view <pr_number> --comments` every 30 seconds
2. Looks for comments from author `claude`
3. Times out after 10 minutes (20 attempts)
4. Returns the full review content when found

## Implementation

### Initial Review Mode (default)

Wait for Claude's first review on a PR:

```bash
PR_NUMBER=<pr_number>

for i in {1..20}; do
  COMMENTS=$(gh pr view $PR_NUMBER --comments 2>/dev/null)
  if echo "$COMMENTS" | grep -q "^author:.*claude"; then
    echo "Claude review found!"
    gh pr view $PR_NUMBER --comments | grep -A 1000 "^author:.*claude"
    exit 0
  fi
  echo "Waiting for Claude review... (attempt $i/20)"
  sleep 30
done

echo "Timeout: No Claude review found after 10 minutes"
exit 1
```

### Follow-up Review Mode

Wait for a NEW Claude review after pushing fixes:

```bash
PR_NUMBER=<pr_number>

# Count existing Claude comments
INITIAL_COUNT=$(gh pr view $PR_NUMBER --comments 2>/dev/null | grep -c "^author:.*claude" || echo "0")
echo "Found $INITIAL_COUNT existing Claude comment(s)"

for i in {1..20}; do
  CURRENT_COUNT=$(gh pr view $PR_NUMBER --comments 2>/dev/null | grep -c "^author:.*claude" || echo "0")
  if [ "$CURRENT_COUNT" -gt "$INITIAL_COUNT" ]; then
    echo "New Claude review found!"
    # Get the latest review (last claude comment block)
    gh pr view $PR_NUMBER --comments | tac | grep -B 1000 -m 1 "^author:.*claude" | tac
    exit 0
  fi
  echo "Waiting for new Claude review... (attempt $i/20)"
  sleep 30
done

echo "Timeout: No new Claude review found after 10 minutes"
exit 1
```

## Output

Returns the full Claude review content, including:
- Code quality assessment
- Security analysis
- Recommended fixes
- Approval status

## Examples

```
/poll-claude-review 726
```
Wait for Claude's initial review on PR #726.

```
/poll-claude-review 726 follow-up
```
Wait for Claude's next review after pushing fixes to PR #726.

## Integration with /next-task

This skill is used in the PR review loop of `/next-task`:

1. Create PR with `gh pr create`
2. Run `/poll-claude-review <pr_number>` to get initial review
3. Address Category A (blocking) issues
4. Push fixes
5. Run `/poll-claude-review <pr_number> follow-up` to get next review
6. Repeat until approved
7. Merge with `gh pr merge`

## Notes

- Uses `gh pr view --comments` which captures all comment types (issue comments, PR reviews, inline comments)
- Claude's author name appears as `claude` (not `claude[bot]`) in `gh pr view` output
- Polling interval is 30 seconds to balance responsiveness with API rate limits
- 10-minute timeout is configurable by modifying the loop count
