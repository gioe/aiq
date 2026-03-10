---
name: xcode-group-manager
description: Manage Xcode group hierarchies in the AIQ project. Use when the target group for new Swift files does not yet exist in the Xcode project — run this before /xcode-file-manager to create the needed group path.
allowed-tools: Bash, Read
---

# Xcode Group Manager Skill

This skill creates or removes Xcode group hierarchies in the AIQ project using the `xcodeproj` Ruby gem.

## When to Use This Skill vs /xcode-file-manager

| Scenario | Skill to use |
|----------|-------------|
| Group already exists, adding files to it | `/xcode-file-manager` only |
| Group does **not** exist yet | `/xcode-group-manager` first, then `/xcode-file-manager` |
| Removing an empty group after deleting its files | `/xcode-group-manager` |
| Removing files (with or without deleting from disk) | `/xcode-file-manager` only |

**Why this exists:** `/xcode-file-manager`'s `add_files_to_xcode.rb` requires every group in the path to already exist. If a group is missing, the script emits `[ERROR] Group not found in project: …` and falls back to placing the file at the wrong level under the root group — causing "Build input files cannot be found" build failures. Use this skill to create the group hierarchy first.

## Creating a Group Path

```bash
cd ios && ruby scripts/manage_xcode_groups.rb --create-group <group_path>
```

**Examples:**

```bash
# Create a nested feature group (all intermediate groups are created as needed)
cd ios && ruby scripts/manage_xcode_groups.rb --create-group AIQ/Features/Auth/Views
cd ios && ruby scripts/manage_xcode_groups.rb --create-group AIQ/Features/Auth/ViewModels
cd ios && ruby scripts/manage_xcode_groups.rb --create-group AIQ/Features/Onboarding/Views

# Then add files using /xcode-file-manager
cd ios && ruby scripts/add_files_to_xcode.rb AIQ/Features/Auth/Views/LoginView.swift
```

- All missing intermediate groups are created automatically.
- Already-existing groups are left untouched (idempotent).

## Removing an Empty Group

```bash
cd ios && ruby scripts/manage_xcode_groups.rb --remove-group <group_path>
```

**Examples:**

```bash
# Remove a leaf group after its files have been deleted
cd ios && ruby scripts/manage_xcode_groups.rb --remove-group AIQ/Features/Auth/Views
```

- Fails with an error if the group still has children (files or subgroups).
- No-ops silently if the group no longer exists.

## Typical Workflow: Adding Files to a New Feature Module

```bash
# 1. Create group hierarchy
cd ios && ruby scripts/manage_xcode_groups.rb --create-group AIQ/Features/Auth/Views
cd ios && ruby scripts/manage_xcode_groups.rb --create-group AIQ/Features/Auth/ViewModels

# 2. Create the Swift files on disk (Write tool or ios-engineer agent)

# 3. Add files to the Xcode project and build target
cd ios && ruby scripts/add_files_to_xcode.rb \
  AIQ/Features/Auth/Views/LoginView.swift \
  AIQ/Features/Auth/ViewModels/LoginViewModel.swift
```

## Prerequisites

The `xcodeproj` gem must be installed:

```bash
gem install xcodeproj
```

## Troubleshooting

- **`[ERROR] Group not found`** when running `add_files_to_xcode.rb`: The group doesn't exist — run `manage_xcode_groups.rb --create-group` first.
- **`[ERROR] Group is not empty`** when removing: Remove or move all files from the group first using `/xcode-file-manager`.
- **Build failure "Build input files cannot be found"**: A file was added to the wrong group (root instead of the intended nested group). Remove the misplaced reference with `/xcode-file-manager --keep-files`, create the correct group with this skill, then re-add the file.
