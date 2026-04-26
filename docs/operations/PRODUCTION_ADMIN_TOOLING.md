# Production Admin Tooling

Production admin API commands should use the backend service variables from
Railway instead of copying `ADMIN_TOKEN` into local `.env` files. The backend
Railway service owns the admin token accepted by
`https://aiq-backend-production.up.railway.app/v1/admin`.

## Data CLI

Run production data checks through `railway run` so `ADMIN_TOKEN` is injected
from the `aiq-backend` production service:

```bash
railway run --service aiq-backend --environment production \
  backend/venv/bin/python backend/cli/aiq_data.py --json --prod sql 'SELECT 1'
```

## LLM Benchmark CLI

Check that the benchmark endpoint accepts the approved production admin token
without starting benchmark runs:

```bash
railway run --service aiq-backend --environment production \
  question-service/venv/bin/python question-service/scripts/benchmark_models.py \
  --auth-check
```

Run live benchmarks the same way, adding the benchmark options you need:

```bash
railway run --service aiq-backend --environment production \
  question-service/venv/bin/python question-service/scripts/benchmark_models.py \
  --runs 1 --question-ids 1,2,3
```
