---
name: next-task
description: Get the most important task that is ready to be worked on
allowed-tools: Bash, Task, Read, Edit, Write, Grep, Glob
---

# Next Task Skill

The primary interface for working with tasks from the local `tasks.db` SQLite database. Use this to get the next task, start working on it, and manage the full development workflow.

## Commands

### Get Next Task (default - no arguments)

Finds the highest-priority task that is ready to work on (no incomplete dependencies) and **automatically begins working on it**.

```bash
sqlite3 -header -column taskdb/tasks.db "
SELECT t.id, t.summary, t.priority, t.priority_score, t.domain, t.assignee, t.description
FROM tasks t
WHERE t.status = 'To Do'
  AND NOT EXISTS (
    SELECT 1 FROM task_dependencies d
    JOIN tasks blocker ON d.depends_on_id = blocker.id
    WHERE d.task_id = t.id AND blocker.status != 'Done'
  )
ORDER BY t.priority_score DESC, t.id
LIMIT 1;
"
```

**Note**: The `priority_score` is pre-computed by `/groom-backlog` and factors in priority level, how many tasks this unblocks, and task age. This enables fast, intelligent task selection without LLM inference.

After finding the next ready task, **immediately proceed to the "Begin Work on a Task" workflow** using the retrieved task ID. Do not wait for user confirmation.

### Begin Work on a Task (with task ID argument)

When called with a task ID (e.g., `/next-task 6`), begin the full development workflow:

**Follow these steps IN ORDER:**

1. **Fetch the task** from the local database:
   ```bash
   sqlite3 -header -column taskdb/tasks.db "SELECT * FROM tasks WHERE id = <id>"
   ```

2. **Start task metrics tracking**:
   ```bash
   ~/.claude/task-metrics.sh start "TASK-<id>" "<task_summary>"
   ```

3. **Update the task status** to In Progress:
   ```bash
   sqlite3 taskdb/tasks.db "UPDATE tasks SET status = 'In Progress', updated_at = datetime('now') WHERE id = <id>"
   ```

4. **Extract task details** including:
   - Summary
   - Description
   - Priority
   - Domain
   - Assignee

5. **Create a new git branch IMMEDIATELY**:
   - Format: `feature/TASK-<id>-brief-description`
   - Commands:
     ```bash
     git checkout main && git pull origin main
     git checkout -b feature/TASK-<id>-brief-description
     ```

6. **Use the technical-product-manager subagent** to determine the best subagent(s) for the task based on:
   - Task domain (iOS, Backend, etc.)
   - Task assignee field (often indicates the right agent type)
   - Task description and requirements

7. **Explore the codebase before implementing** — use a sub-agent to research and answer:
   - What files will need to change?
   - What's the correct virtualenv and PYTHONPATH for this area?
   - Are there existing patterns to follow (check the relevant CLAUDE.md)?
   - What tests already exist for this area?
   - Are there any related recent changes that could conflict?

   Report findings before writing any code. Sessions that skip this step have significantly higher friction from wrong-approach starts.

8. **Delegate the work** to the chosen subagent(s).

9. **Create atomic commits** as you complete logical units of work.
   - All commits should be on the feature branch, NOT main.

10. **Review the code locally** before considering the work complete.
   - Use the appropriate code review agent for the domain.

11. **Push the branch and create a PR**:
    ```bash
    git push -u origin feature/TASK-<id>-description
    gh pr create --title "[TASK-<id>] Brief task description" --body "..."
    ```
    Capture the PR URL from the output (e.g., `https://github.com/gioe/aiq/pull/540`).

12. **Update the task status and PR URL**:
    ```bash
    sqlite3 taskdb/tasks.db "UPDATE tasks SET github_pr = '<pr_url>', updated_at = datetime('now') WHERE id = <id>"
    ```

13. **Review loop - iterate until Claude approves**:
    After the PR is created, enter a review loop with the remote Claude reviewer. Continue until agreement is reached that the PR is ready to merge.

    ```
    ┌─► Poll for Claude's review
    │         │
    │         ▼
    │   Analyze review
    │         │
    │         ▼
    │   ┌─────────────┐
    │   │ Approved?   │───Yes──► Exit loop (ready to merge)
    │   └─────────────┘
    │         │ No
    │         ▼
    │   Address comments
    │         │
    │         ▼
    │   Push fixes
    │         │
    └─────────┘
    ```

    **Step 13a: Poll for Claude's review**

    Use the `/poll-claude-review` skill to wait for Claude's review:
    ```
    /poll-claude-review <pr_number>
    ```

    For subsequent reviews after pushing fixes, use follow-up mode:
    ```
    /poll-claude-review <pr_number> follow-up
    ```

    The skill handles polling, timeout, and returns the full review content.

    **Step 13b: Check if Claude approved**
    Parse the review to determine if Claude has approved the PR. Look for approval signals:
    - "LGTM" (Looks Good To Me)
    - "Approved"
    - "Ready to merge"
    - "No blocking issues"
    - No Category A (blocking) comments in the review

    If approved → Exit loop, proceed to step 14.
    If not approved → Continue to step 13c.

    **Step 13c: Address Claude's review comments**

    **Category A - Address Immediately (must fix in this PR):**
    - Security concerns (XSS, SQL injection, auth issues, secrets)
    - Bug reports (logic errors, null pointers, race conditions)
    - Breaking changes (API contract violations)
    - Test failures or missing tests for code introduced/modified in this PR
    - Performance issues
    - Type errors or missing error handling
    - Missing documentation for new public APIs, modules, or complex logic added in this PR
    - Refactoring of code introduced or modified in this PR (e.g., extract duplication you just created)
    - Error handling gaps in code you wrote or changed

    The bar is: if the reviewer is commenting on code this PR touches, fix it now.

    For each Category A comment:
    1. Read the relevant file(s)
    2. Make the code fix using Edit tool
    3. Commit: `[TASK-<id>] Address PR review: <brief description>`

    **Category B - Defer to backlog (cosmetic only):**
    - Pure style preferences (naming conventions, formatting) that don't affect correctness
    - Suggestions about pre-existing code NOT touched by this PR
    - "In the future, we might want to..." aspirational ideas
    - Improvements to unrelated modules the reviewer noticed in passing

    The bar is: only defer if the comment is about code this PR did NOT change, or is a purely cosmetic preference with no functional impact.

    For each Category B comment:
    1. **Check for duplicates first** using `/check-dupes`:
       ```bash
       python3 .claude/scripts/check_duplicates.py check "[Deferred] <brief description>" --domain <domain>
       ```
       - If exit code 1 (duplicates found): skip the INSERT and log which existing task covers it.
       - If exit code 0 (no duplicates): proceed to create the task.
    2. Create a task in the local SQLite database (with 60-day expiry):
       ```bash
       sqlite3 taskdb/tasks.db "INSERT INTO tasks (summary, description, status, priority, domain, created_at, updated_at, expires_at)
         VALUES ('[Deferred] <brief description>', 'Deferred from PR #<pr_number> review for TASK-<id>.\n\nOriginal comment: <comment text>\n\nReason deferred: <why this can wait>', 'To Do', 'Low', '<domain>', datetime('now'), datetime('now'), datetime('now', '+60 days'))"
       ```
    3. Document in `.github/DEFERRED_REVIEW_ITEMS.md`

    **Step 13d: Push fixes and loop back**
    ```bash
    git push origin feature/TASK-<id>-description
    ```
    Then use `/poll-claude-review <pr_number> follow-up` to wait for Claude's next review. Loop back to step 13b.

14. **PR approved - finalize and merge**:
    Once Claude approves, automatically perform ALL of these steps:

    **Step 14a: Create deferred tasks for any remaining Category B items**
    Category B items should be rare (only cosmetic style nits or comments about untouched code).
    If there are any, for each one:
    1. **Check for duplicates first** using `/check-dupes`:
       ```bash
       python3 .claude/scripts/check_duplicates.py check "[Deferred] <brief description>" --domain <domain>
       ```
       - If exit code 1 (duplicates found): skip the INSERT and log which existing task covers it.
       - If exit code 0 (no duplicates): proceed to create the task.
    2. Create the task (with 60-day expiry):
       ```bash
       sqlite3 taskdb/tasks.db "INSERT INTO tasks (summary, description, status, priority, domain, created_at, updated_at, expires_at)
         VALUES ('[Deferred] <brief description>', 'Deferred from PR #<pr_number> review for TASK-<id>.

Original comment: <comment text>

Reason deferred: <why this can wait>', 'To Do', 'Low', '<domain>', datetime('now'), datetime('now'), datetime('now', '+60 days'))"
       ```

    **Step 14b: Merge the PR**
    ```bash
    gh pr merge $PR_NUMBER --squash --delete-branch
    ```

    **Step 14c: Update task status to Done**
    ```bash
    sqlite3 taskdb/tasks.db "UPDATE tasks SET status = 'Done', closed_reason = 'completed', updated_at = datetime('now') WHERE id = <id>"
    ```

15. **End task metrics tracking**:
    ```bash
    ~/.claude/task-metrics.sh end
    ```

16. **Check for newly unblocked tasks**:
    ```bash
    sqlite3 -header -column taskdb/tasks.db "
    SELECT t.id, t.summary, t.priority
    FROM tasks t
    JOIN task_dependencies d ON t.id = d.task_id
    WHERE d.depends_on_id = <id> AND t.status = 'To Do'
    "
    ```

### Mark Task as Done

When called with `done <id>`:

```bash
sqlite3 taskdb/tasks.db "UPDATE tasks SET status = 'Done', closed_reason = 'completed', updated_at = datetime('now') WHERE id = <id>"
```

Then show newly unblocked tasks.

### View Task Details

When called with `view <id>`:

```bash
sqlite3 -header -column taskdb/tasks.db "SELECT * FROM tasks WHERE id = <id>"
```

### List Top N Ready Tasks

When called with `list <n>` or just a number:

```bash
sqlite3 -header -column taskdb/tasks.db "
SELECT t.id, t.summary, t.priority, t.domain, t.assignee
FROM tasks t
WHERE t.status = 'To Do'
  AND NOT EXISTS (
    SELECT 1 FROM task_dependencies d
    JOIN tasks blocker ON d.depends_on_id = blocker.id
    WHERE d.task_id = t.id AND blocker.status != 'Done'
  )
ORDER BY t.priority_score DESC, t.id
LIMIT <n>;
"
```

### Filter by Domain

When called with `domain <value>`:

Get next ready task for that domain only.

### Filter by Assignee

When called with `assignee <value>`:

Get next ready task for that assignee only.

### Show Blocked Tasks

When called with `blocked`:

```bash
sqlite3 -header -column taskdb/tasks.db "
SELECT t.id, t.summary, t.priority,
  (SELECT GROUP_CONCAT(d.depends_on_id) FROM task_dependencies d WHERE d.task_id = t.id) as blocked_by
FROM tasks t
WHERE t.status = 'To Do'
  AND EXISTS (
    SELECT 1 FROM task_dependencies d
    JOIN tasks blocker ON d.depends_on_id = blocker.id
    WHERE d.task_id = t.id AND blocker.status != 'Done'
  )
ORDER BY t.id
"
```

### Show In Progress Tasks

When called with `wip` or `in-progress`:

```bash
sqlite3 -header -column taskdb/tasks.db "SELECT id, summary, priority, domain, assignee, github_pr FROM tasks WHERE status = 'In Progress'"
```

### Preview Next Task (without starting)

When called with `preview`:

Show the next ready task but do NOT start working on it. Just display the task details and stop.

```bash
sqlite3 -header -column taskdb/tasks.db "
SELECT t.id, t.summary, t.priority, t.domain, t.assignee, t.description
FROM tasks t
WHERE t.status = 'To Do'
  AND NOT EXISTS (
    SELECT 1 FROM task_dependencies d
    JOIN tasks blocker ON d.depends_on_id = blocker.id
    WHERE d.task_id = t.id AND blocker.status != 'Done'
  )
ORDER BY t.priority_score DESC, t.id
LIMIT 1;
"
```

## Argument Parsing Summary

| Argument | Action |
|----------|--------|
| (none) | Get next ready task and automatically start working on it |
| `<id>` | Begin full workflow on task #id |
| `list <n>` | Show top N ready tasks |
| `done <id>` | Mark task as Done |
| `view <id>` | Show full task details |
| `domain <value>` | Filter next task by domain |
| `assignee <value>` | Filter next task by assignee |
| `blocked` | Show all blocked tasks |
| `wip` | Show all In Progress tasks |
| `preview` | Show next ready task without starting it |

## Canonical Values (Enforced by SQLite Triggers)

All inserts and updates are validated by triggers. Using non-canonical values will be rejected.

### Domain
`iOS`, `Backend`, `Question Service`, `Infrastructure`, `Docs`, `Data`, `Testing`, `Web`

WARNING: Do NOT use lowercase variants like `backend`, `ios`, `question-service`, or alternatives like `documentation`, `devops`. Always use the exact canonical values above.

### Task Type
`bug`, `feature`, `refactor`, `test`, `docs`, `infrastructure`

WARNING: Do NOT use variants like `bug_fix`, `Bug`, `refactoring`, `testing`, `documentation`, `deployment`, `enhancement`, `engineering`, `production`, `implementation`. Always use the exact canonical values above.

### Priority
`Highest`, `High`, `Medium`, `Low`, `Lowest`

### Status
`To Do`, `In Progress`, `Done`

### Closed Reason (set when status = Done)
`completed`, `expired`, `wont_do`, `duplicate`

Always set `closed_reason` when marking a task Done. Use `completed` for work that was implemented, `expired` for auto-closed deferred tasks, `wont_do` for obsolete/cancelled tasks, `duplicate` for redundant tasks.

## Important Guidelines

- Write tests for all tasks unless the task is untestable
- Ask clarifying questions if task requirements are ambiguous
- Use the TodoWrite tool to track progress within the task
- Make sure work is delegated to the correct subagent based on the assignee field
- Mark complete only when fully implemented and tested
- The widget at `~/.claude/widget.py` displays real-time task metrics while in progress
