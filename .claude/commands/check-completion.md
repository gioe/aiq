---
description: Verify that all tasks in a plan file are complete and update documentation
args:
  - name: plan_file
    description: Path to the plan markdown file to verify (e.g., PLAN_EMPIRICAL_CALIBRATION)
    required: true
---

You are verifying that a plan has been fully completed and updating documentation to reflect the completed work.

**Plan File**: docs/plans/in-progress/{{plan_file}}.md

## Step 1: Read and Parse the Plan File

1. **Read the plan file** at the specified path
2. **Extract all tasks** by looking for:
   - Checkbox patterns: `- [ ]` (incomplete) and `- [x]` or `- [X]` (complete)
   - Task ID patterns (e.g., `EIC-001`, `P8-010`, etc.)
   - Acceptance criteria checkboxes within tasks
3. **Identify the plan type** (e.g., "Empirical Item Calibration", "In-Progress Test Detection")

## Step 2: Verify Checkbox Completion

1. **Count checkboxes**:
   - Total checkboxes found
   - Completed checkboxes (`[x]` or `[X]`)
   - Incomplete checkboxes (`[ ]`)

2. **Report status**:
   - If ANY incomplete checkboxes exist, report: "INCOMPLETE: Found X incomplete tasks"
   - List each incomplete task with its ID and description

## Step 3: Verify Code Implementation

For each task marked as complete, verify the implementation exists:

1. **Extract implementation details** from the plan:
   - File paths mentioned (e.g., `backend/app/core/scoring.py`)
   - Function/class names mentioned
   - API endpoints mentioned
   - Database migrations mentioned

2. **Verify each element exists**:
   - Use Glob/Read to check files exist
   - Use Grep to verify functions/classes are implemented
   - Check that test files exist if tests were required

3. **Report verification results**:
   - List each verified component
   - Flag any missing implementations

## Step 4: Decision Point

### If Work is INCOMPLETE:

Report to the user:
```
## Plan Completion Status: INCOMPLETE

### Missing Checkboxes:
- [ ] Task-ID: Description

### Missing Implementations:
- File `path/to/file.py` not found
- Function `function_name` not implemented

### Recommendation:
Complete the above items before marking this plan as done.
```

**STOP HERE** - Do not proceed to documentation updates.

### If Work is COMPLETE:

Proceed to Step 5.

## Step 5: Update Documentation (Only if Complete)

When all tasks are verified complete, update the following documentation:

### 5.1 Architecture Overview
**File**: `docs/architecture/OVERVIEW.md`

Update relevant sections:
- Add new API endpoints to the endpoint list
- Add new database fields to schema descriptions
- Update component responsibilities if expanded
- Add new data flows if applicable
- Update the ASCII architecture diagram if significant changes

### 5.2 Documentation Index
**File**: `docs/INDEX.md`

- Ensure the plan is listed under "Implementation Plans"
- Update status if applicable

### 5.3 Main README
**File**: `README.md`

- Update feature list if new user-facing features added
- Update component descriptions if significantly changed

### 5.4 Component READMEs
Update relevant component documentation:
- `backend/README.md` for API/backend changes
- `ios/README.md` for iOS app changes
- `question-service/README.md` for question service changes

### 5.5 CLAUDE.md
**File**: `CLAUDE.md`

Update if new:
- Commands or scripts added
- Database schema changes
- API endpoints added
- Development patterns established

### 5.6 Plan File Status
Update the plan file itself:
- Add a "Completed" status at the top
- Add completion date

## Step 6: Create Completion Summary

Generate a summary for the user:

```
## Plan Completion Verified: {{plan_file}}

### Tasks Completed:
- [x] Task-001: Description
- [x] Task-002: Description
...

### Documentation Updated:
- docs/architecture/OVERVIEW.md - Added new endpoints, updated schema
- CLAUDE.md - Added new API endpoints section
- backend/README.md - Updated feature list

### New Components Added:
- `backend/app/api/v1/endpoints/new_endpoint.py`
- `backend/app/core/new_module.py`

### Verification Summary:
- Total tasks: X
- All checkboxes: Complete
- Code verification: Passed
- Documentation: Updated
```

## Important Guidelines:

1. **Be thorough** - Check every checkbox and every mentioned file
2. **Don't assume** - Actually verify code exists, don't just check filenames
3. **Be specific** - List exact file paths and function names in reports
4. **Preserve existing content** - When updating docs, add to existing content, don't replace
5. **Maintain formatting** - Match the style of existing documentation
6. **Create atomic commits** - Commit documentation updates with message: `[DOCS] Update documentation for completed {{plan_file}}`

Begin by reading the plan file at docs/plans/in-progress/{{plan_file}}.md.
