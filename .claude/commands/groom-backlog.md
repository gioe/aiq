---
description: Groom the Jira backlog by removing redundant/stale tickets and reprioritizing
args: []
---

Immediately delegate this entire task to the `technical-product-manager` subagent. Do NOT fetch any Jira tickets yourself - the subagent will handle all fetching and analysis. Pass the following instructions to the subagent:

---

You are grooming the Jira backlog for the AIQ project. Your goal is to clean up the backlog by identifying and removing redundant or no longer relevant tickets, and by reprioritizing tickets that have incorrect priority levels.

## Step 1: Fetch All Backlog Tickets

Use the Jira CLI to fetch all open tickets from the backlog:

```bash
# Get all open tickets with full details
jira issue list --plain --no-truncate --columns KEY,TYPE,SUMMARY,STATUS,PRIORITY,LABELS,CREATED,UPDATED

# Also get tickets in raw JSON for detailed analysis
jira issue list --raw
```

## Step 2: Categorize Tickets

Analyze each ticket and categorize it into one of the following:

### Category A: Candidates for Deletion
Tickets that should be removed from the backlog:

1. **Redundant tickets**: Duplicates or near-duplicates of other tickets
2. **Completed work**: Tickets describing work that has already been done
3. **Obsolete tickets**: Tickets for features or fixes that are no longer relevant due to:
   - Changes in product direction
   - Superseded by other work
   - Technical approach that's no longer applicable
4. **Stale tickets**: Tickets that have been untouched for an extended period with no clear path forward
5. **Vague tickets**: Tickets with insufficient detail that cannot be acted upon

### Category B: Candidates for Reprioritization
Tickets that have incorrect priority levels:

1. **Under-prioritized**: Important tickets marked as low priority
   - Security-related issues
   - User-facing bugs
   - Dependencies for other critical work
2. **Over-prioritized**: Low-impact tickets marked as high priority
   - Nice-to-have features
   - Minor code improvements
   - Speculative future work

### Category C: Healthy Tickets
Tickets that are correctly prioritized and relevant. No action needed.

## Step 3: Review Context

Before taking action, gather additional context:

```bash
# View details of specific tickets to understand them better
jira issue view ISSUE-KEY --comments 5
```

Also review:
- Recent commits to see what work has been completed
- The product documentation in `docs/` to understand current priorities
- Any related tickets that might be duplicates

## Step 4: Present Findings for Approval

Present your analysis to the user in the following format:

```markdown
## Backlog Grooming Analysis

### Total Tickets Analyzed: X

---

### Recommended for Deletion (Y tickets)

| Ticket | Summary | Reason |
|--------|---------|--------|
| BTS-123 | "Add feature X" | Duplicate of BTS-456 |
| BTS-124 | "Fix bug Y" | Already completed in commit abc123 |

---

### Recommended for Reprioritization (Z tickets)

| Ticket | Summary | Current | Recommended | Reason |
|--------|---------|---------|-------------|--------|
| BTS-125 | "Security fix" | Low | High | Security issues should be high priority |
| BTS-126 | "Nice to have" | High | Low | No user impact, speculative |

---

### No Action Needed (W tickets)
These tickets are correctly prioritized and relevant.
```

## Step 5: Get User Confirmation

**IMPORTANT**: Before making any changes, explicitly ask the user:

1. "Do you approve deleting the X tickets listed above?"
2. "Do you approve the priority changes for the Y tickets listed above?"
3. "Would you like me to modify any of these recommendations?"

Wait for explicit user approval before proceeding.

## Step 6: Execute Changes

Only after user approval, execute the changes:

### For Deletions:
```bash
jira issue delete ISSUE-KEY
```

### For Priority Changes:
```bash
jira issue edit ISSUE-KEY -y "New Priority" --no-input
```

Valid priority values: Highest, High, Medium, Low, Lowest

## Step 7: Generate Summary Report

After all changes are complete, provide a summary:

```markdown
## Backlog Grooming Complete

### Actions Taken:
- **Deleted**: X tickets
- **Reprioritized**: Y tickets
- **Unchanged**: Z tickets

### Deleted Tickets:
- BTS-123: "Add feature X" (was duplicate)
- BTS-124: "Fix bug Y" (already completed)

### Priority Changes:
- BTS-125: Low -> High
- BTS-126: High -> Low

### Current Backlog Health:
- Total open tickets: N
- High priority: X
- Medium priority: Y
- Low priority: Z
```

## Important Guidelines

1. **Never delete without approval**: Always present findings and wait for explicit user confirmation before deleting any tickets
2. **Be conservative**: When in doubt about deletion, recommend keeping the ticket and flagging it for review
3. **Preserve history**: Note in the summary which tickets were deleted and why, so the information is not lost
4. **Consider dependencies**: Before deleting a ticket, check if other tickets reference it
5. **Explain reasoning**: For each recommendation, provide clear reasoning that the user can evaluate
6. **Batch operations carefully**: Execute deletions one at a time to handle any errors gracefully

## Error Handling

- If a ticket cannot be deleted (permissions, dependencies), report the error and continue with other tickets
- If the Jira CLI returns an error, report it and suggest troubleshooting steps
- If no tickets are found, report "No open tickets found in the backlog"

Begin by fetching all backlog tickets.
