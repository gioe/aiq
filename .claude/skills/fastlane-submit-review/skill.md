---
name: fastlane-submit-review
description: Submit the current App Store Connect build for App Store review with metadata and screenshots. Does not build or upload a new binary.
allowed-tools: Bash, Read
---

# Fastlane Submit Review Skill

This skill runs the fastlane `submit_review` lane to submit the app for App Store review.

## What it does

- Uploads latest metadata and screenshots
- Submits the current build for App Store review
- Sets IDFA usage to false

**Important:** This submits the app for Apple review. Always confirm with the user before running.

## Usage

```bash
cd "$(git rev-parse --show-toplevel)/ios" && export PATH="/opt/homebrew/opt/ruby/bin:/opt/homebrew/lib/ruby/gems/4.0.0/bin:$PATH" && bundle exec fastlane submit_review 2>&1
```

**Timeout:** Use a 300000ms timeout.

## Prerequisites

- A binary must already be uploaded and processed on App Store Connect
- App Privacy section must be completed in App Store Connect
- All required screenshots must be uploaded
