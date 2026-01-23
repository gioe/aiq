# Privacy Policy

**Effective Date:** January 23, 2026

This Privacy Policy describes how AIQ ("we," "us," or "our") collects, uses, and shares your personal information when you use our mobile application (the "App"). We are committed to protecting your privacy and being transparent about our data practices.

## Table of Contents

1. [Information We Collect](#information-we-collect)
2. [How We Use Your Information](#how-we-use-your-information)
3. [How We Share Your Information](#how-we-share-your-information)
4. [Data Retention](#data-retention)
5. [Data Security](#data-security)
6. [Your Rights and Choices](#your-rights-and-choices)
7. [International Data Transfers](#international-data-transfers)
8. [Children's Privacy](#childrens-privacy)
9. [California Privacy Rights (CCPA)](#california-privacy-rights-ccpa)
10. [European Privacy Rights (GDPR)](#european-privacy-rights-gdpr)
11. [Changes to This Policy](#changes-to-this-policy)
12. [Contact Us](#contact-us)

## Information We Collect

We collect information that you provide directly to us and information that is automatically collected when you use the App.

### Personal Information You Provide

When you create an account and use AIQ, we collect:

- **Email Address** - Used for account authentication, login, and important service communications
- **Name** (first and last) - Used to personalize your profile and test results display
- **Password** - Stored securely using industry-standard bcrypt hashing (we never store passwords in plain text)

### Test Performance Data

To provide our core cognitive assessment service, we collect:

- **Test Responses** - Your answers to assessment questions
- **Test Scores** - Calculated IQ scores and performance metrics
- **Response Times** - Time spent on each question (used for validity analysis)
- **Test Completion Data** - Test start times, completion times, and session status

This data is essential for:
- Tracking your cognitive capacity over time
- Generating personalized insights
- Ensuring test validity through statistical analysis
- Improving question quality

### Automatically Collected Information

When you use the App, we automatically collect:

- **Device ID** - A unique identifier for your iOS device, used for:
  - Crash reporting and debugging
  - Analytics to improve app performance
  - Linking your test sessions to your account

- **Crash and Diagnostic Data** - Information about app crashes, errors, and performance issues, including:
  - Stack traces and error logs
  - App state at time of crash
  - Device model and iOS version
  - Non-fatal errors for debugging

- **Analytics Data** - Information about how you interact with the App:
  - Features you use
  - Screens you view
  - Actions you take (e.g., starting a test, viewing history)
  - App session duration
  - Performance metrics (load times, responsiveness)

### What We Don't Collect

We want to be clear about data we **do not** collect:

- Location data (GPS, geolocation, IP-based location)
- Contacts or address book
- Photos or camera access
- Microphone or audio
- Health data from HealthKit
- Browsing history or web activity
- Advertising identifiers (IDFA)
- Device fingerprints for tracking purposes
- Demographic information (age, gender, race, etc.) unless you voluntarily provide it

**We do not track you for advertising purposes.** Our App does not use advertising tracking, does not share data with data brokers, and does not sell your personal information.

## How We Use Your Information

We use your information for the following purposes:

### Core Service Delivery (Legal Basis: Contract Performance)

- **Account Management** - Creating and maintaining your account, authenticating your identity
- **Test Administration** - Delivering cognitive assessment questions, recording responses
- **Score Calculation** - Computing IQ scores using statistical models
- **Historical Tracking** - Storing your test results over time to show cognitive trends
- **Question Rotation** - Ensuring you don't receive repeated questions by tracking which questions you've seen

### Service Improvement (Legal Basis: Legitimate Interest)

- **Quality Assurance** - Analyzing question difficulty, discrimination, and reliability
- **Validity Analysis** - Detecting aberrant response patterns that may indicate invalid test-taking (e.g., random clicking, test-taking under inappropriate conditions)
- **App Performance** - Monitoring crashes, errors, and performance issues to improve stability
- **Product Development** - Understanding which features are used to prioritize improvements
- **Analytics** - Analyzing aggregate usage patterns to optimize user experience

### Communication (Legal Basis: Legitimate Interest / Consent)

- **Service Communications** - Sending important updates about your account, tests, or the App
- **Test Reminders** - Sending push notifications to remind you when it's time for your next assessment (every 90 days) - you can opt out anytime

### Security and Fraud Prevention (Legal Basis: Legitimate Interest)

- **Test Validity** - Using statistical analysis to identify potentially invalid test sessions
- **Security Monitoring** - Detecting and preventing unauthorized access or abuse
- **Error Detection** - Identifying and fixing bugs that could affect data integrity

## How We Share Your Information

We do not sell, rent, or trade your personal information. We share your information only in the following limited circumstances:

### Service Providers

We share data with third-party service providers who help us operate the App:

- **Firebase Crashlytics (Google)** - Crash reporting and app stability monitoring. Firebase receives crash logs, device information, and stack traces. [Firebase Privacy Policy](https://firebase.google.com/support/privacy)

- **Railway** - Cloud hosting provider for our backend database and API services. Railway hosts our PostgreSQL database containing your account information, test responses, and scores. [Railway Privacy Policy](https://railway.app/legal/privacy)

- **Apple Push Notification Service (APNs)** - Delivery of push notifications for test reminders. Apple receives your device token (not linked to your identity by us) to route notifications. [Apple Privacy Policy](https://www.apple.com/legal/privacy/)

All service providers are contractually obligated to use your data only for the purposes we specify and to protect your data with appropriate security measures.

### Legal Obligations

We may disclose your information if required to do so by law or in response to valid requests by public authorities (e.g., a court order or subpoena), including to meet national security or law enforcement requirements.

### Business Transfers

If AIQ is involved in a merger, acquisition, or sale of assets, your information may be transferred as part of that transaction. We will notify you via email and/or a prominent notice in the App before your information is transferred and becomes subject to a different privacy policy.

### Aggregated or De-Identified Data

We may share aggregated, de-identified, or anonymized data that cannot reasonably be used to identify you. For example, we might publish research about average IQ score distributions or question difficulty statistics.

## Data Retention

We retain your personal information for as long as necessary to provide our services and fulfill the purposes described in this Privacy Policy.

### Active Accounts

- **Account Information** - Retained as long as your account is active
- **Test Results** - Retained as long as your account is active to provide historical tracking
- **Analytics Data** - Retained for up to 24 months for service improvement

### Deleted Accounts

When you delete your account:
- Your email, name, and account credentials are permanently deleted within 30 days
- Your test responses and scores are permanently deleted within 30 days
- Aggregated analytics that cannot identify you may be retained
- Some data may be retained longer if required by law or for legitimate business purposes (e.g., fraud prevention, financial records)

### Backup Retention

Data in backups may persist for up to 90 days after deletion from production systems, after which it is permanently destroyed.

## Data Security

We implement industry-standard security measures to protect your information:

### Technical Safeguards

- **Encryption in Transit** - All data transmitted between the App and our servers uses TLS 1.2+ encryption
- **Encryption at Rest** - Sensitive data stored in our database is encrypted
- **Password Security** - Passwords are hashed using bcrypt with salt, never stored in plain text
- **Token-Based Authentication** - JWT tokens with secure key signing for session management
- **Secure API Endpoints** - Rate limiting and security headers to prevent abuse

### Organizational Safeguards

- **Access Controls** - Strict access controls limiting who can access personal data
- **Monitoring** - Security monitoring for unauthorized access attempts
- **Incident Response** - Procedures for detecting and responding to data breaches
- **Vendor Management** - Security requirements for all third-party service providers

### Limitations

No method of transmission over the internet or electronic storage is 100% secure. While we strive to protect your personal information, we cannot guarantee its absolute security. If we become aware of a security breach that compromises your data, we will notify you in accordance with applicable law.

## Your Rights and Choices

You have choices regarding your personal information:

### Account Information

- **Access and Update** - You can view and update your profile information (name, email) within the App settings
- **Delete Account** - You can request deletion of your account and all associated data by contacting us at privacy@aiq.app

### Test Data

- **View History** - You can view all your past test results in the App's History section
- **Delete Specific Tests** - Contact us to request deletion of specific test sessions

### Push Notifications

- **Opt Out** - You can disable push notifications at any time:
  - In the App: Settings > Notifications
  - In iOS: Settings > AIQ > Notifications

### Analytics

- **Limit Analytics** - While you cannot opt out of essential analytics (needed for app functionality), you can limit data collection by using the App less frequently

### Do Not Sell My Information

We do not sell your personal information. We have not sold personal information in the preceding 12 months.

## International Data Transfers

AIQ is based in the United States. Your information may be transferred to, stored, and processed in the United States or other countries where our service providers operate.

### Data Transfer Safeguards

When we transfer data internationally, we rely on:

- **Standard Contractual Clauses** - EU-approved contract terms with service providers
- **Adequacy Decisions** - Transfers to countries deemed adequate by the European Commission
- **Necessary for Contract Performance** - Transfers required to provide the service you requested

If you are located in the European Economic Area (EEA), United Kingdom, or Switzerland, we ensure appropriate safeguards are in place for international transfers as required by GDPR.

## Children's Privacy

AIQ is not intended for children under 13 years of age. We do not knowingly collect personal information from children under 13. If you are a parent or guardian and believe your child has provided us with personal information, please contact us at privacy@aiq.app. If we learn we have collected personal information from a child under 13, we will delete that information promptly.

## California Privacy Rights (CCPA)

If you are a California resident, you have specific rights under the California Consumer Privacy Act (CCPA):

### Right to Know

You have the right to request that we disclose:
- Categories of personal information we collected about you
- Categories of sources from which the information was collected
- Business or commercial purpose for collecting the information
- Categories of third parties with whom we share personal information
- Specific pieces of personal information we collected about you

### Right to Delete

You have the right to request deletion of your personal information, subject to certain exceptions (e.g., to complete a transaction, detect security incidents, comply with legal obligations).

### Right to Opt-Out of Sale

You have the right to opt out of the "sale" of your personal information. **We do not sell your personal information and have not sold personal information in the preceding 12 months.**

### Right to Non-Discrimination

You have the right not to receive discriminatory treatment for exercising your CCPA rights.

### How to Exercise Your Rights

To exercise your rights, contact us at privacy@aiq.app with the subject line "CCPA Request." We will verify your identity before processing your request. You may designate an authorized agent to make requests on your behalf; we will require proof of authorization.

### Response Timing

We will respond to verifiable requests within 45 days. If we need more time (up to 90 days total), we will notify you of the reason and extension period.

### Information Sharing for Business Purposes

In the preceding 12 months, we have shared the following categories of personal information for business purposes:

| Category | Shared With | Purpose |
|----------|-------------|---------|
| Identifiers (email, user ID, device ID) | Railway, Firebase | Service delivery, crash reporting |
| Test performance data | Railway | Data storage |
| Device and usage data | Firebase, Railway | Analytics, debugging |

## European Privacy Rights (GDPR)

If you are located in the European Economic Area (EEA), United Kingdom, or Switzerland, you have rights under the General Data Protection Regulation (GDPR):

### Data Controller

AIQ is the data controller responsible for your personal information. Contact details are provided in the [Contact Us](#contact-us) section.

### Legal Bases for Processing

We process your personal information under the following legal bases:

- **Contract Performance** - Processing necessary to provide the AIQ service (account management, test delivery, score calculation)
- **Legitimate Interests** - Processing for analytics, service improvement, security, and fraud prevention, where not overridden by your rights
- **Consent** - Processing for optional features like push notifications (you can withdraw consent anytime)
- **Legal Obligations** - Processing to comply with laws and regulations

### Your GDPR Rights

You have the right to:

- **Access** - Obtain confirmation of whether we process your data and receive a copy
- **Rectification** - Correct inaccurate or incomplete personal data
- **Erasure** ("Right to be Forgotten") - Request deletion of your personal data in certain circumstances
- **Restriction of Processing** - Request that we limit how we use your data
- **Data Portability** - Receive your data in a structured, machine-readable format and transmit it to another controller
- **Object** - Object to processing based on legitimate interests or for direct marketing purposes
- **Withdraw Consent** - Withdraw consent for processing that requires consent (e.g., push notifications)
- **Lodge a Complaint** - File a complaint with your local data protection authority

### How to Exercise Your Rights

To exercise your GDPR rights, contact us at privacy@aiq.app. We will respond within 30 days (extendable by 60 days for complex requests).

### Data Protection Authority

If you are not satisfied with our response, you have the right to lodge a complaint with your supervisory authority. A list of EEA data protection authorities is available at: https://edpb.europa.eu/about-edpb/board/members_en

## Changes to This Policy

We may update this Privacy Policy from time to time to reflect changes in our practices, technology, legal requirements, or other factors.

### Notification of Changes

- **Material Changes** - If we make material changes, we will notify you via email (sent to the email address associated with your account) and/or through a prominent notice in the App at least 30 days before the changes take effect
- **Non-Material Changes** - For minor changes, we will update the "Effective Date" at the top of this policy

### Your Acceptance

Your continued use of the App after the effective date of an updated Privacy Policy constitutes your acceptance of the changes. If you do not agree to the updated policy, please stop using the App and delete your account.

## Contact Us

If you have questions, concerns, or requests regarding this Privacy Policy or our data practices, please contact us:

**Email:** privacy@aiq.app

**Subject Line for Requests:**
- "GDPR Request" - For EU data subject rights
- "CCPA Request" - For California privacy rights
- "Privacy Question" - For general inquiries

We will respond to all legitimate requests within the timeframes required by applicable law.

---

**Last Updated:** January 23, 2026

This Privacy Policy is effective as of the date stated above and applies to all users of the AIQ mobile application.
