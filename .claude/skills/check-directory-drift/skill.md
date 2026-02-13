---
name: check-directory-drift
description: Compare a directory's actual structure against its README tree block and fix any drift
allowed-tools: Bash, Read, Edit
---

# Check Directory Drift

Compares the actual directory layout against the ASCII tree block in a directory's README.md. Detects new directories, removed directories, and broken markdown links. Automatically fixes the tree block and any broken links.

## Arguments

The first argument is the directory to check. Defaults to the repo root (`.`) if omitted.

## Steps

### Step 1: Run the sync script

```bash
python3 scripts/sync_readme_structure.py {{directory}} --fix
```

If the directory argument is empty or `.`, omit it to default to the repo root.

### Step 2: Report results

- If the script exits 0 and says "in sync", report that to the user — no changes needed.
- If the script updated the tree block, show the user what changed (new dirs added, removed dirs dropped).
- If broken links were reported, fix them:
  1. For each broken link, search for the file elsewhere in the repo.
  2. If found, update the link path in the README.
  3. If not found, tell the user the link target doesn't exist and ask if they want to remove it.

### Step 3: Verify

Run the script once more without `--fix` to confirm everything is clean:

```bash
python3 scripts/sync_readme_structure.py {{directory}}
```

If it still reports issues, address them and repeat.

### Step 4: Handle directories without tree blocks

If the script reports "No directory-tree code block found", tell the user that the README in that directory doesn't have a directory structure tree. Ask if they'd like you to generate one.
