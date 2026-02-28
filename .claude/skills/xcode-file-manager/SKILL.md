---
name: xcode-file-manager
description: Add or remove Swift files in the AIQ Xcode project. Use when creating new Swift files (views, view models, services, models, tests) that need to be added to the Xcode project and build targets, or when dead files need to be removed.
allowed-tools: Bash, Read, Write, Glob
---

# Xcode File Manager Skill

This skill handles adding and removing Swift files in the AIQ Xcode project using the `xcodeproj` Ruby gem.

## When to Use This Skill

Use this skill whenever you:
- Create a new Swift file in the `ios/AIQ/` directory
- Create a new test file in the `ios/AIQTests/` directory
- Need to add existing Swift files to the Xcode project
- Need to remove dead or deleted Swift files from the Xcode project

## How to Add Files

### Using the Existing Script

There is a reusable Ruby script at `ios/scripts/add_files_to_xcode.rb`. Use it like this:

```bash
cd ios && ruby scripts/add_files_to_xcode.rb <relative_path_to_file>
```

**Examples:**

```bash
# Add a single file
cd ios && ruby scripts/add_files_to_xcode.rb AIQ/ViewModels/NewViewModel.swift

# Add multiple files
cd ios && ruby scripts/add_files_to_xcode.rb AIQ/Views/NewView.swift AIQ/ViewModels/NewViewModel.swift

# Add a test file (automatically added to AIQTests target)
cd ios && ruby scripts/add_files_to_xcode.rb AIQTests/NewTests.swift
```

### File Path Convention

- Paths must be relative to the `ios/` directory
- The script uses the directory structure to find the correct Xcode group
- Files in `AIQ/` are added to the main `AIQ` target
- Files in `AIQTests/` are added to the `AIQTests` target

### Common Directories

| Directory | Purpose | Target |
|-----------|---------|--------|
| `AIQ/Views/` | SwiftUI views | AIQ |
| `AIQ/ViewModels/` | View models | AIQ |
| `AIQ/Models/` | Data models | AIQ |
| `AIQ/Services/` | API and business services | AIQ |
| `AIQ/Utilities/` | Helper utilities | AIQ |
| `AIQTests/` | Unit tests | AIQTests |

### Creating New Groups

If you need to add a file to a group that doesn't exist in the Xcode project, you must first create the group in Xcode or modify the script to create groups dynamically.

## How to Remove Files

There is a reusable Ruby script at `ios/scripts/remove_files_from_xcode.rb`. Use it like this:

```bash
cd ios && ruby scripts/remove_files_from_xcode.rb <relative_path_to_file>
```

**Examples:**

```bash
# Remove a single file (deletes from project and disk)
cd ios && ruby scripts/remove_files_from_xcode.rb AIQ/ViewModels/OldViewModel.swift

# Remove multiple files
cd ios && ruby scripts/remove_files_from_xcode.rb AIQ/Views/OldView.swift AIQ/ViewModels/OldViewModel.swift

# Remove from project only, keep file on disk
cd ios && ruby scripts/remove_files_from_xcode.rb --keep-files AIQ/openapi.json
```

The script:
- Removes the file reference from `project.pbxproj`
- Removes all build phase entries (Sources, Resources, etc.) across every target
- Deletes the file from disk (unless `--keep-files` is passed)

> **Warning:** Disk deletion is permanent. Ensure the file is committed to git before running without `--keep-files`.

> **Note:** The remove script does **not** stage any changes in git. After running the script, you must stage changes manually before committing:
> - Without `--keep-files`: `git add <path/to/file> ios/AIQ.xcodeproj/project.pbxproj`
> - With `--keep-files`: `git add ios/AIQ.xcodeproj/project.pbxproj`

### Options

| Flag | Effect |
|------|--------|
| *(none)* | Remove from project and delete from disk |
| `--keep-files` | Remove from project only; file is not deleted |

## Prerequisites

The `xcodeproj` gem must be installed:

```bash
gem install xcodeproj
```

## Troubleshooting

- **"Group not found"**: The directory structure in the file path must match the group structure in the Xcode project
- **"File already in project"**: The file reference already exists; the script will skip it unless the path is incorrect
- **"File not found"**: The Swift file must exist on disk before running the add script
- **"File not found in project"**: The file reference doesn't exist in the project; nothing to remove
