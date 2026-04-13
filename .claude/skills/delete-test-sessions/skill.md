---
name: delete-test-sessions
description: Delete test sessions for a user by email via the admin API. Dry-run preview by default, --execute to delete.
allowed-tools: Bash
---

# Delete Test Sessions Skill

Wraps the `DELETE /v1/admin/sessions/by-email/{email}` endpoint to delete test sessions for a user.

## Usage

```
/delete-test-sessions <email> [--session-id <N>] [--execute]
```

## Arguments

Parse the user's args string for:
- `<email>` — required, the user's email address (positional, first non-flag argument)
- `--session-id <N>` — optional, scope deletion to a single session ID
- `--execute` — perform the actual deletion. Without this flag, the command runs in **dry-run** mode (preview only)

## Implementation

1. Load the admin token and API base URL from the backend `.env` file:

```bash
cd backend && set -a && source .env && set +a
```

The required variables are:
- `ADMIN_TOKEN` — sent as the `X-Admin-Token` header
- API base URL: `https://aiq-backend-production.up.railway.app`

2. Build and execute the curl command:

```bash
# Determine dry_run query param
# Default: dry_run=true (preview)
# If --execute was passed: dry_run=false

DRY_RUN="true"
# Set DRY_RUN="false" if --execute flag is present

# Build URL
URL="https://aiq-backend-production.up.railway.app/v1/admin/sessions/by-email/<email>?dry_run=${DRY_RUN}"

# If --session-id N was passed, append: &session_id=N
# URL="${URL}&session_id=<N>"

curl -s -w "\n%{http_code}" \
  -X DELETE \
  -H "X-Admin-Token: ${ADMIN_TOKEN}" \
  "${URL}"
```

3. Parse the response. The last line of output is the HTTP status code. Everything before it is the JSON body.

## Output

### Success (HTTP 200)

Print a concise summary from the JSON response:

**Dry-run mode:**
```
Dry-run preview for <email> (user_id: <user_id>):
  Sessions: <sessions_deleted>
  Responses: <total_responses>
  User questions: <total_user_questions>
  Test results: <total_test_results>
  Session IDs: [<session_ids>]

To delete, run: /delete-test-sessions <email> --execute
```

**Execute mode:**
```
Deleted <sessions_deleted> session(s) for <email> (user_id: <user_id>):
  Responses removed: <total_responses>
  User questions removed: <total_user_questions>
  Test results removed: <total_test_results>
  Session IDs: [<session_ids>]
```

### Error (HTTP 404)

```
User not found: <email>
```

Or if `--session-id` was used and the session wasn't found:

```
Session <N> not found for user <email>
```

### Error (HTTP 401/403)

```
Authentication failed. Check ADMIN_TOKEN in backend/.env
```

### Other errors

Print the raw status code and response body.
