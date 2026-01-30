# Bootstrap Inventory Script Improvements

## Overview
Enhance the `/Users/mattgioe/aiq/scripts/bootstrap_inventory.sh` script to provide better visibility, error handling, and monitoring during long-running question generation jobs.

## Strategic Context

### Problem Statement
The bootstrap_inventory.sh script orchestrates generation of 900 questions across 18 strata, which can take 30+ minutes. During execution, users face several pain points:

1. **Lack of progress visibility**: All output goes to log files only, creating "black box" syndrome during long runs
2. **Poor error diagnostics**: Exit codes are logged but actual error messages aren't extracted or displayed
3. **Limited observability**: No structured logging for programmatic monitoring
4. **Incomplete metrics**: Partial successes (judge filtering) aren't tracked or reported
5. **No alerting integration**: Failures aren't surfaced to monitoring systems
6. **No heartbeat**: No periodic signals to prove the script is still alive during long jobs

### Success Criteria
- Users can see real-time progress without tailing log files
- Errors surface immediately with actionable context
- Monitoring systems can parse structured output
- Partial success metrics (approval rates, deduplication) are captured
- Critical failures integrate with existing alerting (building on run_generation.py's email alerts)
- Long-running jobs provide periodic heartbeat signals

### Why Now?
This is a bootstrapping-critical script that runs infrequently but with high stakes. Poor visibility during 30-minute runs creates anxiety and wastes time. The underlying run_generation.py already has rich logging and metrics - we just need to surface them in the wrapper.

## Technical Approach

### High-Level Architecture
The solution involves three layers:

1. **Output Streaming Layer**: Tee run_generation.py output to both log file and terminal in real-time
2. **Error Extraction Layer**: Parse run_generation.py logs to extract structured error information
3. **Progress Reporting Layer**: Inject periodic heartbeat and summary messages during generation

Key insight: run_generation.py already writes JSON heartbeats to stdout (lines 105, 141) and logs rich metrics. We can parse these in real-time.

### Key Decisions & Tradeoffs

**Decision 1: Tee vs. Full Duplex Logging**
- **Choice**: Use `tee` to stream output to both terminal and log file
- **Why**: Simple, doesn't require modifying run_generation.py, leverages existing logging
- **Tradeoff**: Can't selectively filter what goes to terminal vs. file, but that's acceptable

**Decision 2: Parse JSONL Heartbeats vs. Custom Protocol**
- **Choice**: Parse existing `HEARTBEAT:` and `SUCCESS_RUN:` JSON lines from run_generation.py
- **Why**: Zero changes to Python code, leverages existing instrumentation
- **Tradeoff**: Slightly more complex parsing, but more maintainable

**Decision 3: In-Script Parsing vs. External Monitor**
- **Choice**: Parse in bash script using `grep` and `jq`
- **Why**: Self-contained, works without additional processes
- **Tradeoff**: Parsing in bash is more fragile, but acceptable for structured JSON

**Decision 4: Alerting Integration Strategy**
- **Choice**: Leverage run_generation.py's existing AlertManager, add wrapper-level alerting for script failures
- **Why**: Separates concerns - Python handles generation errors, bash handles orchestration errors
- **Tradeoff**: Two alerting paths to maintain, but clearer separation

### Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Tee overhead slows generation | Medium | Use unbuffered output (`stdbuf -oL`) to minimize latency |
| Parsing errors crash script | Medium | Use `|| true` on parse attempts, degrade gracefully |
| Heartbeat log size grows unbounded | Low | Write heartbeats to separate temp file, clean up on exit |
| JSON parsing dependency (jq) not installed | Medium | Add preflight check for `jq`, provide clear error if missing |

## Implementation Plan

### Phase 1: Real-Time Progress Visibility
**Goal**: Surface generation progress to terminal in real-time
**Duration**: 2-3 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 1.1 | Add preflight check for `jq` dependency | None | 20 min | Exit with clear error if not installed |
| 1.2 | Modify `generate_type()` to tee output to both log and terminal | 1.1 | 45 min | Use `stdbuf -oL` for unbuffered output |
| 1.3 | Add real-time heartbeat parsing to extract progress signals | 1.2 | 60 min | Parse `HEARTBEAT:` JSON lines, display phase info |
| 1.4 | Test with short run (--count 10 --types math) | 1.3 | 30 min | Verify output appears in real-time |

**Acceptance Criteria**:
- Terminal shows phase transitions (PHASE 1: Generation, PHASE 2: Judge, etc.)
- Users see progress without opening log files
- Full output still captured in log file
- No performance degradation vs. current implementation

### Phase 2: Error Extraction & Summarization
**Goal**: Display actual error messages from run_generation.py failures
**Duration**: 2-3 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 2.1 | Create `extract_last_error()` function to parse log for failures | None | 45 min | Look for `ERROR` lines, exception tracebacks |
| 2.2 | Modify failure handling to call `extract_last_error()` and display | 2.1 | 30 min | Show last 5-10 error lines when type fails |
| 2.3 | Parse structured error from heartbeat JSON if available | 2.2 | 45 min | Check `error_message` field in final heartbeat |
| 2.4 | Test with intentional failures (invalid API key, bad config) | 2.3 | 30 min | Verify error extraction works for common cases |

**Acceptance Criteria**:
- When a type fails, terminal shows actual error message (not just exit code)
- Error summary includes last N log lines with ERROR prefix
- If run_generation.py wrote error to heartbeat, that's surfaced first
- Users don't need to grep log files to understand failures

### Phase 3: Structured Logging
**Goal**: Output JSONL format for monitoring tools
**Duration**: 2-3 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 3.1 | Create `log_event()` function to emit JSONL to dedicated file | None | 30 min | Write to `logs/bootstrap_events.jsonl` |
| 3.2 | Log structured events for script start, type start, type end | 3.1 | 45 min | Include timestamp, type, status, duration |
| 3.3 | Add final summary event with aggregate stats | 3.2 | 30 min | Total duration, success/fail counts, types |
| 3.4 | Document JSONL schema in script header comments | 3.3 | 30 min | Help future monitoring integration |

**Acceptance Criteria**:
- Bootstrap script emits JSONL events to separate file
- Schema includes: timestamp, event_type, status, duration, type, error_message
- Final event includes aggregate statistics
- JSONL file can be parsed by monitoring tools (verified with `jq`)

### Phase 4: Partial Success Tracking
**Goal**: Capture and report judge filtering and deduplication metrics
**Duration**: 3-4 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 4.1 | Parse `SUCCESS_RUN:` JSON from run_generation.py output | None | 45 min | Extract questions_generated, questions_inserted, approval_rate |
| 4.2 | Store per-type metrics in temp files during generation | 4.1 | 60 min | Write to `$RESULTS_DIR/{type}_metrics.json` |
| 4.3 | Enhance summary to show approval rates per type | 4.2 | 45 min | Display "math: 150 generated, 120 approved (80%), 118 inserted" |
| 4.4 | Add warning if approval rate < 70% for any type | 4.3 | 30 min | Suggest reviewing judge config or prompts |

**Acceptance Criteria**:
- Summary shows per-type breakdown: generated, approved, inserted
- Approval rate % displayed for each type
- Deduplication impact visible (approved vs. inserted delta)
- Warning displayed if approval rate below threshold (70%)

### Phase 5: Alerting Integration
**Goal**: Surface critical failures to monitoring systems
**Duration**: 2-3 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 5.1 | Add `--alerting-config` parameter to pass through to run_generation.py | None | 20 min | Default to `./config/alerting.yaml` |
| 5.2 | Create wrapper alerting function for script-level failures | 5.1 | 60 min | Call if multiple types fail, or script crashes |
| 5.3 | Write sentinel file for monitoring systems on complete failure | 5.2 | 30 min | e.g., `logs/bootstrap_failure.flag` |
| 5.4 | Test alerting with intentional multi-type failure | 5.3 | 30 min | Verify alert triggers only for critical failures |

**Acceptance Criteria**:
- Script-level alerting only fires for critical failures (e.g., 3+ types failed)
- Generation-level errors handled by run_generation.py's existing AlertManager
- Sentinel file written for external monitoring to detect failures
- No duplicate alerts when both systems trigger

### Phase 6: Heartbeat for Long Runs
**Goal**: Provide periodic "still running" signals during 30+ minute jobs
**Duration**: 2 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 6.1 | Add background heartbeat loop to emit periodic status | None | 60 min | Every 60s, echo status to terminal and JSONL |
| 6.2 | Include current type, elapsed time, estimated completion | 6.1 | 30 min | Display "Running math (2/6, 8m elapsed, ~24m remaining)" |
| 6.3 | Stop heartbeat loop cleanly when type completes | 6.2 | 20 min | Use trap to kill background job |
| 6.4 | Test with long run (--count 150 --types pattern,logic) | 6.3 | 20 min | Verify heartbeat appears every 60s |

**Acceptance Criteria**:
- Terminal shows heartbeat message every 60 seconds during generation
- Heartbeat includes current progress (type X of N) and elapsed time
- Heartbeat stops cleanly when type completes (no zombie processes)
- Heartbeat doesn't interfere with real-time output from run_generation.py

## Open Questions

1. **Should we add a `--quiet` flag to suppress real-time output?**
   - Some users may prefer the current "silent until done" behavior
   - Could default to verbose, offer `--quiet` to restore old behavior

2. **What's the right heartbeat interval?**
   - 60s seems reasonable for 30-minute jobs
   - Should it be configurable via CLI flag?

3. **Should we integrate with Sentry for script-level errors?**
   - run_generation.py already uses Sentry (recent PR #802)
   - Could send bootstrap script errors to same Sentry project

4. **Should summary include cost estimates?**
   - run_generation.py tracks API usage
   - Could parse and display estimated cost per type

## Appendix

### Example Output (Current)
```bash
[1/6] Generating math (150 questions)... done (245s)
[2/6] Generating logic (150 questions)... FAILED (89s)
  Attempt 1 failed (exit code: 1)
  Retry 1/3
  Attempt 2 failed (exit code: 1)
  Retry 2/3
  Attempt 3 failed (exit code: 1)

================================================================
                     BOOTSTRAP SUMMARY
================================================================

Results:
  Successful types: 1 / 6
  Failed types: 5
  Total duration: 8m 23s

Type Details:
  [OK] math
  [FAILED] logic
  ...
```

### Example Output (After Phase 1 & 2)
```bash
[1/6] Generating math (150 questions)...
PHASE 1: Question Generation
  Generated: 150/150 questions (100% success rate)
PHASE 2: Judge Evaluation
  Approved: 122/150 (81.3%)
PHASE 3: Deduplication
  Unique: 118/122
PHASE 4: Database Insertion
  Inserted: 118/118
done (245s)

[2/6] Generating logic (150 questions)...
PHASE 1: Question Generation
  Generated: 85/150 questions (56.7% success rate)
ERROR: Rate limit exceeded for provider gpt-4o
  Provider: openai
  Retryable: true
  Quota resets: 2026-01-25 14:30:00 UTC

  Attempt 1 failed (exit code: 5)

Last errors from log:
  ERROR [openai] Rate limit exceeded (quota)
  ERROR Failed to generate questions: BILLING_ERROR
  ERROR See https://platform.openai.com/usage for quota details

Retry 1/3
  ...
```

### Example JSONL Output (After Phase 3)
```jsonl
{"timestamp":"2026-01-25T13:00:00Z","event":"script_start","total_types":6,"target_per_type":150}
{"timestamp":"2026-01-25T13:00:05Z","event":"type_start","type":"math","attempt":1}
{"timestamp":"2026-01-25T13:04:10Z","event":"type_end","type":"math","status":"success","duration_seconds":245,"generated":150,"approved":122,"inserted":118,"approval_rate":81.3}
{"timestamp":"2026-01-25T13:04:15Z","event":"type_start","type":"logic","attempt":1}
{"timestamp":"2026-01-25T13:05:44Z","event":"type_end","type":"logic","status":"failed","duration_seconds":89,"exit_code":5,"error":"Rate limit exceeded"}
{"timestamp":"2026-01-25T13:12:15Z","event":"script_end","status":"partial_failure","total_duration_seconds":735,"successful_types":1,"failed_types":5}
```

### Related Files
- `/Users/mattgioe/aiq/scripts/bootstrap_inventory.sh` - Target file for improvements
- `/Users/mattgioe/aiq/question-service/run_generation.py` - Underlying generation script
- `/Users/mattgioe/aiq/question-service/app/alerting.py` - Existing alert infrastructure
- `/Users/mattgioe/aiq/question-service/app/metrics.py` - Metrics tracking system
- `/Users/mattgioe/aiq/config/alerting.yaml` - Alerting configuration (if exists)
