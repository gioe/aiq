---
description: Generate technical implementation plan from a gap analysis document
args:
  - name: gap_file
    description: Name of the gap file from /docs/psychometric-methodology/gaps/ (e.g., EMPIRICAL-ITEM-CALIBRATION.md)
    required: true
---

You are generating a technical implementation plan based on a gap analysis document.

**Gap File**: docs/psychometric-methodology/gaps/{{gap_file}}

Follow these steps:

1. **Read the gap analysis document** at `docs/psychometric-methodology/gaps/{{gap_file}}`

2. **Derive a task prefix** from the gap file name:
   - Extract initials from the filename (e.g., EMPIRICAL-ITEM-CALIBRATION.md → EIC)
   - Use this prefix for all task IDs in the format: `{PREFIX}-001`, `{PREFIX}-002`, etc.
   - Common mappings:
     - EMPIRICAL-ITEM-CALIBRATION.md → EIC
     - RELIABILITY-ESTIMATION.md → RE
     - STANDARD-ERROR-OF-MEASUREMENT.md → SEM
     - ITEM-DISCRIMINATION-ANALYSIS.md → IDA
     - DISTRACTOR-ANALYSIS.md → DA
     - TIME-STANDARDIZATION.md → TS
     - CHEATING-DETECTION.md → CD
     - DOMAIN-WEIGHTING.md → DW

3. **Extract key information** from the document:
   - Problem Statement: What issue needs to be solved
   - Current State: What exists vs what's missing
   - Solution Requirements: Proposed functions, endpoints, and database changes
   - Success Criteria: What defines "done"
   - Testing Strategy: Required tests

4. **Generate a technical implementation plan** in markdown format:

   ```markdown
   # Implementation Plan: [Title from gap document]

   **Source:** docs/psychometric-methodology/gaps/{{gap_file}}
   **Task Prefix:** {PREFIX}
   **Generated:** {current date}

   ## Overview
   A 2-3 sentence summary of what this implementation addresses.

   ## Prerequisites
   - List any database migrations needed
   - List any new dependencies required
   - List any existing code that must be understood first

   ## Tasks

   ### {PREFIX}-001: [Brief Title]
   **Status:** [ ] Not Started
   **Files:** `path/to/file.py`
   **Description:** What to implement
   **Acceptance Criteria:**
   - [ ] Specific testable outcome
   - [ ] Another testable outcome

   ### {PREFIX}-002: [Brief Title]
   **Status:** [ ] Not Started
   **Files:** `path/to/file.py`
   **Description:** What to implement
   **Acceptance Criteria:**
   - [ ] Specific testable outcome

   (continue for all tasks...)

   ## Database Changes
   If the gap document mentions schema changes, detail them here with:
   - Table/column names
   - Data types
   - Migration approach

   ## API Endpoints
   If new endpoints are needed, list them with:
   - Method and path
   - Request/response schemas
   - Authentication requirements

   ## Testing Requirements
   Organize tests into:
   - Unit tests (with specific functions to test)
   - Integration tests (with specific scenarios)
   - Edge cases to cover

   ## Task Summary
   | Task ID | Title | Complexity |
   |---------|-------|------------|
   | {PREFIX}-001 | ... | Small/Medium/Large |
   | {PREFIX}-002 | ... | Small/Medium/Large |

   ## Estimated Total Complexity
   Rate as: Small (1-2 tasks), Medium (3-5 tasks), Large (6+ tasks)
   ```

5. **Output the plan** as a markdown file. Save to:
   `docs/psychometric-methodology/plans/PLAN-{{gap_file}}`

   For example, if the input is `EMPIRICAL-ITEM-CALIBRATION.md`, output to:
   `docs/psychometric-methodology/plans/PLAN-EMPIRICAL-ITEM-CALIBRATION.md`

6. **Create the plans directory** if it doesn't exist:
   ```bash
   mkdir -p docs/psychometric-methodology/plans
   ```

**Important Guidelines:**
- Each task gets a unique ID with the derived prefix (e.g., EIC-001, EIC-002)
- Task IDs must be unique and searchable via the `/task` command
- Tasks should be small enough to be completed atomically
- Include all code locations mentioned in the gap document
- Preserve technical details from the Solution Requirements section
- Maintain the recommended implementation order from the gap document
- Include specific function signatures where provided in the gap document
- Reference line numbers from the gap document where applicable

Begin by reading the gap analysis document.
