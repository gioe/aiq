---
name: fastlane-release
description: Full App Store release pipeline — generates release notes, captures screenshots, frames them, bumps build, builds IPA, uploads to TestFlight, and submits for App Store review.
allowed-tools: Bash, Read
---

# Fastlane Release Skill

This skill runs the fastlane `release` lane for a full App Store submission.

## What it does

1. Generates release notes from commits since the last tag (writes `release_notes.txt` and `WhatsNew.json`)
2. Captures App Store screenshots on all devices
3. Adds device frames and captions to screenshots
4. Bumps the build number
5. Builds the IPA with App Store signing
6. Uploads binary to TestFlight
7. Submits for App Store review (with metadata and screenshots)

## Usage

**Important:** This submits the app for App Store review. Confirm with the user before running.

```bash
cd "$(git rev-parse --show-toplevel)/ios" && export PATH="/opt/homebrew/opt/ruby/bin:/opt/homebrew/lib/ruby/gems/4.0.0/bin:$PATH" && bundle exec fastlane release 2>&1
```

**Timeout:** This command can take 10+ minutes due to screenshot capture. Use a 600000ms timeout.

## Interpreting results

- Look for `fastlane.tools finished successfully` at the end
- The app will be submitted for Apple review after completion
- Precheck warnings about "test content" or "broken urls" are non-blocking

## Prerequisites

- App Store Connect API key at `~/Desktop/keys/AuthKey_UCV7S354H2.p8`
- Homebrew Ruby with bundler 4.0.8
- Gems installed via `bundle install` in the ios/ directory
- iOS Simulator available for screenshot capture
