# BTS-182: Notification Permission Strategy Analysis

## Executive Summary

**Recommendation: Request notification permission after first test completion (Option 2) with optional provisional notifications as a supplementary approach.**

This strategy maximizes opt-in rates by establishing value before asking for permissions, aligns with iOS best practices, and fits the unique characteristics of AIQ's 3-month testing cadence.

---

## Context

### App Characteristics
- **Testing Cadence**: Users take IQ tests every 3 months
- **Long Intervals**: 90-day gaps between meaningful app interactions
- **High Stakes**: Users need timely reminders or they may forget to test
- **Value Proposition**: Cognitive capacity tracking over time
- **Current State**: Onboarding Page 3 mentions reminders can be enabled in Settings (no permission request during onboarding)

### The Decision Point
Onboarding Screen 3 currently states "You can enable reminders in Settings to help you track your progress." We need to decide WHEN and HOW to request notification permissions.

---

## Option Analysis

### Option 1: Request During Onboarding

**Description**: Add a permission request during or immediately after onboarding flow (e.g., at the end of Page 4).

#### Pros
- **Maximum Coverage**: Reaches 100% of new users at the start
- **Simplicity**: Single, predictable permission flow
- **Immediate Setup**: No follow-up prompts needed
- **Aligns with Messaging**: Page 3 already mentions reminders

#### Cons
- **Low Grant Rates**: Average iOS opt-in during onboarding: 43-45% (vs 80% on Android)
- **No Demonstrated Value**: Users haven't experienced the app yet
- **Permanent Denial Risk**: iOS permission prompt appears only ONCE - if denied, extremely difficult to recover (requires manual Settings navigation)
- **Cognitive Overload**: Users already processing onboarding information
- **Against Apple Guidance**: Apple explicitly recommends waiting for "meaningful user action"

#### Data Points
- Average iOS opt-in rate: 43.9% in 2025
- Apps using onboarding prompts: 37-45% immediate dismissal rate
- Gaming apps (similar to our use case): 37% rejection rate
- **Critical**: If user taps "Don't Allow", it takes multiple taps in Settings to re-grant - effectively permanent

---

### Option 2: Request After First Test Completion ⭐ RECOMMENDED

**Description**: Show permission prompt immediately after user completes their first test, when they've just experienced the core value proposition.

#### Pros
- **Demonstrated Value**: User has just experienced what notifications will remind them about
- **"A-ha Moment" Timing**: User understands the need for 3-month reminders after seeing the test
- **Higher Grant Rates**: Post-action prompts see 40% higher consent rates than onboarding
- **Natural Context**: "Want to be reminded when it's time for your next test?"
- **Psychological Momentum**: User just invested 12 minutes; likely to want reminders
- **Recoverable**: If denied, we can re-prime later with soft prompts

#### Cons
- **Lower Coverage**: Only reaches users who complete first test (~85-90% completion expected)
- **Implementation Complexity**: Requires tracking first-test completion state
- **Delayed Protection**: 10-15% of users might exit before completing first test
- **Additional Code**: Need logic to show prompt once per user lifecycle

#### Best Practice Alignment
- Apple Developer Documentation: "Trigger after meaningful user action"
- Industry consensus: "Wait for user to recognize product worth"
- CleverTap study: Apps targeting engaged users see higher opt-in rates
- Cluster case study: 89% opt-in when users trigger prompt themselves

#### Implementation Notes
- Show immediately after test results screen
- Use pre-permission "soft prompt" explaining 3-month reminder value
- Store `hasRequestedNotificationPermission` flag in UserDefaults
- Fallback: Settings screen always available

---

### Option 3: Provisional Authorization (Quiet Notifications)

**Description**: Use iOS 12+ provisional authorization to send silent notifications to Notification Center without explicit permission.

#### Pros
- **No Permission Needed**: Notifications delivered without user prompt
- **Try Before Committing**: Users experience notification value first
- **Gradual Escalation**: Users can "Keep" or "Turn Off" notifications
- **Zero Rejection Risk**: No system prompt to deny

#### Cons
- **Silent Delivery Only**: No lock screen, no sound, no badge - easily missed
- **Inappropriate for Use Case**: 3-month reminders MUST be seen, not buried in Notification Center
- **Health App Anti-Pattern**: "Health apps should ensure full opt-in before delivering information"
- **Critical Alerts Unavailable**: Critical Alerts (loud, bypasses DND) require Apple approval and are for urgent medical/safety use only
- **Uncertain Upgrade Path**: Users may never notice silent notifications to upgrade

#### Apple Guidance
- "Make sure provisional push makes sense for your use cases"
- "If messaging is urgent or will cause issues if missed, get full opt-in ASAP"
- "Health apps should ensure traditional opt-in before delivering information"

#### Verdict for AIQ
**Not recommended as primary strategy** because:
1. 3-month reminders are too important to miss
2. Silent notifications may never be seen
3. Health/cognitive tracking apps should use explicit permissions
4. Our use case doesn't benefit from "try before committing"

**However**: Could be used as a supplementary approach:
- Enable provisional on first launch
- Send one silent notification at Day 30
- If user engages, show full permission prompt
- Provides data on notification engagement before asking

---

## Industry Data & Best Practices

### Opt-In Rates (2025-2026)
| Timing Strategy | iOS Opt-In Rate |
|----------------|----------------|
| Onboarding (immediate) | 43-45% |
| Onboarding with priming | 50-60% |
| Post-action (contextual) | 60-70% |
| Self-triggered | 89% |

### Key Statistics
- Apps using optimization techniques see **40% higher consent rates**
- Users who opt-in are **4x more engaged** and **2x more likely to be retained**
- Gaming industry: 63.5% opt-in rate (relevant for engagement-based apps)
- Banking/Business/Services: Highest iOS opt-in rates

### iOS Platform Considerations
- **One Shot Only**: Permission prompt appears once per app lifetime
- **Recovery Difficulty**: Requires Settings > [App] > Notifications (5+ taps)
- **iOS 18 Changes**: New "Priority Notifications" system ranks alerts by importance
- **Provisional Limitation**: Always silent - no alerts, sounds, or badges

---

## Recommendation: Hybrid Approach

### Primary Strategy: Post-First-Test Permission (Option 2)

**Implementation Flow:**

1. **During Onboarding (Page 3)**
   - Keep current messaging: "You can enable reminders in Settings"
   - No permission request
   - Educate about 3-month cadence

2. **After First Test Completion**
   - Show custom "soft prompt" immediately after results screen
   - Explain: "You'll test again in 3 months. Get a reminder so you don't miss it."
   - If user accepts soft prompt → trigger iOS system permission dialog
   - If user declines soft prompt → no harm done, can retry later

3. **Fallback: Settings Screen**
   - Always available for users who change their mind
   - Show instructional banner if permission denied at OS level

### Supplementary Strategy: Optional Provisional Notifications

**If development resources allow**, add provisional authorization:

1. **First Launch**: Request provisional authorization silently
2. **Day 30 Reminder**: Send quiet notification: "Your first test was 30 days ago..."
3. **If User Engages**: Show full permission prompt with priming
4. **If No Engagement**: Wait for first test completion flow

This provides early data on notification engagement without risking permanent denial.

---

## Rationale

### Why Post-First-Test Wins

1. **Value Alignment**: User has just experienced what notifications will remind them about
2. **Timing is Critical**: iOS permission prompt appears only once - we need maximum conversion
3. **Data-Driven**: Post-action prompts see 40% higher consent vs onboarding
4. **Apple Guidance**: Explicitly recommends "meaningful action" timing
5. **Recoverable**: Soft prompt allows retry without burning iOS permission
6. **Psychological Momentum**: User just invested 12 minutes, understands value

### Why Not Onboarding

1. **Low Conversion**: 43-45% vs 60-70% for post-action
2. **Permanent Risk**: Denying iOS prompt is effectively irreversible
3. **No Context**: User hasn't experienced the app yet
4. **Cognitive Load**: Already processing onboarding information

### Why Provisional is Supplementary, Not Primary

1. **Silent Notifications**: Too easy to miss for 3-month cadence
2. **Health App Guidance**: Apple recommends full opt-in for health information
3. **Critical Use Case**: Can't risk users missing test reminders
4. **Limited Value**: "Try before commit" doesn't apply to simple reminders

---

## Implementation Plan

### Phase 1: Core Implementation (Required)

**Task 1.1: Add Permission State Tracking**
- Add `hasRequestedNotificationPermission: Bool` to UserDefaults
- Add check to prevent duplicate permission requests
- Estimated effort: 30 minutes

**Task 1.2: Create Soft Prompt UI**
- Design custom pre-permission screen
- Title: "Don't Miss Your Next Test"
- Body: "You'll test again in 3 months. Get a reminder so you can track your cognitive trends."
- Actions: "Enable Reminders", "Not Now"
- Estimated effort: 2 hours

**Task 1.3: Add Post-Test Permission Flow**
- Trigger soft prompt after first test completion
- If user accepts → call NotificationManager.requestAuthorization()
- Store permission request state
- Estimated effort: 2 hours

**Task 1.4: Update Settings Screen**
- Add instructional banner when permission denied at OS level
- Show "Go to Settings" deep link if needed
- Estimated effort: 1 hour

**Total Phase 1: 5.5 hours**

### Phase 2: Provisional Notifications (Optional Enhancement)

**Task 2.1: Enable Provisional Authorization**
- Update NotificationManager to request `.provisional` on first launch
- No user-facing prompt
- Estimated effort: 1 hour

**Task 2.2: Day 30 Reminder Logic**
- Backend: Calculate 30 days after first test
- Send silent notification if provisional enabled
- Estimated effort: 2 hours (backend + iOS)

**Task 2.3: Engagement Tracking**
- Track if user taps provisional notification
- Show full permission prompt if engaged
- Estimated effort: 2 hours

**Total Phase 2: 5 hours**

---

## Success Metrics

### Primary Metrics
- **Notification Opt-In Rate**: Target 60-70% (vs 43% baseline)
- **Test Completion Rate**: % of users completing 2nd test on time
- **Notification Engagement**: % of users who tap reminder notifications

### Secondary Metrics
- **Permission Prompt Timing**: When users see prompt (test #1, #2, etc.)
- **Settings Screen Conversion**: % who enable after initial decline
- **Provisional Engagement**: % who interact with quiet notifications (if implemented)

### Success Criteria
- Achieve >60% opt-in rate (vs 43% industry average for onboarding)
- <5% permission denials at OS level (prevent permanent rejection)
- 2nd test completion rate improves with notifications enabled

---

## Stakeholder Alignment

### User Experience Team
- Maintains clean onboarding flow
- Respects user attention during initial experience
- Aligns permission request with demonstrated value

### Engineering Team
- Clear implementation path
- Leverages existing NotificationManager
- Minimal new infrastructure required

### Product Team
- Data-driven decision based on industry benchmarks
- Maximizes notification reach for retention
- Preserves ability to iterate (soft prompts allow retry)

---

## Open Questions

1. **Soft Prompt Copy**: Should we A/B test different messaging?
2. **Retry Logic**: How often should we re-show soft prompt if declined?
3. **Provisional Implementation**: Phase 1 only or include Phase 2?
4. **Analytics**: What events should we track for optimization?
5. **Edge Cases**: What if user force-quits after test before seeing prompt?

---

## Next Steps

1. **Product Decision**: Confirm recommendation or request alternative analysis
2. **Design Review**: Create soft prompt UI mockups
3. **Engineering Estimate**: Confirm effort estimates with iOS team
4. **Analytics Setup**: Define tracking events for success metrics
5. **Implementation**: Execute Phase 1 (core functionality)
6. **Monitoring**: Track opt-in rates and adjust strategy

---

## Sources

### iOS Best Practices & Grant Rates
- [iOS push notifications guide (2026): How they work, setup, and best practices | Pushwoosh](https://www.pushwoosh.com/blog/ios-push-notifications/)
- [Asking permission to use notifications | Apple Developer Documentation](https://developer.apple.com/documentation/usernotifications/asking-permission-to-use-notifications)
- [The Ultimate Guide to Push Notification Consent in 2025](https://www.anstrex.com/blog/the-ultimate-guide-to-push-notification-consent-in-2025)
- [How to increase push notification opt-in rate: Best practices](https://www.pushwoosh.com/blog/increase-push-notifications-opt-in/)
- [Asking for iOS push notification permissions - CleverTap](https://clevertap.com/blog/asking-for-ios-push-notification-permissions/)

### Provisional Authorization & Quiet Notifications
- [iOS Provisional Notifications | Medium](https://medium.com/@samermurad555/ios-provisional-notifications-eeb3832836fc)
- [Sending trial notifications with provisional authorization on iOS](https://nilcoalescing.com/blog/TrialNotificationsWithProvisionalAuthorizationOnIOS/)
- [Improve Your Push Notification Strategy with Provisional Push | Braze](https://www.braze.com/resources/articles/mastering-provisional-push)
- [Provisional Authorization of User Notifications](https://useyourloaf.com/blog/provisional-authorization-of-user-notificatons/)

### Onboarding vs Post-Action Timing
- [Push notifications: how to maximize opt-ins](https://www.ngrow.ai/blog/push-notifications-how-to-maximize-opt-ins)
- [Onboarding UX Patterns | Permission Priming | UserOnboard](https://www.useronboard.com/onboarding-ux-patterns/permission-priming/)
- [Asking nicely: 3 strategies for successful mobile permission priming](https://www.appcues.com/blog/mobile-permission-priming)
- [iOS Push Notification Permissions: The Best Practices](https://blog.hurree.co/ios-push-notification-permissions-best-practises)

---

## Document Information

- **Ticket**: BTS-182
- **Created**: 2026-01-10
- **Author**: Product Analysis
- **Status**: Pending Review
- **Impact**: High (affects user retention and notification reach)
