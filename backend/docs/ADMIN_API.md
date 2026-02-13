# Admin API

The admin API provides endpoints for managing question generation, quality metrics, reliability analysis, and test validity. All admin endpoints are under `/v1/admin/`.

For the full interactive API reference, see [Swagger UI](https://aiq-backend-production.up.railway.app/v1/docs) when the server is running.

## Authentication

Admin endpoints use two types of authentication:

| Auth Type | Header | Use Case |
|-----------|--------|----------|
| **Admin Token** | `X-Admin-Token` | Manual operations (trigger generation, check job status) |
| **Service Key** | `X-Service-Key` | Service-to-service communication (question-service reporting metrics) |

Configure these in your environment:
```bash
ADMIN_TOKEN=your-admin-token-here
SERVICE_API_KEY=your-service-key-here
```

## Submodules

- **Generation**: Question generation job control and run tracking
- **Calibration**: Question difficulty calibration
- **Analytics**: Response time analytics and factor analysis
- **Distractors**: Distractor effectiveness analysis
- **Validity**: Test session validity assessment ([detailed docs](VALIDITY_SYSTEM.md))
- **Config**: Weighted scoring configuration
- **Discrimination**: Item discrimination analysis and quality flags
- **Reliability**: Reliability metrics (Cronbach's alpha, test-retest, split-half)

## Question Generation Control

### `POST /v1/admin/trigger-question-generation`
Manually trigger the question generation job.

**Authentication:** `X-Admin-Token`

**Request Body:**
```json
{
  "count": 50,
  "dry_run": false
}
```

**Example:**
```bash
curl -X POST https://aiq-backend-production.up.railway.app/v1/admin/trigger-question-generation \
  -H "X-Admin-Token: your-admin-token" \
  -H "Content-Type: application/json" \
  -d '{"count": 50, "dry_run": false}'
```

### `GET /v1/admin/question-generation-status/{job_id}`
Check the status of a running question generation job.

**Authentication:** `X-Admin-Token`

## Generation Run Tracking

These endpoints track and analyze question generation service execution metrics.

### `POST /v1/admin/generation-runs`
Create a new generation run record (called by question-service after generation completes).

**Authentication:** `X-Service-Key`

### `GET /v1/admin/generation-runs`
List generation runs with pagination, filtering, and sorting.

**Authentication:** `X-Service-Key`

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `page` | int | Page number (1-indexed, default: 1) |
| `page_size` | int | Items per page (1-100, default: 20) |
| `status` | string | Filter: `running`, `success`, `partial_failure`, `failed` |
| `environment` | string | Filter: `production`, `staging`, `development` |
| `start_date` / `end_date` | datetime | Filter by date range (ISO 8601) |
| `min_success_rate` / `max_success_rate` | float | Filter by success rate (0.0-1.0) |
| `sort_by` | string | `started_at`, `duration_seconds`, `overall_success_rate` |
| `sort_order` | string | `asc` or `desc` (default: `desc`) |

**Example:**
```bash
curl "https://aiq-backend-production.up.railway.app/v1/admin/generation-runs?status=success&page=1&page_size=10" \
  -H "X-Service-Key: your-service-key"
```

### `GET /v1/admin/generation-runs/{run_id}`
Get detailed information for a specific generation run, including computed `pipeline_losses`.

**Authentication:** `X-Service-Key`

**Pipeline Losses:**
- `generation_loss`: Questions that failed during LLM generation
- `evaluation_loss`: Questions not evaluated by judge
- `rejection_loss`: Questions rejected by judge (low quality)
- `deduplication_loss`: Questions removed as duplicates
- `insertion_loss`: Questions that failed database insertion

### `GET /v1/admin/generation-runs/stats`
Get aggregated statistics for generation runs over a time period.

**Authentication:** `X-Service-Key`

**Required Query Parameters:**
- `start_date` (datetime): Start of analysis period (ISO 8601)
- `end_date` (datetime): End of analysis period (ISO 8601)

**Optional:** `environment` (string)

**Trend Indicators:**
- `improving`: Recent runs show higher rates than older runs (>5% difference)
- `declining`: Recent runs show lower rates (>5% difference)
- `stable`: Rate difference within 5%

## Discrimination Analysis

### `GET /v1/admin/questions/discrimination-report`
Comprehensive discrimination quality report for all questions.

**Authentication:** `X-Admin-Token`

**Quality Tiers:**
| Tier | Discrimination Range |
|------|---------------------|
| Excellent | > 0.40 |
| Good | 0.30 - 0.40 |
| Acceptable | 0.20 - 0.30 |
| Poor | 0.10 - 0.20 |
| Very Poor | 0.00 - 0.10 |
| Negative | < 0.00 |

### `GET /v1/admin/questions/{question_id}/discrimination-detail`
Detailed discrimination information for a specific question.

**Authentication:** `X-Admin-Token`

### `PATCH /v1/admin/questions/{question_id}/quality-flag`
Update the quality flag for a question (for admin review workflow).

**Authentication:** `X-Admin-Token`

**Valid quality_flag values:**
- `normal` - Question is in good standing
- `under_review` - Question flagged for review (excluded from tests)
- `deactivated` - Question permanently removed from pool (reason required)

**Notes:**
- Questions with `quality_flag != "normal"` are automatically excluded from test composition
- Questions with negative discrimination are auto-flagged as `under_review` when they reach 50 responses
- Setting `quality_flag = "deactivated"` requires a reason

## Error Responses

All admin endpoints return standard error responses:

| Status Code | Description |
|-------------|-------------|
| 401 | Invalid or missing authentication token/key |
| 404 | Resource not found |
| 500 | Server error or misconfigured authentication |
