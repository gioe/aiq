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
| `app/prompts.py` | Prompt templates, `QUESTION_SUBTYPES`, `GOLD_STANDARD_EXAMPLES`, `GOLD_STANDARD_BY_SUBTYPE`, `build_generation_prompt()` |
| `app/generator.py` | Multi-LLM generation, sub-type selection & rotation, batch chunking |
| `app/judge.py` | Question quality evaluation |
| `app/pipeline.py` | End-to-end pipeline orchestration |
| `app/models.py` | `GeneratedQuestion`, `EvaluatedQuestion` data models |
| `run_generation.py` | CLI entry point, salvage strategies (answer repair, difficulty reclassification, regeneration) |
| `config/generators.yaml` | Primary/fallback provider routing per question type |
| `config/judges.yaml` | Judge model assignment per question type |
