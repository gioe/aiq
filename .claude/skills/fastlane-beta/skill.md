---
name: fastlane-beta
description: Build and upload the iOS app to TestFlight with metadata and screenshots. Runs bump_build_number, build, upload_testflight, and upload_metadata.
allowed-tools: Bash, Read
---

# Fastlane Beta Skill

This skill runs the fastlane `beta` lane to build and upload the AIQ iOS app to TestFlight, including metadata and screenshots.

## What it does

1. Bumps the build number (fetches latest from App Store Connect + 1)
2. Builds the IPA with App Store signing
3. Uploads binary to TestFlight
4. Uploads metadata and screenshots to App Store Connect

## Usage

Run the following command:

```bash
cd "$(git rev-parse --show-toplevel)/ios" && export PATH="/opt/homebrew/opt/ruby/bin:/opt/homebrew/lib/ruby/gems/4.0.0/bin:$PATH" && bundle exec fastlane beta 2>&1
```

**Timeout:** This command takes 3-5 minutes. Use a 600000ms timeout.

## Interpreting results

- Look for `fastlane.tools finished successfully` at the end
- The build number and TestFlight upload status will be in the output
- Precheck warnings about "test content" or "broken urls" are non-blocking and can be ignored (the word "test" refers to cognitive tests, not test builds)
- If it fails, check for signing issues, API key problems, or App Store Connect errors

## Prerequisites

- App Store Connect API key at `~/Desktop/keys/AuthKey_UCV7S354H2.p8`
- Homebrew Ruby with bundler 4.0.8
- Gems installed via `bundle install` in the ios/ directory
