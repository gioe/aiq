# iOS Scripts

Utility scripts for working with the iOS project.

## add_files_to_xcode.rb

Adds Swift files to the Xcode project automatically.

**Usage:**
```bash
cd ios
ruby scripts/add_files_to_xcode.rb <file_path1> <file_path2> ...
```

**Example:**
```bash
# Add a single file
ruby scripts/add_files_to_xcode.rb AIQ/ViewModels/MyViewModel.swift

# Add multiple files
ruby scripts/add_files_to_xcode.rb \
  AIQ/ViewModels/MyViewModel.swift \
  AIQ/Views/MyView.swift
```

**Requirements:**
- Ruby with xcodeproj gem installed: `gem install xcodeproj`

**Notes:**
- File paths are relative to the `ios/` directory
- The script will find the appropriate group in the Xcode project based on the file path
- Files are automatically added to the main app target
- The script will skip files that are already in the project

## test_rtl.sh

Interactive helper script for testing the app in RTL (Right-to-Left) mode.

**Usage:**
```bash
cd ios
./scripts/test_rtl.sh
```

**Features:**
- Guides you through enabling RTL launch arguments
- Builds the project for testing
- Opens RTL testing documentation
- Opens the project in Xcode

**What it helps with:**
- Testing with Arabic/Hebrew layouts
- Verifying RTL text direction
- Ensuring proper layout mirroring

**See also:**
- [RTL Testing Guide](../docs/RTL_TESTING_GUIDE.md) - Comprehensive RTL testing instructions
- [Coding Standards - RTL Section](../docs/CODING_STANDARDS.md#rtl-right-to-left-support) - RTL coding guidelines
