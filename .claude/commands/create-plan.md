---
description: Generate technical implementation plan from a gap analysis document
args:
  - name: gap_file
    description: Name of the gap file from /docs/gaps/ (e.g., EMPIRICAL-ITEM-CALIBRATION.md)
    required: true
---

Use the technical-product-manager subagent to derive tasks and acceptance criteria based on the gaps outlined in the document. Use the jira-workflow-architect subagent to write this information to Jira.

**Gap File**: docs/gaps/{{gap_file}}

Follow these steps:

1. **Read the gap analysis document** at `docs/gaps/{{gap_file}}`

2. **Extract key information** from the document:
   - Problem Statement: What issue needs to be solved
   - Current State: What exists vs what's missing
   - Solution Requirements: Proposed functions, endpoints, and database changes
   - Success Criteria: What defines "done"
   - Surface Area: What components of our system will require changes.
   - Testing Strategy: Required tests

3. **Write the tasks to Jira**, making sure to leverage as many fields as possible, including but not limited to:
   - Priority
   - Description
   - Labels

4. Once complete, **write a summary document in markdown** and save it to docs/plans/in-progress.

**Important Guidelines:**
- Tasks must have test coverage and logging as part of their acceptance criteria
- Include all code locations mentioned in the gap document
- Preserve technical details from the Solution Requirements section
- Include specific function signatures where provided in the gap document
- Reference line numbers from the gap document where applicable
- Make all subagent decisions based on the agents existing in the ~/.claude/agents directory and their relevance to the Task.

Begin by reading the gap analysis document.
