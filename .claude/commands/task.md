---
description: Begin work on a specific task from a plan file
args:
  - name: plan_file
    description: Path to the plan markdown file (e.g., PLAN.md, IN_PROGRESS_TEST_PLAN.md)
    required: true
  - name: task_id
    description: Task identifier to work on (e.g., P1-001, P8-010)
    required: true
---

You are about to begin work on a specific task from a plan file.

**Plan File**: {{plan_file}}
**Task ID**: {{task_id}}

Follow these steps:

1. **Read the plan file** at the specified path to understand the full context
2. **Locate the specific task** with the identifier {{task_id}}
3. **Extract task details** including:
   - Task description
   - Phase context
   - Dependencies or prerequisites mentioned
   - Any technical notes relevant to this task
4. **Create a new git branch** for this task:
   - Format: `feature/{{task_id}}-brief-description` (e.g., `feature/P8-010-brief-description`)
   - ALWAYS start from latest main: `git checkout main && git pull origin main`
   - Then create feature branch: `git checkout -b feature/{{task_id}}-description`
5. **Use TodoWrite** to create a focused todo list for implementing this specific task
6. **Begin implementation** following the task requirements
7. **Create atomic commits** as you complete logical units of work
8. **Update the plan file** to mark the task as complete when done (change `[ ]` to `[x]`)
9. **Push the branch to GitHub** and create a PR:
   - Push: `git push -u origin feature/{{task_id}}-description`
   - Create PR: `gh pr create` with title format `[{{task_id}}] Brief task description`

Important guidelines:
- Read related tasks in the same phase for context
- Follow existing code patterns and architecture
- Write tests if specified in the task
- Ask clarifying questions if task requirements are ambiguous
- Mark the task as in_progress in your todo list before starting
- Mark complete only when fully implemented and tested

Begin by reading the plan file and locating task {{task_id}}.
