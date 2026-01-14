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
sqlite3 -header -column tasks.db "
SELECT t.id, t.summary, t.priority, t.domain, t.assignee, t.description
FROM tasks t
WHERE t.status = 'To Do'
  AND NOT EXISTS (
    SELECT 1 FROM task_dependencies d
    JOIN tasks blocker ON d.depends_on_id = blocker.id
    WHERE d.task_id = t.id AND blocker.status != 'Done'
  )
ORDER BY
  CASE t.priority
    WHEN 'Highest' THEN 1
    WHEN 'High' THEN 2
    WHEN 'Medium' THEN 3
    WHEN 'Low' THEN 4
    ELSE 5
  END,
  t.id
LIMIT 1;
"
```

After finding the next ready task, **immediately proceed to the "Begin Work on a Task" workflow** using the retrieved task ID. Do not wait for user confirmation.

### Begin Work on a Task (with task ID argument)

When called with a task ID (e.g., `/next-task 6`), begin the full development workflow:

**Follow these steps IN ORDER:**

1. **Fetch the task** from the local database:
   ```bash
   sqlite3 -header -column tasks.db "SELECT * FROM tasks WHERE id = <id>"
   ```

2. **Start task metrics tracking**:
   ```bash
   ~/.claude/task-metrics.sh start "TASK-<id>" "<task_summary>"
   ```

3. **Update the task status** to In Progress:
   ```bash
   sqlite3 tasks.db "UPDATE tasks SET status = 'In Progress', updated_at = datetime('now') WHERE id = <id>"
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

7. **Delegate the work** to the chosen subagent(s).

8. **Create atomic commits** as you complete logical units of work.
   - All commits should be on the feature branch, NOT main.

9. **Review the code locally** before considering the work complete.
   - Use the appropriate code review agent for the domain.

10. **Push the branch and create a PR**:
    ```bash
    git push -u origin feature/TASK-<id>-description
    gh pr create --title "[TASK-<id>] Brief task description" --body "..."
    ```

11. **Update the task status** to In Review:
    ```bash
    sqlite3 tasks.db "UPDATE tasks SET status = 'In Review', updated_at = datetime('now') WHERE id = <id>"
    ```

12. **End task metrics tracking**:
    ```bash
    ~/.claude/task-metrics.sh end
    ```

13. **Check for newly unblocked tasks**:
    ```bash
    sqlite3 -header -column tasks.db "
    SELECT t.id, t.summary, t.priority
    FROM tasks t
    JOIN task_dependencies d ON t.id = d.task_id
    WHERE d.depends_on_id = <id> AND t.status = 'To Do'
    "
    ```

### Mark Task as Done

When called with `done <id>`:

```bash
sqlite3 tasks.db "UPDATE tasks SET status = 'Done', updated_at = datetime('now') WHERE id = <id>"
```

Then show newly unblocked tasks.

### View Task Details

When called with `view <id>`:

```bash
sqlite3 -header -column tasks.db "SELECT * FROM tasks WHERE id = <id>"
```

### List Top N Ready Tasks

When called with `list <n>` or just a number:

```bash
sqlite3 -header -column tasks.db "
SELECT t.id, t.summary, t.priority, t.domain, t.assignee
FROM tasks t
WHERE t.status = 'To Do'
  AND NOT EXISTS (
    SELECT 1 FROM task_dependencies d
    JOIN tasks blocker ON d.depends_on_id = blocker.id
    WHERE d.task_id = t.id AND blocker.status != 'Done'
  )
ORDER BY
  CASE t.priority
    WHEN 'Highest' THEN 1
    WHEN 'High' THEN 2
    WHEN 'Medium' THEN 3
    WHEN 'Low' THEN 4
    ELSE 5
  END,
  t.id
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
sqlite3 -header -column tasks.db "
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
sqlite3 -header -column tasks.db "SELECT id, summary, priority, domain, assignee FROM tasks WHERE status = 'In Progress'"
```

### Preview Next Task (without starting)

When called with `preview`:

Show the next ready task but do NOT start working on it. Just display the task details and stop.

```bash
sqlite3 -header -column tasks.db "
SELECT t.id, t.summary, t.priority, t.domain, t.assignee, t.description
FROM tasks t
WHERE t.status = 'To Do'
  AND NOT EXISTS (
    SELECT 1 FROM task_dependencies d
    JOIN tasks blocker ON d.depends_on_id = blocker.id
    WHERE d.task_id = t.id AND blocker.status != 'Done'
  )
ORDER BY
  CASE t.priority
    WHEN 'Highest' THEN 1
    WHEN 'High' THEN 2
    WHEN 'Medium' THEN 3
    WHEN 'Low' THEN 4
    ELSE 5
  END,
  t.id
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

## Important Guidelines

- Write tests for all tasks unless the task is untestable
- Ask clarifying questions if task requirements are ambiguous
- Use the TodoWrite tool to track progress within the task
- Make sure work is delegated to the correct subagent based on the assignee field
- Mark complete only when fully implemented and tested
- The widget at `~/.claude/widget.py` displays real-time task metrics while in progress
