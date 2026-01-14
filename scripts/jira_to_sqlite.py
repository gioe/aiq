#!/usr/bin/env python3
"""Sync Jira issues to SQLite database."""

import sqlite3
import subprocess
import json

DB_PATH = "tasks.db"
PROJECT = "BTS"
BATCH_SIZE = 100  # Jira CLI max per request

SCHEMA = """
  CREATE TABLE IF NOT EXISTS tasks (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      jira_key TEXT UNIQUE,
      summary TEXT NOT NULL,
      description TEXT,
      status TEXT,                       -- Done, In Progress, To Do
      priority TEXT,                     -- Low, Medium, High
      domain TEXT,                       -- iOS, Android, Web, Backend, Data
      assignee TEXT,
      created_at TEXT,
      updated_at TEXT
  );
"""


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def adf_to_text(adf: dict | None) -> str | None:
    """Convert Atlassian Document Format to plain text."""
    if not adf:
        return None

    text_parts = []

    def extract(node):
        if isinstance(node, dict):
            if node.get("type") == "text":
                text_parts.append(node.get("text", ""))
            elif node.get("type") == "hardBreak":
                text_parts.append("\n")
            for child in node.get("content", []):
                extract(child)
        elif isinstance(node, list):
            for item in node:
                extract(item)

    extract(adf)
    return "".join(text_parts).strip() or None


def parse_issue(data: dict) -> dict:
    """Parse a Jira issue dict into our schema."""
    fields = data["fields"]

    # Extract first component as domain
    components = fields.get("components", [])
    domain = components[0]["name"] if components else None

    # Extract assignee display name
    assignee = fields["assignee"]["displayName"] if fields.get("assignee") else None

    return {
        "jira_key": data["key"],
        "summary": fields["summary"],
        "description": adf_to_text(fields.get("description")),
        "status": fields["status"]["name"],
        "priority": fields["priority"]["name"] if fields.get("priority") else None,
        "domain": domain,
        "assignee": assignee,
        "created_at": fields.get("created"),
        "updated_at": fields.get("updated"),
    }


def fetch_issues_batch(jql: str) -> list[dict]:
    """Fetch a batch of issues using JQL."""
    result = subprocess.run(
        ["jira", "issue", "list", "-q", jql, "--raw"],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        raise Exception(f"Failed to list issues: {result.stderr}")

    issues = json.loads(result.stdout)
    return [parse_issue(issue) for issue in issues]


def fetch_all_issues() -> list[dict]:
    """Fetch all issues using Jira CLI with pagination via JQL key ranges."""
    all_issues = []
    max_key = None

    print(f"Fetching issues from project {PROJECT}...")

    while True:
        # Build JQL query with key range for pagination
        # Note: ORDER BY is separate from JQL in some Jira CLIs
        if max_key:
            jql = f"project = {PROJECT} AND key < {max_key}"
        else:
            jql = f"project = {PROJECT}"

        batch = fetch_issues_batch(jql)

        if not batch:
            break

        all_issues.extend(batch)
        print(f"  Fetched {len(batch)} issues (total: {len(all_issues)})")

        # Get the lowest key from this batch for next iteration
        # Keys are like "BTS-123", extract the number
        keys = [issue["jira_key"] for issue in batch]
        min_key_num = min(int(k.split("-")[1]) for k in keys)
        max_key = f"{PROJECT}-{min_key_num}"

        # If we got fewer than max, we're done
        if len(batch) < BATCH_SIZE:
            break

    return all_issues


def upsert_issue(conn: sqlite3.Connection, issue: dict):
    """Insert or update an issue."""
    conn.execute("""
        INSERT INTO tasks
            (jira_key, summary, description, status, priority, domain, assignee, created_at, updated_at)
        VALUES
            (:jira_key, :summary, :description, :status, :priority, :domain, :assignee, :created_at, :updated_at)
        ON CONFLICT(jira_key) DO UPDATE SET
            summary = excluded.summary,
            description = excluded.description,
            status = excluded.status,
            priority = excluded.priority,
            domain = excluded.domain,
            assignee = excluded.assignee,
            created_at = excluded.created_at,
            updated_at = excluded.updated_at
    """, issue)


def main():
    conn = init_db()
    issues = fetch_all_issues()

    for issue in issues:
        upsert_issue(conn, issue)
    conn.commit()

    print(f"Synced {len(issues)} issues to {DB_PATH}")


if __name__ == "__main__":
    main()
