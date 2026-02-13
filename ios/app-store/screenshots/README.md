# App Store Screenshots

This directory contains screenshots for App Store submission.

## Generating Screenshots

Screenshots are generated using UI tests that run on specific device simulators.

### Quick Generation (Single Device)

To quickly test screenshot generation on iPhone 16 Pro Max:

```bash
./ios/scripts/generate-app-store-screenshots.sh --quick
```

### Full Generation (All Devices)

To generate screenshots for all required App Store device sizes:

```bash
./ios/scripts/generate-app-store-screenshots.sh
```

### Specific Device

To generate screenshots for a specific device:

```bash
./ios/scripts/generate-app-store-screenshots.sh --device "iPhone 16 Pro Max"
```

## Required Device Sizes

| Display Size | Simulator | Resolution |
|--------------|-----------|------------|
| 6.9" | iPhone 16 Pro Max | 1320 x 2868 |
| 6.7" | iPhone 15 Pro Max | 1290 x 2796 |
| 6.5" | iPhone XS Max | 1242 x 2688 |
| 5.5" | iPhone 8 Plus | 1242 x 2208 |
| 12.9" iPad | iPad Pro (12.9-inch) (6th gen) | 2048 x 2732 |

## Screenshot Order

Screenshots follow the order specified in APP_STORE_METADATA.md:

1. **01_Dashboard** - Home screen with test status
2. **02_TestQuestion** - Active test with sample question
3. **03_Results** - IQ score and domain breakdown
4. **04_History** - Test history with trend chart
5. **05_DomainScores** - Six cognitive domains breakdown
6. **06_Settings** - Privacy-focused settings

## Manual Test Execution

You can also run the screenshot tests directly with xcodebuild:

```bash
cd ios
xcodebuild test \
  -project AIQ.xcodeproj \
  -scheme AIQ \
  -destination 'platform=iOS Simulator,name=iPhone 16 Pro Max' \
  -only-testing:AIQUITests/AppStoreScreenshotTests/testGenerateAllScreenshots \
  -resultBundlePath ~/Desktop/screenshots.xcresult
```

Then use `xcrun xcresulttool` or a tool like `xcparse` to extract the screenshots from the result bundle.

## Directory Structure

After generation:

```
screenshots/
├── README.md
├── iPhone_6.9/
│   ├── 01_Dashboard.png
│   ├── 02_TestQuestion.png
│   └── ...
├── iPhone_6.7/
│   └── ...
├── iPhone_6.5/
│   └── ...
├── iPhone_5.5/
│   └── ...
└── iPad_12.9/
    └── ...
```

## Notes

- Screenshots are captured using mock data (loggedInWithHistory scenario) for consistent, attractive content
- The app must be in DEBUG mode for mock scenarios to work
- Review screenshots before uploading to ensure no personal data is visible
