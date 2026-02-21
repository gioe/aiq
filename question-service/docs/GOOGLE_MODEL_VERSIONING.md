# Google Gemini Model Version Monitoring Strategy

This document describes the strategy for monitoring and managing Google Gemini model version transitions, with particular focus on preview models that may be promoted to stable or deprecated.

## Table of Contents

- [Overview](#overview)
- [Current Model Usage](#current-model-usage)
- [Preview vs Stable Models](#preview-vs-stable-models)
- [Monitoring Strategy](#monitoring-strategy)
- [Version Transition Playbook](#version-transition-playbook)
- [Test Maintenance](#test-maintenance)
- [Alert Configuration](#alert-configuration)

## Overview

The AIQ question service uses Google Gemini models for pattern recognition and spatial reasoning tasks. As of January 2026, we use preview versions of Gemini 3 models (`gemini-3-pro-preview`, `gemini-3-flash-preview`) because stable versions have not yet been released.

**Risk:** When Google promotes these models to stable or deprecates preview endpoints, our tests and production configurations may fail.

**Mitigation:** This document outlines a monitoring and response strategy to handle model version transitions proactively.

## Current Model Usage

### Production Configuration

| Component | Role | Model | File |
|-----------|------|-------|------|
| Memory Generator | primary | `gemini-3-pro-preview` | `config/generators.yaml` |
| Spatial Generator | fallback | `gemini-3-pro-preview` | `config/generators.yaml` |
| Memory Judge | primary | `gemini-3-pro-preview` | `config/judges.yaml` |
| Spatial Judge | fallback | `gemini-3-pro-preview` | `config/judges.yaml` |

### Code References

| File | Purpose |
|------|---------|
| `app/providers/google_provider.py` | Provider implementation with `fetch_available_models()` for API queries |
| `tests/integration/test_google_integration.py` | Integration tests using preview models |
| `tests/providers/test_provider_model_availability_integration.py` | Model availability validation |

**Note:** `GoogleProvider` has two model-related methods:
- `get_available_models()` - Returns a static hardcoded list of known models
- `fetch_available_models()` - Queries the Google API for currently available models (use this for monitoring)

## Preview vs Stable Models

Google follows a consistent naming convention for Gemini models:

| Phase | Naming Pattern | Example | Characteristics |
|-------|----------------|---------|-----------------|
| Preview | `gemini-{version}-{variant}-preview` | `gemini-3-pro-preview` | API may change, early access |
| Stable | `gemini-{version}-{variant}` | `gemini-2.5-pro` | Frozen API, production-ready |

### Transition Timeline (Typical)

Based on historical patterns with Gemini 2.0 and 2.5:

1. **Preview Launch:** Model released with `-preview` suffix
2. **Stabilization:** 2-4 months of preview availability
3. **GA Announcement:** Google announces stable release via blog/changelog
4. **Grace Period:** Both endpoints typically work for 30-90 days
5. **Deprecation:** Preview endpoint returns errors or redirects

## Monitoring Strategy

### 1. Automated Model Availability Checks

The `GoogleProvider.fetch_available_models()` method queries the Google API for currently available models. Use this in CI to detect model changes.

**Weekly CI Job (Recommended):**

```yaml
# .github/workflows/model-availability-check.yml
name: Model Availability Check
on:
  schedule:
    - cron: '0 9 * * 1'  # Every Monday at 9 AM UTC
  workflow_dispatch:

jobs:
  check-models:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.13'
      - name: Install dependencies
        run: |
          cd question-service
          pip install -r requirements.txt
      - name: Check model availability
        env:
          GOOGLE_API_KEY: ${{ secrets.GOOGLE_API_KEY }}
        run: |
          cd question-service
          python -c "
          from app.providers.google_provider import GoogleProvider
          import os, yaml

          provider = GoogleProvider(api_key=os.environ['GOOGLE_API_KEY'])
          available = set(provider.fetch_available_models())

          # Collect all Google models from config files dynamically.
          # Note: default_generator / default_judge entries are not checked
          # here; they currently use OpenAI, not Google.
          google_models = set()
          for config_path in ['config/generators.yaml', 'config/judges.yaml']:
              with open(config_path) as f:
                  config = yaml.safe_load(f)
              entries = config.get('generators', config.get('judges', {}))
              for entry in entries.values():
                  if not isinstance(entry, dict):
                      continue
                  if entry.get('provider') == 'google':
                      if model := entry.get('model'):
                          google_models.add(model)
                  if entry.get('fallback') == 'google':
                      if fallback_model := entry.get('fallback_model'):
                          google_models.add(fallback_model)

          assert google_models, 'No Google models found in configs — check key names'

          missing = [m for m in google_models if m not in available]

          if missing:
              print(f'WARNING: Missing expected models: {missing}')
              print(f'Available models: {sorted(available)}')
              exit(1)

          # Check for new stable versions (indicates transition)
          new_stable = [m for m in available if m.startswith('gemini-3') and 'preview' not in m]
          if new_stable:
              print(f'NOTICE: New stable Gemini 3 models detected: {new_stable}')
              print('Consider updating configurations to use stable versions.')

          print(f'All {len(google_models)} configured Google models available.')
          "
```

### 2. Google AI Changelog Monitoring

Subscribe to Google AI announcements for model updates:

- **Blog:** https://blog.google/technology/ai/
- **Changelog:** https://ai.google.dev/gemini-api/docs/changelog
- **Release Notes:** https://cloud.google.com/vertex-ai/docs/release-notes

**Manual Check Cadence:** Weekly review of changelog during team standup.

### 3. Integration Test Failure Alerts

Integration tests (`test_google_integration.py`) will fail when models become unavailable. Configure CI to notify the team immediately on failures:

```yaml
# In existing CI workflow
- name: Notify on Google integration test failure
  if: failure()
  uses: actions/github-script@v7
  with:
    script: |
      github.rest.issues.create({
        owner: context.repo.owner,
        repo: context.repo.repo,
        title: 'Google Integration Tests Failing - Possible Model Deprecation',
        body: 'Integration tests for Google provider failed. This may indicate model version changes. See: https://ai.google.dev/gemini-api/docs/changelog',
        labels: ['bug', 'provider-google', 'urgent']
      })
```

## Version Transition Playbook

When a model version transition is detected (either through monitoring or test failures), follow this playbook:

### Step 1: Assess the Situation

1. Check Google's changelog for announcements
2. Run `fetch_available_models()` to see current API state
3. Determine if this is:
   - **Deprecation:** Preview model removed, stable version available
   - **Sunset:** Model family being retired entirely
   - **Temporary outage:** Check Google Cloud status page

### Step 2: Update Configuration

If stable version is available:

1. Update `config/generators.yaml`:
   ```yaml
   pattern:
     model: "gemini-3-pro"  # Remove -preview suffix
   ```

2. Update `config/judges.yaml`:
   ```yaml
   pattern:
     model: "gemini-3-pro"  # Remove -preview suffix
   ```

3. Update `app/providers/google_provider.py`:
   ```python
   def get_available_models(self) -> list[str]:
       return [
           "gemini-3-pro",        # Updated from preview
           "gemini-3-flash",      # Updated from preview
           "gemini-2.5-pro",
           ...
       ]
   ```

### Step 3: Update Tests

1. Update test files to use new model identifiers
2. Run integration tests to verify:
   ```bash
   cd question-service
   pytest tests/integration/test_google_integration.py -m integration --run-integration
   ```

### Step 4: Deploy and Verify

1. Create PR with all changes
2. Verify CI passes
3. Deploy to production
4. Monitor generation runs for errors

### Step 5: Documentation Update

1. Update this document with new model versions
2. Update `PERFORMANCE.md` if benchmark data changes
3. Update `../../docs/MODEL_BENCHMARKS.md` if applicable (located in repo root)

## Test Maintenance

### Current Test Coverage

The following tests validate Gemini 3 preview models:

| Test File | Test Name | Model |
|-----------|-----------|-------|
| `test_google_integration.py` | `test_gemini_3_pro_preview_text_completion` | `gemini-3-pro-preview` |
| `test_google_integration.py` | `test_gemini_3_flash_preview_text_completion` | `gemini-3-flash-preview` |
| `test_google_integration.py` | `test_gemini_3_pro_preview_structured_completion` | `gemini-3-pro-preview` |
| `test_google_integration.py` | `test_gemini_3_flash_preview_structured_completion` | `gemini-3-flash-preview` |
| `test_google_integration.py` | `test_gemini_3_pro_preview_token_usage` | `gemini-3-pro-preview` |
| `test_google_integration.py` | `test_gemini_3_flash_preview_token_usage` | `gemini-3-flash-preview` |
| `test_google_integration.py` | `test_gemini_3_pro_preview_async_completion` | `gemini-3-pro-preview` |
| `test_google_integration.py` | `test_gemini_3_flash_preview_async_completion` | `gemini-3-flash-preview` |
| `test_google_integration.py` | `test_gemini_3_pro_preview_async_structured_completion` | `gemini-3-pro-preview` |
| `test_google_integration.py` | `test_gemini_3_flash_preview_async_structured_completion` | `gemini-3-flash-preview` |
| `test_provider_model_availability_integration.py` | Various | All configured models |

### Test Update Checklist

When updating model versions:

- [ ] Update model identifiers in all test files
- [ ] Verify test assertions match new model behavior
- [ ] Run full integration test suite
- [ ] Update test docstrings to reflect new model names

## Alert Configuration

### Recommended Alerts

| Alert | Trigger | Severity | Response |
|-------|---------|----------|----------|
| Integration test failure | Any Google test fails in CI | High | Follow Version Transition Playbook |
| Model availability warning | Weekly check finds missing model | Medium | Investigate within 24 hours |
| New stable model detected | Weekly check finds new stable Gemini 3 | Low | Plan migration within 2 weeks |
| Google API errors spike | >10% error rate from Google provider | High | Check Google Cloud status, consider fallback |

### Integration with Existing Alerting

See `ALERTING.md` for integration with the existing alerting infrastructure.

---

*Last updated: 2026-01-25*
*Document version: 1.0*
