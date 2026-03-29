## Question Service Context

When working on question generation, prompts, or the pipeline, read these docs first:

| Topic | Document |
|-------|----------|
| Sub-type system & gold-standard examples | [docs/SUB_TYPES.md](docs/SUB_TYPES.md) |
| Architecture & pipeline flow | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Judge model selection | [docs/JUDGE_SELECTION.md](docs/JUDGE_SELECTION.md) |
| Configuration reference | [config/README.md](config/README.md) |
| Operations & scheduling | [docs/OPERATIONS.md](docs/OPERATIONS.md) |
| Railway deployment | [docs/RAILWAY_DEPLOYMENT.md](docs/RAILWAY_DEPLOYMENT.md) |

### Key source files

| File | Contains |
|------|----------|
| `app/generation/prompts.py` | Prompt templates, `QUESTION_SUBTYPES`, `GOLD_STANDARD_EXAMPLES`, `GOLD_STANDARD_BY_SUBTYPE`, `build_generation_prompt()` |
| `app/generation/generator.py` | Multi-LLM generation, sub-type selection & rotation, batch chunking |
| `app/evaluation/judge.py` | Question quality evaluation |
| `app/generation/pipeline.py` | End-to-end pipeline orchestration |
| `app/data/models.py` | `GeneratedQuestion`, `EvaluatedQuestion` data models |
| `run_generation.py` | CLI entry point, salvage strategies (answer repair, difficulty reclassification, regeneration) |
| `config/generators.yaml` | Primary/fallback provider routing per question type |
| `config/judges.yaml` | Judge model assignment per question type |

> **Before editing model identifiers in `config/judges.yaml` or `config/generators.yaml`**, run `/refresh-providers` to validate current model names against provider documentation. Model identifiers go stale (e.g., `gemini-3-pro-preview` returning HTTP 400) and `/refresh-providers` will surface the correct names before you edit.

### gioe-libs (shared library)

`gioe-libs` is installed from `github.com/gioe/python-libs`. The AIQ repo's `libs/` directory contains only `__pycache__` — there are no editable source files there. To modify the shared library:

1. Clone or update `git@github.com:gioe/python-libs.git`
2. Make changes, run tests: `PYTHONPATH=/tmp python3 -m pytest /tmp/libs/cron_runner/tests/` (requires the repo cloned as `/tmp/libs`)
3. Commit and push to `main`
4. Reinstall locally: `pip install --force-reinstall git+https://github.com/gioe/python-libs.git`

### Testing & Environment

Always activate the question-service virtualenv (`source venv/bin/activate`) before running tests. `gioe-libs` is installed as a package via `requirements.txt` — no manual `PYTHONPATH` adjustment needed. Never assume import paths — verify them first.

> **mypy enforcement**: Internal utility functions (e.g., `_safe_record_metric`) that delegate to typed facades must use `Literal[...]` for constrained string parameters, not plain `str`. Mypy checks these at pre-commit time — a plain `str` annotation will block commits even for unrelated changes.

### Railway Deployment

- **Config**: `question-service/railway.json` — separate from the root `railway.json` (which is the backend's).
- **Dockerfile**: `question-service/Dockerfile.trigger` — the Railway deployment Dockerfile.
- **PYTHONPATH**: `/app/question-service` inside the container.
- **No healthcheck**: This is a cron/trigger service, not a long-running web server. Do not add a healthcheck path.
- **Watch paths**: `/question-service/**`.
- **Isolation**: Changes to `question-service/railway.json` or its Dockerfiles must NOT affect the backend. They have separate configs. See root CLAUDE.md for the full topology table.
- **Full deployment guide**: [docs/RAILWAY_DEPLOYMENT.md](docs/RAILWAY_DEPLOYMENT.md)
