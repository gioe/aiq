---
description: Begin work on a specific task from a plan file
args:
  - name: task_id
    description: Task identifier to work on (e.g., P1-001, P8-010)
    required: true
---

You are about to begin work on a specific task in Jira. You are to use the Jira CLI in order to interact with Jira, never the Jira MCP.

**Task ID**: {{task_id}}

Follow these steps IN ORDER:

1. **Fetch the task** from Jira

2. **Start task metrics tracking** by running:
   ```bash
   ~/.claude/task-metrics.sh start "{{task_id}}" "<task_title_from_jira>"
   ```
   Replace `<task_title_from_jira>` with the actual task title you fetched.

3. **Update the Jira ticket status** to In Progress

4. **Extract task details** including:
   - Description
   - Acceptance Criteria

5. **🚨 MANDATORY: Create a new git branch IMMEDIATELY 🚨**
   - **DO NOT SKIP THIS STEP - CREATE THE BRANCH BEFORE ANY CODE CHANGES**
   - Format: `feature/{{task_id}}-brief-description` (e.g., `feature/P8-010-add-feature`)
   - Commands to run RIGHT NOW:
     ```bash
     git checkout main && git pull origin main
     git checkout -b feature/{{task_id}}-brief-description
     ```

6. **Use the technical-product-manager subagent** to determine the subagent or subagents most suited to do the task based on the task details.

7. **Delegate the work** to the chosen subagent or subagents.

8. **Create atomic commits** as you complete logical units of work
   - All commits should be on the feature branch, NOT main

9. **Review the code locally** before considering the work complete. This review can be done by any subagent, although should be done by those with the most domain review expertise.

10. Once complete **push the branch to GitHub** and create a PR:
    - Push: `git push -u origin feature/{{task_id}}-description`
    - Create PR: `gh pr create` with title format `[{{task_id}}] Brief task description`
    - The PR should merge the feature branch into main

11. **Update the Jira ticket status** to In Review

12. **End task metrics tracking** by running:
    ```bash
    ~/.claude/task-metrics.sh end
    ```
    This will save the task metrics (duration, cost, tokens) to `~/.claude/task_history.json` and display a summary.

Important guidelines:
- Write tests for all tasks unless the task is untestable
- Combine tasks from the plan if they are better done together
- Ask clarifying questions if task requirements are ambiguous
- Mark the task as in_progress in your todo list before starting
- Make sure the work is delegated to the correct subagent based on the assignee(s)
- Mark complete only when fully implemented and tested
- The widget at `~/.claude/widget.py` will display real-time task metrics while the task is in progress

Begin by fetching {{task_id}} from Jira.
