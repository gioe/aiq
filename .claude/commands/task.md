---
description: Begin work on a specific task from a plan file
args:
  - name: task_id
    description: Task identifier to work on (e.g., P1-001, P8-010)
    required: true
---

You are about to begin work on a specific task from a plan file.

**Task ID**: {{task_id}}

Follow these steps IN ORDER:

1. **Read the plan file** in the docs/plans/in-progress directory.
2. **Locate the specific task** with the identifier {{task_id}}
3. **Extract task details** including:
   - Description
   - Files
   - Assignee(s)
   - Acceptance Criteria

4. **🚨 MANDATORY: Create a new git branch IMMEDIATELY 🚨**
   - **DO NOT SKIP THIS STEP - CREATE THE BRANCH BEFORE ANY CODE CHANGES**
   - Format: `feature/{{task_id}}-brief-description` (e.g., `feature/P8-010-add-feature`)
   - Commands to run RIGHT NOW:
     ```bash
     git checkout main && git pull origin main
     git checkout -b feature/{{task_id}}-brief-description
     ```

5. **Use TodoWrite and the Assignee(s)** to create a focused todo list for implementing this specific task

6. **Begin implementation** following the task requirements
   - **REMINDER: Verify you're still on the feature branch before making changes**
   - Run `git branch --show-current` if unsure

7. **Create atomic commits** as you complete logical units of work
   - All commits should be on the feature branch, NOT main

9. **Update the plan file** to mark the task as complete when done (change `[ ]` to `[x]`)
   - Add summary content to the task. Summary content should include
	- Total tokens spent on task
	- Total time spent on task
   - This should be your final commit on the feature branch

10. **Push the branch to GitHub** and create a PR:
   - Push: `git push -u origin feature/{{task_id}}-description`
   - Create PR: `gh pr create` with title format `[{{task_id}}] Brief task description`
   - The PR should merge the feature branch into main

Important guidelines:
- Write tests for all tasks unless the task is untestable
- Combine tasks from the plan if they are better done together
- Ask clarifying questions if task requirements are ambiguous
- Mark the task as in_progress in your todo list before starting
- Make sure the work is delegated to the correct subagent based on the assignee(s)
- Mark complete only when fully implemented and tested

Begin by reading the plan file and locating task {{task_id}}.
