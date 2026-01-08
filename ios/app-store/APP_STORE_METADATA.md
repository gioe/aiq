# App Store Connect Metadata Guide

This document provides all metadata needed for App Store Connect submission, including privacy questionnaire answers, app descriptions, and screenshot requirements.

**Last Updated:** December 2024
**Task Reference:** ICG-033

---

## Table of Contents

1. [App Information](#app-information)
2. [App Privacy (Data Collection)](#app-privacy-data-collection)
3. [App Description](#app-description)
4. [Keywords](#keywords)
5. [Screenshots Requirements](#screenshots-requirements)
6. [Support & Marketing URLs](#support--marketing-urls)
7. [Age Rating](#age-rating)
8. [Review Notes](#review-notes)

---

## App Information

| Field | Value |
|-------|-------|
| **App Name** | AIQ - Track Your IQ |
| **Subtitle** | Cognitive Performance Tracking |
| **Bundle ID** | com.aiq.app |
| **SKU** | AIQ001 |
| **Primary Language** | English (US) |
| **Category** | Health & Fitness |
| **Secondary Category** | Education |

---

## App Privacy (Data Collection)

### Overview

AIQ does NOT track users for advertising purposes. All data collection is for app functionality, analytics, and crash reporting only.

**Privacy Nutrition Label Configuration:**

| Setting | Value |
|---------|-------|
| **Does your app collect data?** | Yes |
| **Does your app track users?** | No |
| **Privacy Policy URL** | https://aiq.app/privacy-policy |

---

### Data Types Collected

#### 1. Contact Info

**Email Address**
| Question | Answer |
|----------|--------|
| Is this data linked to the user's identity? | **Yes** |
| Is this data used for tracking purposes? | **No** |
| Purpose | App Functionality |
| Additional Details | Used for account authentication and login |

**Name**
| Question | Answer |
|----------|--------|
| Is this data linked to the user's identity? | **Yes** |
| Is this data used for tracking purposes? | **No** |
| Purpose | App Functionality |
| Additional Details | First and last name for profile personalization |

---

#### 2. User Content

**Other User Content** (Test Responses & Results)
| Question | Answer |
|----------|--------|
| Is this data linked to the user's identity? | **Yes** |
| Is this data used for tracking purposes? | **No** |
| Purpose | App Functionality |
| Additional Details | IQ test responses, scores, and cognitive performance metrics |

---

#### 3. Identifiers

**User ID**
| Question | Answer |
|----------|--------|
| Is this data linked to the user's identity? | **Yes** |
| Is this data used for tracking purposes? | **No** |
| Purpose | App Functionality |
| Additional Details | Internal user identifier for linking account data |

**Device ID**
| Question | Answer |
|----------|--------|
| Is this data linked to the user's identity? | **Yes** |
| Is this data used for tracking purposes? | **No** |
| Purpose | App Functionality, Analytics |
| Additional Details | Vendor ID (IDFV) used for crash reporting and analytics attribution |

---

#### 4. Usage Data

**Product Interaction**
| Question | Answer |
|----------|--------|
| Is this data linked to the user's identity? | **Yes** |
| Is this data used for tracking purposes? | **No** |
| Purpose | Analytics |
| Additional Details | App events like test starts, completions, and feature usage for improving the product |

**Other Usage Data** (Test Performance Metrics)
| Question | Answer |
|----------|--------|
| Is this data linked to the user's identity? | **Yes** |
| Is this data used for tracking purposes? | **No** |
| Purpose | App Functionality |
| Additional Details | Test scores, completion times, and cognitive performance history |

---

#### 5. Diagnostics

**Crash Data**
| Question | Answer |
|----------|--------|
| Is this data linked to the user's identity? | **Yes** |
| Is this data used for tracking purposes? | **No** |
| Purpose | App Functionality |
| Additional Details | Crash reports via Firebase Crashlytics for stability improvement |

**Performance Data**
| Question | Answer |
|----------|--------|
| Is this data linked to the user's identity? | **Yes** |
| Is this data used for tracking purposes? | **No** |
| Purpose | App Functionality, Analytics |
| Additional Details | API response times and app performance metrics |

**Other Diagnostic Data**
| Question | Answer |
|----------|--------|
| Is this data linked to the user's identity? | **Yes** |
| Is this data used for tracking purposes? | **No** |
| Purpose | App Functionality |
| Additional Details | Non-fatal errors and debugging information |

---

#### 6. Sensitive Info (Optional)

**Other Sensitive Info** (Demographic Data)
| Question | Answer |
|----------|--------|
| Is this data linked to the user's identity? | **Yes** |
| Is this data used for tracking purposes? | **No** |
| Purpose | App Functionality |
| Additional Details | Optional birth year, education level, and region for statistical norming research |

---

### Data NOT Collected

The following data types are **NOT** collected by AIQ:

- ❌ Precise Location
- ❌ Coarse Location
- ❌ Health & Fitness data
- ❌ Financial Info
- ❌ Payment Info
- ❌ Contacts
- ❌ Browsing History
- ❌ Search History
- ❌ Photos or Videos
- ❌ Audio Data
- ❌ Gameplay Content
- ❌ Customer Support interactions
- ❌ Physical Address
- ❌ Phone Number
- ❌ Advertising Data
- ❌ Fitness data
- ❌ Emails or Text Messages

---

### Third-Party Data Sharing

| Third Party | Data Shared | Purpose |
|-------------|-------------|---------|
| Firebase (Google) | Crash data, device info, user ID | Crash reporting via Crashlytics |
| Apple Push Notification Service | Device token | Push notification delivery |
| Railway (backend host) | All user data | First-party data storage |

**Note:** No data is shared with data brokers, advertisers, or for tracking purposes.

---

## App Description

### Short Description (30 characters)
```
Track your cognitive capacity
```

### Full Description (4000 characters max)

```
AIQ helps you track your cognitive capacity over time—just like you track your physical health with weight and heart rate.

WHAT IS AIQ?
AIQ uses research-based cognitive assessments to measure your IQ with scientifically validated methods. Unlike traditional IQ tests that you take once, AIQ lets you monitor your cognitive performance over months and years to understand how your mind performs over time.

HOW IT WORKS
• Take a comprehensive cognitive assessment covering multiple domains
• Receive your personalized IQ score with detailed breakdown
• Track your cognitive trends over time with historical charts
• Fresh AI-generated questions ensure valid, repeatable assessments

COGNITIVE DOMAINS MEASURED
Each assessment evaluates six key cognitive areas:
• Pattern Recognition - Visual pattern analysis
• Logical Reasoning - Deductive and inductive thinking
• Spatial Processing - Mental rotation and visualization
• Mathematical Ability - Numerical reasoning
• Verbal Intelligence - Language comprehension
• Working Memory - Information retention and recall

DESIGNED FOR YOUR SCHEDULE
We recommend testing every 90 days for optimal tracking. AIQ sends gentle reminders when it's time for your next assessment. Each test takes approximately 20-30 minutes and can be paused and resumed.

PRIVACY-FIRST DESIGN
Your cognitive data is personal. AIQ is built with privacy at its core:
• No advertising or tracking
• Your data is never sold to third parties
• Full account deletion capability
• Transparent data practices documented in our privacy policy

SCIENTIFICALLY GROUNDED
AIQ uses psychometric principles for reliable, valid assessments:
• Questions calibrated using Item Response Theory
• Adaptive difficulty based on performance
• Statistical validity checks for accurate results
• Continuous improvement through research data

START YOUR COGNITIVE JOURNEY
Download AIQ today and begin understanding your mind like never before. Track your IQ, identify trends, and take charge of your cognitive health.

Questions? Contact us at support@aiq.app
```

### Promotional Text (170 characters)
```
Track your cognitive capacity over time. Fresh AI-generated questions, privacy-first design, and scientifically validated assessments.
```

### What's New (Version Notes)
```
• Privacy compliance updates
• Performance improvements
• Bug fixes
```

---

## Keywords

```
iq test,iq score,cognitive,intelligence,brain training,mental fitness,iq tracker,cognitive health,brain test,intelligence test
```

**Note:** Keywords are comma-separated, max 100 characters total.

---

## Screenshots Requirements

### Required Screenshot Dimensions

| Device | Size (pixels) |
|--------|---------------|
| iPhone 6.9" (Pro Max) | 1320 x 2868 |
| iPhone 6.7" (Plus) | 1290 x 2796 |
| iPhone 6.5" | 1242 x 2688 |
| iPhone 5.5" | 1242 x 2208 |
| iPad Pro 12.9" (6th gen) | 2048 x 2732 |
| iPad Pro 12.9" (2nd gen) | 2048 x 2732 |

### Screenshot Content Guide

Screenshots should highlight the following screens in order:

1. **Home/Dashboard**
   - Shows current status and quick test access
   - Caption: "Track your cognitive performance"

2. **Active Test Question**
   - Shows a sample question being answered
   - Caption: "AI-generated cognitive assessments"

3. **Results Screen**
   - Shows IQ score and domain breakdown
   - Caption: "Detailed performance insights"

4. **History/Progress Chart**
   - Shows IQ trend over time
   - Caption: "Monitor your trends over time"

5. **Domain Breakdown**
   - Shows six cognitive domains with scores
   - Caption: "Understand your strengths"

6. **Settings/Profile**
   - Shows privacy-focused settings
   - Caption: "Privacy-first design"

### Screenshot Best Practices

- Use real app UI, not mockups
- Ensure no personal data is visible (use demo/test account)
- Dark mode OR light mode consistently across all screenshots
- High contrast, readable text
- Current iOS version UI

---

## Support & Marketing URLs

| URL Type | URL |
|----------|-----|
| **Privacy Policy URL** | https://aiq.app/privacy-policy |
| **Terms of Service URL** | https://aiq.app/terms-of-service |
| **Support URL** | https://aiq.app/support |
| **Marketing URL** | https://aiq.app |
| **Support Email** | support@aiq.app |
| **Privacy Email** | privacy@aiq.app |

---

## Age Rating

### Content Descriptions

| Question | Answer |
|----------|--------|
| Cartoon or Fantasy Violence | None |
| Realistic Violence | None |
| Prolonged Graphic or Sadistic Violence | None |
| Profanity or Crude Humor | None |
| Mature/Suggestive Themes | None |
| Horror/Fear Themes | None |
| Medical/Treatment Information | None |
| Alcohol, Tobacco, or Drug Use | None |
| Simulated Gambling | None |
| Sexual Content or Nudity | None |
| Graphic Sexual Content and Nudity | None |
| Unrestricted Web Access | No |
| Gambling with Real Currency | No |
| Contests | No |

### Recommended Age Rating
**4+** (Suitable for all ages)

**Note:** While the app measures cognitive abilities similar to IQ tests, it does not provide medical or diagnostic information. It's an educational/fitness tool for self-tracking.

---

## Review Notes

### Demo Account Credentials

```
Email: demo@aiq.app
Password: [Provide to App Review team only]
```

### Review Instructions

```
AIQ is a cognitive assessment app that allows users to track their IQ scores over time.

To test the app:
1. Create an account or use demo credentials
2. Start a new cognitive test from the home screen
3. Answer the assessment questions (approximately 20-30 minutes for full test)
4. View your results and historical trends
5. Check Settings for privacy controls and account management

Key features to review:
• Account creation and login
• Starting and completing a cognitive test
• Viewing test results and history
• Push notification preferences
• Account deletion (Settings > Account > Delete Account)

Notes:
• The app requires network connectivity to fetch questions and submit results
• Push notifications are optional and used for test reminders only
• All data collection is disclosed in our Privacy Policy
• Account deletion permanently removes all user data
```

### Contact Information for Review

```
Name: [App Owner Name]
Email: review@aiq.app
Phone: [Phone Number]
```

---

## Submission Checklist

Before submitting to App Store:

- [ ] App privacy questionnaire completed in App Store Connect
- [ ] Privacy policy URL is live and accessible
- [ ] Terms of service URL is live and accessible
- [ ] Support URL is live and accessible
- [ ] All screenshots uploaded for required device sizes
- [ ] App description reviewed for accuracy
- [ ] Keywords optimized (100 char limit)
- [ ] Demo account created and tested
- [ ] Review notes are clear and complete
- [ ] Age rating questionnaire completed
- [ ] All app capabilities match entitlements
- [ ] Push notification entitlement matches usage
- [ ] In-App Purchase items configured (if applicable)

---

## Related Documentation

- [Privacy Policy](/docs/PRIVACY_POLICY.md)
- [Terms of Service](/docs/TERMS_OF_SERVICE.md)
- [iOS Privacy Manifest](/ios/AIQ/PrivacyInfo.xcprivacy)
- [iOS Codebase Gaps Plan](/docs/plans/in-progress/PLAN-IOS-CODEBASE-GAPS.md)
