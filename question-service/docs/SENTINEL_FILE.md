# Bootstrap Failure Sentinel File

The `BootstrapAlerter` class (`scripts/bootstrap_inventory.py`) writes a JSON sentinel file when a critical number of question types fail during bootstrap generation. External monitoring tools can poll for this file's existence or modification time to detect failures without parsing logs.

## Path Resolution

The sentinel file path is resolved in priority order:

| Priority | Source | Example |
|----------|--------|---------|
| 1 | `failure_flag_path` constructor parameter | `/var/log/aiq/bootstrap_failure.flag` |
| 2 | `BOOTSTRAP_FAILURE_FLAG_PATH` environment variable | Set via Railway or systemd |
| 3 | Default: `{log_dir}/bootstrap_failure.flag` | `logs/bootstrap_failure.flag` |

The parent directory is created automatically if it does not exist.

## JSON Schema

```json
{
  "timestamp": "2026-02-10T14:30:00.000000+00:00",
  "failed_count": 4,
  "failed_types": ["pattern", "logic", "spatial", "math"],
  "threshold": 3,
  "error_sample": "Rate limit exceeded for model gpt-4o..."
}
```

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | string | ISO-8601 UTC timestamp of the failure (`datetime.now(timezone.utc).isoformat()`) |
| `failed_count` | integer | Number of question types that failed during the bootstrap run |
| `failed_types` | array of strings | Names of the failed question types (e.g., `["pattern", "logic", "spatial"]`) |
| `threshold` | integer | The `CRITICAL_FAILURE_THRESHOLD` value that triggered the sentinel write (default: 3) |
| `error_sample` | string or null | First error message from the failed types, sanitized to remove API keys and truncated to 200 characters. Null if no error message was captured. |

## When Written

The sentinel file is written when **all** of the following conditions are met:

1. `failed_count >= CRITICAL_FAILURE_THRESHOLD` (default: 3)
2. No alert has already been sent for the current bootstrap run (`_alert_sent` flag)

Behavior details:

- **One file per run**: The file is overwritten (not appended) on each critical failure, using `open(path, "w")`.
- **Sanitized content**: Error messages are processed through `_sanitize_error()` to redact API keys, tokens, and other sensitive data before writing.
- **Truncation**: The `error_sample` field is truncated to a maximum of 200 characters.
- **Write failures are non-fatal**: If the file cannot be written (IOError/OSError), the error is logged but does not prevent the alert from being sent via `AlertManager`.

## Monitoring Integration

External monitoring tools can integrate with the sentinel file in several ways:

| Approach | Description |
|----------|-------------|
| File existence check | Poll for the file's existence to detect any critical failure |
| Modification time check | Compare `mtime` against a known-good baseline to detect new failures |
| JSON parsing | Read `failed_count` and `failed_types` for detailed failure information |
| Timestamp comparison | Parse the `timestamp` field to determine failure recency |

The bash script (`question-service/scripts/bootstrap_inventory.sh`) contains equivalent failure-detection logic via `send_multi_type_failure_alert()`. Both the Python and bash implementations use the same `CRITICAL_FAILURE_THRESHOLD` of 3 failed types.
