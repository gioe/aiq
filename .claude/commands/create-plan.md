---
description: Generate technical implementation plan from a gap analysis document
args:
  - name: gap_file
    description: Name of the gap file from /docs/gaps/ (e.g., EMPIRICAL-ITEM-CALIBRATION.md)
    required: true
---

Use the technical-product-manager subagent to generate a technical implementation plan based on the provided gap_file.

**Gap File**: docs/gaps/{{gap_file}}

Follow these steps:

1. **Read the gap analysis document** at `docs/gaps/{{gap_file}}`

2. **Derive a task prefix** from the gap file name:
   - Extract initials from the filename (e.g., EMPIRICAL-ITEM-CALIBRATION.md → EIC)
   - Use this prefix for all task IDs in the format: `{PREFIX}-001`, `{PREFIX}-002`, etc.
   - Common mappings:
     - EMPIRICAL-ITEM-CALIBRATION.md → EIC
     - RELIABILITY-ESTIMATION.md → RE
     - STANDARD-ERROR-OF-MEASUREMENT.md → SEM

3. **Extract key information** from the document:
   - Problem Statement: What issue needs to be solved
   - Current State: What exists vs what's missing
   - Solution Requirements: Proposed functions, endpoints, and database changes
   - Success Criteria: What defines "done"
   - Surface Area: What components of our system will require changes.
   - Testing Strategy: Required tests

4. **Generate a technical implementation plan** in markdown format:

   ```markdown
   # Implementation Plan: [Title from gap document]

   **Source:** docs/gaps/{{gap_file}}
   **Task Prefix:** {PREFIX}
   **Generated:** {current date}

   ## Overview
   A 2-3 sentence summary of what this implementation addresses.

   ## Tasks

   ### {PREFIX}-001: [Brief Title]
   **Status:** [ ] Not Started
   **Files:** `path/to/file.py`
   **Description:** What to implement
   **Assignee(s):** The subagent(s) that should work on this task
   **Acceptance Criteria:**
   - [ ] Specific testable outcome
   - [ ] Another testable outcome

   ### {PREFIX}-002: [Brief Title]
   **Status:** [ ] Not Started
   **Files:** `path/to/file.py`
   **Description:** What to implement
   **Assignee(s):** The subagent(s) that should work on this task
   **Acceptance Criteria:**
   - [ ] Specific testable outcome

   (continue for all tasks...)

   ```

5. **Output the plan** as a markdown file. Save to:
   `docs/plans/in-progress/PLAN-{{gap_file}}`

   For example, if the input is `EMPIRICAL-ITEM-CALIBRATION.md`, output to:
   `docs/plans/in-progress/PLAN-EMPIRICAL-ITEM-CALIBRATION.md`

**Important Guidelines:**
- Each task gets a unique ID with the derived prefix (e.g., EIC-001, EIC-002)
- Task IDs must be unique and searchable via the `/task` command
- Tasks should be small enough to be completed atomically
- Tasks must have test coverage as part of their acceptance criteria
- Include all code locations mentioned in the gap document
- Preserve technical details from the Solution Requirements section
- Maintain the recommended implementation order from the gap document
- Include specific function signatures where provided in the gap document
- Reference line numbers from the gap document where applicable
- Make all subagent decisions based on the agents existing in the ~/.claude/agents directory and their relevance to the Task.

Begin by reading the gap analysis document.
