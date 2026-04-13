---
name: fastlane-upload-metadata
description: Upload App Store metadata (description, keywords, screenshots, review info) to App Store Connect without building or uploading a binary.
allowed-tools: Bash, Read
---

# Fastlane Upload Metadata Skill

This skill runs the fastlane `upload_metadata` lane to push metadata and screenshots to App Store Connect.

## What it does

- Uploads app name, subtitle, description, keywords, promotional text
- Uploads support/marketing/privacy URLs
- Uploads categories and review information
- Uploads screenshots for all device sizes

## Usage

```bash
cd "$(git rev-parse --show-toplevel)/ios" && export PATH="/opt/homebrew/opt/ruby/bin:/opt/homebrew/lib/ruby/gems/4.0.0/bin:$PATH" && bundle exec fastlane upload_metadata 2>&1
```

**Timeout:** Use a 300000ms timeout.

## Interpreting results

- Look for `fastlane.tools finished successfully` at the end
- Screenshots that are already uploaded will show "Previous uploaded. Skipping"
- Precheck warnings about "test content" or "broken urls" are non-blocking

## Metadata file locations

All metadata lives in `ios/fastlane/metadata/`:
- `en-US/name.txt` — App name (max 30 chars)
- `en-US/subtitle.txt` — Subtitle (max 30 chars)
- `en-US/description.txt` — Full description
- `en-US/keywords.txt` — Comma-separated keywords (max 100 chars)
- `en-US/promotional_text.txt` — Promotional text
- `en-US/release_notes.txt` — What's new
- `en-US/support_url.txt`, `marketing_url.txt`, `privacy_url.txt` — URLs
- `primary_category.txt`, `secondary_category.txt` — Categories (SCREAMING_CASE)
- `review_information/` — App review contact details

Screenshots live in `ios/fastlane/screenshots/en-US/`.
