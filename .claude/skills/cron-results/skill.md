---
name: cron-results
description: Display a formatted summary of the latest question generation run from production, including pipeline funnel, quality metrics, and breakdowns by type, difficulty, and provider.
allowed-tools: Bash
---

# Cron Results Skill

Fetches the latest question generation run from the production Railway backend and prints a human-readable summary.

## Usage

```
/cron-results
```

## Implementation

Run this bash script to fetch and display the latest generation run:

```bash
set -a && source backend/.env && set +a

BASE_URL="https://aiq-backend-production.up.railway.app"

if [ -z "$SERVICE_API_KEY" ]; then
  echo "ERROR: SERVICE_API_KEY not found in backend/.env"
  exit 1
fi

# Fetch latest run summary
LIST_RESPONSE=$(curl -sf \
  -H "X-Service-Key: $SERVICE_API_KEY" \
  "$BASE_URL/v1/admin/generation-runs?page=1&page_size=1&sort_by=started_at&sort_order=desc" \
  2>&1)

if [ $? -ne 0 ]; then
  echo "ERROR: Failed to reach production API."
  echo "$LIST_RESPONSE"
  exit 1
fi

TOTAL=$(echo "$LIST_RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('total',0))")

if [ "$TOTAL" = "0" ] || [ -z "$TOTAL" ]; then
  echo "No runs recorded yet."
  exit 0
fi

RUN_ID=$(echo "$LIST_RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['runs'][0]['id'])")

# Fetch full detail
DETAIL=$(curl -sf \
  -H "X-Service-Key: $SERVICE_API_KEY" \
  "$BASE_URL/v1/admin/generation-runs/$RUN_ID" \
  2>&1)

if [ $? -ne 0 ]; then
  echo "ERROR: Failed to fetch run detail for run $RUN_ID."
  echo "$DETAIL"
  exit 1
fi

# Render formatted output
echo "$DETAIL" | python3 -c "
import sys, json
from datetime import datetime, timezone

d = json.load(sys.stdin)

def fmt_dt(s):
    if not s:
        return 'N/A'
    try:
        dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M UTC')
    except Exception:
        return s

def pct(v):
    if v is None:
        return 'N/A'
    return f'{v * 100:.1f}%'

def num(v, default=0):
    return v if v is not None else default

# Header
print()
print('=' * 70)
print(f'  Generation Run #{d[\"id\"]}  |  {d[\"status\"].upper()}  |  {fmt_dt(d[\"started_at\"])}')
print('=' * 70)

# Timing
dur = d.get('duration_seconds')
if dur is not None:
    mins, secs = divmod(int(dur), 60)
    print(f'  Duration       : {mins}m {secs}s')
print(f'  Environment    : {d.get(\"environment\") or \"N/A\"}')
print(f'  Triggered by   : {d.get(\"triggered_by\") or \"N/A\"}')
print(f'  Exit code      : {d.get(\"exit_code\") if d.get(\"exit_code\") is not None else \"N/A\"}')
print()

# Pipeline funnel
pl = d.get('pipeline_losses', {})
req  = num(d.get('questions_requested'))
gen  = num(d.get('questions_generated'))
evl  = num(d.get('questions_evaluated'))
appr = num(d.get('questions_approved'))
dup  = num(d.get('duplicates_found'))
ins  = num(d.get('questions_inserted'))

print('Pipeline Funnel')
print('-' * 70)
print(f'  Requested      : {req:>6}')
print(f'  Generated      : {gen:>6}   (loss: {num(pl.get(\"generation_loss\"))}, {pct(pl.get(\"generation_loss_pct\"))})')
print(f'  Evaluated      : {evl:>6}   (loss: {num(pl.get(\"evaluation_loss\"))})')
print(f'  Approved       : {appr:>6}   (loss: {num(pl.get(\"rejection_loss\"))}, rejection rate: {pct(1 - d[\"approval_rate\"] if d.get(\"approval_rate\") is not None else None)})')
print(f'  Deduped out    : {dup:>6}')
print(f'  Inserted       : {ins:>6}   (loss: {num(pl.get(\"insertion_loss\"))})')
print()

# Quality metrics
print('Quality Metrics')
print('-' * 70)
print(f'  Approval rate  : {pct(d.get(\"approval_rate\"))}')
avg_j = d.get(\"avg_judge_score\")
min_j = d.get(\"min_judge_score\")
max_j = d.get(\"max_judge_score\")
if avg_j is not None:
    print(f'  Avg judge score: {avg_j:.2f}  (min: {min_j:.2f}, max: {max_j:.2f})')
else:
    print(f'  Avg judge score: N/A')
print(f'  Duplicate rate : {pct(d.get(\"duplicate_rate\"))}')
print(f'    Exact dups   : {num(d.get(\"exact_duplicates\"))}')
print(f'    Semantic dups: {num(d.get(\"semantic_duplicates\"))}')
print(f'  Total API calls: {num(d.get(\"total_api_calls\"))}')
print(f'  Total errors   : {num(d.get(\"total_errors\"))}')
print()

# Type breakdown
tm = d.get('type_metrics')
if tm:
    print('By Question Type')
    print('-' * 70)
    for qtype, count in sorted(tm.items(), key=lambda x: -x[1]):
        bar = '#' * min(count, 40)
        print(f'  {qtype:<20} {count:>4}  {bar}')
    print()

# Difficulty breakdown
dm = d.get('difficulty_metrics')
if dm:
    print('By Difficulty')
    print('-' * 70)
    for diff in ['easy', 'medium', 'hard']:
        count = dm.get(diff, 0)
        bar = '#' * min(count, 40)
        print(f'  {diff:<20} {count:>4}  {bar}')
    print()

# Provider breakdown
pm = d.get('provider_metrics')
if pm:
    print('By Provider')
    print('-' * 70)
    for provider, metrics in sorted(pm.items()):
        gen_count = metrics.get('generated', 0)
        calls = metrics.get('api_calls', 0)
        failures = metrics.get('failures', 0)
        print(f'  {provider:<20}  generated: {gen_count:>4}  api_calls: {calls:>4}  failures: {failures:>3}')
    print()

# Error summary
es = d.get('error_summary')
if es and (es.get('by_category') or es.get('critical_count', 0) > 0):
    print('Error Summary')
    print('-' * 70)
    print(f'  Critical count : {es.get(\"critical_count\", 0)}')
    by_cat = es.get('by_category', {})
    if by_cat:
        for cat, cnt in sorted(by_cat.items(), key=lambda x: -x[1]):
            print(f'  {cat:<20} : {cnt}')
    by_sev = es.get('by_severity', {})
    if by_sev:
        print('  By severity:')
        for sev, cnt in sorted(by_sev.items(), key=lambda x: -x[1]):
            print(f'    {sev:<18} : {cnt}')
    print()
"
```

## Output Format

```
======================================================================
  Generation Run #42  |  SUCCESS  |  2026-03-20 04:00 UTC
======================================================================
  Duration       : 12m 34s
  Environment    : production
  Triggered by   : scheduler
  Exit code      : 0

Pipeline Funnel
----------------------------------------------------------------------
  Requested      :    300
  Generated      :    280   (loss: 20, 6.7%)
  Evaluated      :    280   (loss: 0)
  Approved       :    238   (loss: 42, rejection rate: 15.0%)
  Deduped out    :     18
  Inserted       :    220   (loss: 0)

Quality Metrics
----------------------------------------------------------------------
  Approval rate  : 85.0%
  Avg judge score: 7.82  (min: 5.10, max: 9.90)
  Duplicate rate : 7.6%
    Exact dups   :  8
    Semantic dups: 10
  Total API calls:  460
  Total errors   :    3

By Question Type
----------------------------------------------------------------------
  math                   48  ################################################
  logic                  42  ##########################################
  ...

By Difficulty
----------------------------------------------------------------------
  easy                   75  ###########################################################################
  medium                 92  ####...
  hard                   53  ...

By Provider
----------------------------------------------------------------------
  anthropic              generated:   85  api_calls:  120  failures:   2
  google                 generated:  135  api_calls:  180  failures:   1
```

## Error Handling

- **SERVICE_API_KEY missing**: Prints error message and exits
- **API unreachable**: Prints curl error and exits
- **No runs yet**: Prints `No runs recorded yet.` and exits
- **Null metric sections** (type_metrics, difficulty_metrics, provider_metrics): Sections are omitted when fields are null
- **Error summary absent or empty**: Error section is omitted

## Requirements

- `backend/.env` must contain `SERVICE_API_KEY`
- Internet access to reach `https://aiq-backend-production.up.railway.app`
- `python3` available in shell (standard on macOS)
- `curl` available in shell (standard on macOS)
