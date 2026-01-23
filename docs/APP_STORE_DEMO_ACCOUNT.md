# App Store Review Demo Account

This document contains credentials and instructions for the Apple App Store Review demo account.

## Account Credentials

| Field | Value |
|-------|-------|
| **Email** | `demo-reviewer@aiq-app.com` |
| **Password** | *Stored in 1Password under "AIQ App Store Demo Account"* |
| **Account Marker** | `APP_STORE_REVIEW_DEMO` |

> **SECURITY NOTE**: The password is stored securely in 1Password. Never commit credentials to source control.

## Account Details

- **User ID**: 2
- **Created**: 2026-01-23
- **Status**: Active with test history

## Test History

The demo account has pre-populated test history to demonstrate the app's cognitive tracking features:

| Test Date | IQ Score | Percentile | Questions | Accuracy |
|-----------|----------|------------|-----------|----------|
| 2025-05-28 | 112 | 79th | 20 | 65% |
| 2025-11-24 | 115 | 84th | 20 | 70% |

This shows a 3-point improvement over ~6 months, demonstrating the app's ability to track cognitive trends.

## App Store Connect Instructions

When submitting the app for review, add these credentials to App Store Connect:

1. Go to **App Store Connect** > **My Apps** > **AIQ**
2. Click **App Information** in the sidebar
3. Scroll to **App Review Information**
4. Under **Sign-in Information**, enter:
   - **User name**: `demo-reviewer@aiq-app.com`
   - **Password**: *Retrieve from 1Password "AIQ App Store Demo Account"*
5. In **Notes for Review**, add:

```
Demo Account Instructions:

This demo account has been pre-configured with test history to demonstrate the app's features:

1. Login with the provided credentials
2. View the Dashboard to see IQ trend visualization
3. Navigate to History to see past test results
4. Review Profile settings

Note: This account has completed tests and cannot take a new test due to the 6-month cadence restriction. This is working as designed - users can only take one test every 6 months to ensure meaningful cognitive tracking.

For a fresh account to test the full test-taking flow, please register a new account in the app.
```

## Account Protection

This account is marked with `APP_STORE_REVIEW_DEMO` in the database to:
- Prevent accidental deletion
- Identify it in analytics/monitoring
- Enable special handling if needed

### Database Marker

The account's test sessions contain a marker in `composition_metadata`:
```json
{"strategy": "demo_account", "marker": "APP_STORE_REVIEW_DEMO"}
```

### Do Not Delete

This account should NOT be deleted from production. If cleanup is needed:
1. Check for the `APP_STORE_REVIEW_DEMO` marker
2. Verify this is not the active review account
3. Create a new demo account before deleting

## Re-creating the Account

If the account needs to be recreated:

1. **Create the user via API**:
   ```bash
   # Replace <PASSWORD> with the actual password from 1Password
   curl -X POST "https://aiq-backend-production.up.railway.app/v1/auth/register" \
     -H "Content-Type: application/json" \
     -d '{"email":"demo-reviewer@aiq-app.com","password":"<PASSWORD>","first_name":"App Store","last_name":"Reviewer","birth_year":1990,"education_level":"bachelors","country":"United States","region":"California"}'
   ```

2. **Populate test history**:
   ```bash
   # From backend directory
   railway connect postgres < scripts/populate_demo_history.sql
   ```

   Or run the Python script:
   ```bash
   DATABASE_URL="..." python scripts/create_demo_account.py
   ```

## Troubleshooting

### Login Fails
- Verify the account exists: Check users table for email `demo-reviewer@aiq-app.com`
- Password is case-sensitive: `DemoReview2026!Aiq`

### No Test History Visible
- Run `scripts/populate_demo_history.sql` against production database
- Verify `test_results` table has entries for user_id 2

### Account Locked/Rate Limited
- Login endpoint has rate limiting (5 attempts per 5 minutes)
- Wait 5 minutes and try again, or check Railway logs

## Related Files

- `backend/scripts/create_demo_account.py` - Python script for automated setup
- `backend/scripts/populate_demo_history.sql` - SQL for adding test history
