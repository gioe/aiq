#!/usr/bin/env python3
"""Assign tasks to agents based on description content and domain."""

import argparse
import re
import sqlite3
from pathlib import Path

from db_path import DB_PATH
AGENTS_DIR = Path(".claude/agents")

# Agent definitions with their specializations
# Order matters: more specific patterns should come first
AGENT_RULES = [
    {
        "agent": "statistical-analysis-scientist",
        "keywords": [
            r"\bstatistic", r"\bmath", r"\bformula", r"\bcalculat",
            r"\baverage", r"\bmean\b", r"\bmedian\b", r"\bpercentile",
            r"\bcorrelation", r"\bregression", r"\bprobability",
            r"\bscoring\s+algorithm", r"\breliability\s+metric",
            r"\bCronbach", r"\bpsychometric"
        ],
        "domains": [],
    },
    {
        "agent": "database-engineer",
        "keywords": [
            r"\bdatabase", r"\bSQL\b", r"\bquery", r"\bschema",
            r"\bmigration", r"\bindex", r"\bSQLAlchemy", r"\bAlembic",
            r"\btable\b", r"\bPostgreSQL", r"\bSQLite"
        ],
        "domains": ["Data"],
    },
    {
        "agent": "ios-engineer",
        "keywords": [
            r"\bSwiftUI\b", r"\bSwift\b", r"\bViewModel\b", r"\bView\b",
            r"\bUIKit\b", r"\biOS\b", r"\bXcode\b", r"\bObservable",
            r"\b@State\b", r"\b@Published\b", r"\b@MainActor\b",
            r"\bnavigation", r"\bAppRouter", r"\bBaseViewModel",
            r"\bUserDefaults\b", r"\bNetworkMonitor", r"\bOfflineOperation",
            r"\bdashboard\b", r"\bonboarding\b", r"\bMainTabView",
            r"\bTests?\b.*swift", r"swift.*\bTests?\b",
            r"\bXCT", r"\b\.swift\b",
            r"\bhaptic", r"\bkeyboard\s+shortcut", r"\biPad\b"
        ],
        "domains": ["iOS"],
    },
    {
        "agent": "fastapi-architect",
        "keywords": [
            r"\bAPI\b", r"\bendpoint", r"\bFastAPI", r"\bPydantic",
            r"\brouter", r"\bHTTP", r"\bREST", r"\bauth",
            r"\bbackend\b", r"\bservice\b", r"\btoken"
        ],
        "domains": ["Backend", "Web"],
    },
    {
        "agent": "python-code-guardian",
        "keywords": [
            r"\bPython\b", r"\brefactor", r"\berror\s+handling",
            r"\bexception", r"\blogging", r"\bbackground\s+job",
            r"\blong-running", r"\breliability"
        ],
        "domains": [],
    },
    {
        "agent": "technical-product-manager",
        "keywords": [
            r"\bfeature\b", r"\brequirement", r"\bproduct\b",
            r"\bprioritiz", r"\broadmap", r"\buser\s+story",
            r"\bacceptance\s+criteria", r"\bspec"
        ],
        "domains": [],
    },
    {
        "agent": "project-code-reviewer",
        "keywords": [
            r"\breview", r"\bcode\s+quality", r"\bstandards",
            r"\bbest\s+practice", r"\bpattern"
        ],
        "domains": [],
    },
]

# Default agents by domain when no keyword matches
DOMAIN_DEFAULTS = {
    "iOS": "ios-engineer",
    "Backend": "fastapi-architect",
    "Web": "fastapi-architect",
    "Data": "database-engineer",
    "Android": None,  # No Android agent yet
}


def get_connection() -> sqlite3.Connection:
    """Get database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_available_agents() -> set[str]:
    """Get list of available agents from the agents directory."""
    if not AGENTS_DIR.exists():
        return set()
    return {f.stem for f in AGENTS_DIR.glob("*.md")}


def determine_agent(task: sqlite3.Row, available_agents: set[str]) -> str | None:
    """Determine the best agent for a task based on content and domain."""
    summary = task["summary"] or ""
    description = task["description"] or ""
    domain = task["domain"]

    # Combine summary and description for keyword matching
    content = f"{summary} {description}".lower()

    # Try to match based on keywords
    for rule in AGENT_RULES:
        agent = rule["agent"]

        # Skip if agent doesn't exist
        if agent not in available_agents:
            continue

        # Check domain match first (if domains are specified)
        if rule["domains"] and domain in rule["domains"]:
            return agent

        # Check keyword matches
        for pattern in rule["keywords"]:
            if re.search(pattern, content, re.IGNORECASE):
                return agent

    # Fall back to domain default
    if domain and domain in DOMAIN_DEFAULTS:
        default_agent = DOMAIN_DEFAULTS[domain]
        if default_agent and default_agent in available_agents:
            return default_agent

    return None


def assign_tasks(dry_run: bool = False, force: bool = False):
    """Assign agents to tasks based on their content."""
    conn = get_connection()
    available_agents = get_available_agents()

    if not available_agents:
        print(f"Error: No agents found in {AGENTS_DIR}")
        return

    print(f"Available agents: {', '.join(sorted(available_agents))}")
    print()

    # Get tasks to process
    if force:
        tasks = conn.execute(
            "SELECT id, summary, description, domain, assignee FROM tasks WHERE status <> 'Done' ORDER BY id"
        ).fetchall()
    else:
        tasks = conn.execute(
            "SELECT id, summary, description, domain, assignee FROM tasks WHERE status <> 'Done' AND assignee IS NULL ORDER BY id"
        ).fetchall()

    if not tasks:
        print("No unassigned tasks found")
        return

    assignments = []
    unmatched = []

    for task in tasks:
        agent = determine_agent(task, available_agents)
        if agent:
            assignments.append((task["id"], task["summary"], agent, task["assignee"]))
        else:
            unmatched.append((task["id"], task["summary"], task["domain"]))

    # Print assignments
    print("=" * 80)
    print("TASK ASSIGNMENTS")
    print("=" * 80)

    if assignments:
        print(f"\n{'ID':<6} {'Agent':<30} {'Summary'}")
        print("-" * 80)
        for task_id, summary, agent, old_assignee in assignments:
            change_marker = f" (was: {old_assignee})" if old_assignee else ""
            print(f"{task_id:<6} {agent:<30} {summary[:40]}{change_marker}")

    if unmatched:
        print(f"\n\nUNMATCHED TASKS ({len(unmatched)})")
        print("-" * 80)
        for task_id, summary, domain in unmatched:
            print(f"{task_id:<6} [domain: {domain or 'None'}] {summary[:50]}")

    # Apply assignments
    if dry_run:
        print(f"\n[DRY RUN] Would assign {len(assignments)} tasks")
    else:
        for task_id, summary, agent, _ in assignments:
            conn.execute(
                "UPDATE tasks SET assignee = ? WHERE id = ?",
                (agent, task_id)
            )
        conn.commit()
        print(f"\nAssigned {len(assignments)} tasks")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    agent_counts = {}
    for _, _, agent, _ in assignments:
        agent_counts[agent] = agent_counts.get(agent, 0) + 1

    for agent, count in sorted(agent_counts.items(), key=lambda x: -x[1]):
        print(f"  {agent}: {count} tasks")

    if unmatched:
        print(f"  (unmatched): {len(unmatched)} tasks")

    conn.close()


def show_assignments():
    """Show current task assignments."""
    conn = get_connection()

    tasks = conn.execute("""
        SELECT id, summary, domain, assignee, status
        FROM tasks
        ORDER BY assignee, id
    """).fetchall()

    print("Current Task Assignments")
    print("=" * 90)
    print(f"{'ID':<6} {'Status':<12} {'Assignee':<30} {'Summary'}")
    print("-" * 90)

    current_assignee = None
    for task in tasks:
        if task["assignee"] != current_assignee:
            current_assignee = task["assignee"]
            print()  # Blank line between assignees

        assignee = task["assignee"] or "(unassigned)"
        print(f"{task['id']:<6} {task['status']:<12} {assignee:<30} {task['summary'][:35]}")

    conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Assign tasks to agents based on description content",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s assign              # Assign unassigned tasks
  %(prog)s assign --dry-run    # Preview assignments without applying
  %(prog)s assign --force      # Reassign all tasks (even if already assigned)
  %(prog)s show                # Show current assignments
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # assign command
    assign_parser = subparsers.add_parser("assign", help="Assign agents to tasks")
    assign_parser.add_argument("--dry-run", "-n", action="store_true",
                               help="Preview assignments without applying")
    assign_parser.add_argument("--force", "-f", action="store_true",
                               help="Reassign all tasks, even if already assigned")

    # show command
    subparsers.add_parser("show", help="Show current assignments")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == "assign":
        assign_tasks(dry_run=args.dry_run, force=args.force)
    elif args.command == "show":
        show_assignments()


if __name__ == "__main__":
    main()
