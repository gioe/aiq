# Certificate Rotation Runbook

This runbook provides step-by-step procedures for updating SSL certificate pins in the AIQ iOS app to prevent outages due to certificate expiration.

## Overview

AIQ uses TrustKit for certificate pinning against the Railway backend. When certificates expire or are rotated, the pinned hashes must be updated in the iOS app, otherwise all API connections will fail in production builds.

## Current Certificate Status

| Certificate | Domain | Expires | Reminder Date | Status |
|-------------|--------|---------|---------------|--------|
| Railway Backend | `*.up.railway.app` | 2026-03-06 | 2026-02-04 | Active |
| Let's Encrypt R12 | Intermediate CA | 2027-03-12 | 2027-02-10 | Backup |

## Calendar Reminders

Set the following calendar reminders to ensure proactive certificate rotation:

### Railway Certificate (Primary)
- **Reminder Date**: February 4, 2026
- **Lead Time**: 30 days before expiration (March 6, 2026)
- **Title**: "AIQ Certificate Rotation Required - Railway Backend"
- **Description**: "Railway backend SSL certificate expires on 2026-03-06. Follow the Certificate Rotation Runbook to update TrustKit.plist."
- **Assignees**: On-call engineer rotation

### Let's Encrypt R12 Intermediate (Backup)
- **Reminder Date**: February 10, 2027
- **Lead Time**: 30 days before expiration (March 12, 2027)
- **Title**: "AIQ Certificate Rotation Required - Let's Encrypt R12"
- **Description**: "Let's Encrypt R12 intermediate certificate expires on 2027-03-12. Follow the Certificate Rotation Runbook to update TrustKit.plist."
- **Assignees**: On-call engineer rotation

## Pre-Rotation Checklist

Before rotating certificates, verify:

- [ ] Access to the AIQ iOS repository
- [ ] Xcode installed with iOS 17+ SDK
- [ ] openssl command-line tools available
- [ ] Access to production Railway backend
- [ ] App Store Connect access for emergency release (if needed)

## Certificate Rotation Procedure

### Step 1: Check Current Certificate Expiration

Run the monitoring script to check current certificate status:

```bash
./ios/scripts/check_certificate_expiration.sh
```

Or manually check the Railway backend certificate:

```bash
echo | openssl s_client -servername aiq-backend-production.up.railway.app \
  -connect aiq-backend-production.up.railway.app:443 2>/dev/null | \
  openssl x509 -noout -dates
```

Expected output:
```
notBefore=<issue_date>
notAfter=<expiration_date>
```

### Step 2: Generate New Certificate Hash

Extract the new public key hash from the production certificate:

```bash
openssl s_client -servername aiq-backend-production.up.railway.app \
  -showcerts -connect aiq-backend-production.up.railway.app:443 2>/dev/null | \
  openssl x509 -pubkey -noout | \
  openssl pkey -pubin -outform der | \
  openssl dgst -sha256 -binary | \
  base64
```

Save the output - this is the new hash to add to TrustKit.plist.

### Step 3: Update TrustKit.plist

Edit `ios/AIQ/TrustKit.plist`:

1. Open the file in your editor
2. Locate the `TSKPublicKeyHashes` array
3. Add the new hash while keeping the old hash temporarily:

```xml
<key>TSKPublicKeyHashes</key>
<array>
    <!-- NEW: Railway backend certificate -->
    <!-- Valid until: YYYY-MM-DD -->
    <string>NEW_HASH_HERE=</string>

    <!-- OLD: Railway backend certificate (remove after transition) -->
    <!-- Valid until: 2026-03-06 -->
    <string>i+fyVetXyACCzW7mWtTNzuYIjv0JpKqW00eIiiuLp1o=</string>

    <!-- Let's Encrypt R12 Intermediate Certificate (Backup Pin) -->
    <!-- Valid until: 2027-03-12 -->
    <string>kZwN96eHtZftBWrOZUsd6cA4es80n3NzSk/XtYz2EqQ=</string>
</array>
```

4. Update the expiration date comments
5. Update the "Generated" date comment

### Step 4: Test Certificate Pinning

#### 4a. Build in DEBUG mode (against production)

```bash
cd ios
xcodebuild build -scheme AIQ \
  -destination 'platform=iOS Simulator,name=iPhone 16' \
  -configuration Debug
```

Run the app and verify API calls succeed.

#### 4b. Build in RELEASE mode

```bash
cd ios
xcodebuild build -scheme AIQ \
  -destination 'platform=iOS Simulator,name=iPhone 16' \
  -configuration Release
```

Run the app and verify:
- Console shows "TrustKit initialized with certificate pinning"
- API calls succeed
- No SSL validation errors

#### 4c. Run automated tests

```bash
cd ios
xcodebuild test -scheme AIQ \
  -destination 'platform=iOS Simulator,name=iPhone 16' \
  -only-testing:AIQTests/CertificatePinningTests
```

All tests must pass.

### Step 5: Deploy Update

1. Create a PR with the TrustKit.plist changes
2. Get code review approval
3. Merge to main
4. Create a new app release
5. Submit to App Store for review
6. Enable phased rollout (recommended)

### Step 6: Post-Rotation Cleanup

After the old certificate has expired and all users have updated:

1. Remove the old certificate hash from TrustKit.plist
2. Ensure at least 2 hashes remain (primary + backup)
3. Update this runbook with new expiration dates
4. Set new calendar reminders

## Related Files

These files are essential for certificate pinning incident response:

| File | Purpose |
|------|---------|
| [`ios/AIQ/TrustKit.plist`](../AIQ/TrustKit.plist) | Certificate pinning configuration with public key hashes |
| [`ios/AIQ/AppDelegate.swift`](../AIQ/AppDelegate.swift) (lines 67-119) | TrustKit initialization and validation logic |

**Automation Scripts:**

| Script | Purpose |
|--------|---------|
| [`ios/scripts/check_certificate_expiration.sh`](../scripts/check_certificate_expiration.sh) | Automated certificate expiration monitoring with configurable warning thresholds |

## Emergency Procedures

### Scenario: Certificate Expired Before App Update

If users are experiencing connection failures due to expired certificates:

1. **Immediate**: Check if Railway auto-renewed the certificate
2. **If renewed**: Generate new hash and push emergency app update
3. **Verify via TestFlight (Release configuration)**: Before App Store submission, deploy the fix to TestFlight using **Release** configuration and verify API connectivity works with the new certificate hash. TrustKit certificate pinning is only active in Release builds — Debug builds bypass pinning. Always test certificate changes in Release configuration.
4. **If not renewed**: Contact Railway support
5. **Communication**: Post status update to users

### Scenario: Railway Changes Certificate Unexpectedly

Railway may rotate certificates before expiration. If API calls start failing:

1. Run the monitoring script to detect changes:
   ```bash
   ./ios/scripts/check_certificate_expiration.sh
   ```
2. If hash mismatch detected, follow rotation procedure immediately
3. Request expedited App Store review if needed

### Scenario: Let's Encrypt Changes Intermediate Certificate

Let's Encrypt periodically rotates intermediate certificates. If the R12 intermediate expires or changes:

1. Download new intermediate from https://letsencrypt.org/certificates/
2. Generate hash for new intermediate:
   ```bash
   curl -s https://letsencrypt.org/certs/2024/r12.pem | \
     openssl x509 -pubkey -noout | \
     openssl pkey -pubin -outform der | \
     openssl dgst -sha256 -binary | \
     base64
   ```
3. Update TrustKit.plist with new backup pin

## Monitoring

### Automated Monitoring

Run the certificate expiration check script periodically:

```bash
# Add to cron for weekly checks
0 9 * * 1 /path/to/aiq/ios/scripts/check_certificate_expiration.sh
```

The script will output:
- Current certificate expiration dates
- Days until expiration
- Warnings if expiration is within 30 days
- Errors if certificates have expired

### Manual Monitoring

Check certificate status at any time:

```bash
./ios/scripts/check_certificate_expiration.sh
```

## Related Documentation

- [CERTIFICATE_PINNING_TESTING.md](./CERTIFICATE_PINNING_TESTING.md) - Testing procedures
- [CODING_STANDARDS.md](./CODING_STANDARDS.md) - Security standards
- [TrustKit.plist](../AIQ/TrustKit.plist) - Configuration file
- [TrustKit Documentation](https://github.com/datatheorem/TrustKit)

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2026-01-14 | Claude | Initial runbook creation |

## Contact

For certificate-related emergencies, contact the on-call engineer via the standard escalation path.
