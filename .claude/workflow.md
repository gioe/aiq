# AIQ Development Workflow

This document defines the development workflow and conventions for the AIQ project.

## Project Structure

- **Root**: `/Users/mattgioe/iq-tracker/`
- **iOS App**: `/Users/mattgioe/iq-tracker/ios/`
- **Backend**: `/Users/mattgioe/iq-tracker/backend/`
- **Plan**: `/Users/mattgioe/iq-tracker/PLAN.md`

## Branching Strategy

### Branch Naming Convention

Create a new branch for each task following this pattern:

```
P{Phase}-{TaskNumber}/{kebab-case-description}
```

**Examples:**
- `P4-003/answer-input-components`
- `P4-006/local-answer-storage`
- `P5-001/build-history-view`

### Branch Creation Rules

1. **One branch per task** - Each task in PLAN.md gets its own feature branch
2. **Branch from main** - Always create branches from the main branch (unless specified otherwise)
3. **Descriptive names** - Use clear, kebab-case descriptions that match the task
4. **Follow the pattern** - Phase number and task number must match PLAN.md exactly

### Example Workflow

```bash
# Find the task in PLAN.md (e.g., P4-007: Build test submission logic)
# Create and checkout the branch
git checkout main
git pull
git checkout -b P4-007/test-submission-logic
```

## Task Completion Workflow

When completing a task, follow these steps **in order**:

### 1. Implementation
- Complete all code changes
- Ensure the implementation matches the task requirements in PLAN.md
- Add necessary tests (if applicable)

### 2. Update PLAN.md

Mark the task as complete in PLAN.md:

**Before:**
```markdown
- [ ] **P4-007**: Build test submission logic
```

**After:**
```markdown
- [x] **P4-007**: Build test submission logic
```

### 3. Commit Changes

Commit both the implementation AND the PLAN.md update together:

```bash
git add .
git commit -m "Your commit message
```

### 5. Push to Remote

```bash
git push -u origin P4-007/test-submission-logic
```

### 6. Create Pull Request (if ready)

Use the `gh` CLI to create a PR:

```bash
gh pr create --title "P4-007: Build test submission logic" --body "$(cat <<'EOF'
## Summary
- Implemented test submission logic
- Added validation for answers
- Connected to backend API

## Test plan
- [ ] Test submitting with all questions answered
- [ ] Test validation errors
- [ ] Test network error handling

EOF
)"
```

## Commit Message Conventions

### Standard Commits

```
{Brief description of changes}

{Optional detailed explanation}

```

### Task Completion Commits

When marking a task complete, the commit message should reference the task:

```
[P4-007] Build test submission logic

Implemented test submission with validation and error handling.
Updated PLAN.md to mark task complete.


```

## Working with PLAN.md

### Task Format

Tasks in PLAN.md follow this structure:

```markdown
### Phase X: {Phase Name}

**Goal:** {Phase description}

**Tasks:**
- [ ] **P{Phase}-{Number}**: {Task description}
- [ ] **P{Phase}-{Number}**: {Task description}
- [x] **P{Phase}-{Number}**: {Task description} (completed)

**Dependencies:** {Dependencies}
```

### Marking Tasks Complete

**IMPORTANT:** Always update PLAN.md when completing a task:

1. Change `[ ]` to `[x]`
2. Include the PLAN.md change in the same commit as the implementation
3. Push both changes together

**Example:**

```bash
# After completing implementation
git add ios/AIQ/...
git add PLAN.md
git commit -m "[P4-007] Build test submission logic


```

## Pull Request Guidelines

### PR Titles

Use the task number and description:

```
P4-007: Build test submission logic
```

### PR Description Template

```markdown
## Summary
- {Bullet point 1}
- {Bullet point 2}
- {Bullet point 3}

## Test plan
- [ ] {Test case 1}
- [ ] {Test case 2}
- [ ] {Test case 3}

## Notes
{Any additional context}

```

### Creating PRs

Use the GitHub CLI:

```bash
gh pr create --title "P4-007: Build test submission logic" --body "..."
```

## Troubleshooting

### Pre-commit Hook Failures

If pre-commit hooks fail:

1. **Read the error** - The hook will tell you which file and line has an issue
2. **Fix manually** or **run auto-fix**:
3. **Re-commit** - The hooks will run again

### Merge Conflicts on Push

If the remote has changes you don't have locally:

```bash
git stash                    # Save local changes
git pull --rebase            # Rebase on remote changes
git stash pop                # Restore local changes
# Fix any conflicts if needed
git push
```

## Quick Reference

### Starting a New Task

```bash
# 1. Checkout main and update
git checkout main
git pull

# 2. Create task branch (from PLAN.md)
git checkout -b P4-XXX/task-description

# 3. Implement the feature
# ... code ...

# 4. Check quality
cd ios

# 5. Update PLAN.md (mark task complete)
# Edit PLAN.md: [ ] → [x]

# 6. Commit everything
git add .
git commit -m "[P4-XXX] Task description

# 7. Push
git push -u origin P4-XXX/task-description

# 8. Create PR
gh pr create --title "P4-XXX: Task description" --body "..."
```

### Common Commands

```bash
# Check current branch status
git status

# View recent commits
git log --oneline -5

# View all branches
git branch -a
```

---
