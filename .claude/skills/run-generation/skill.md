---
name: run-generation
description: Run the question generation pipeline with optional type and difficulty filters. Generates questions, evaluates with judge, deduplicates, and inserts to database.
allowed-tools: Bash
---

# Run Generation Pipeline

Runs the full question generation pipeline locally using `run_generation.py`.

## Usage

```
/run-generation [--type <type>] [--difficulty <difficulty>] [--count <n>] [--provider-tier <tier>] [--dry-run]
```

## Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--type` | No | all | Question type: `math`, `logic`, `pattern`, `spatial`, `verbal`, `memory` |
| `--difficulty` | No | all | Difficulty level: `easy`, `medium`, `hard` |
| `--count` | No | 50 | Number of questions to generate |
| `--provider-tier` | No | primary | Provider tier: `primary` or `fallback` |
| `--dry-run` | No | false | Generate and evaluate but don't insert to database |

## Implementation

### Step 1: Parse Arguments

Extract the optional arguments from the user's input:
- `--type <type>` or `-t <type>` - maps to `--types <type>`
- `--difficulty <difficulty>` or `-d <difficulty>` - maps to `--difficulties <difficulty>`
- `--count <n>` or `-c <n>` - maps to `--count <n>`
- `--provider-tier <tier>` - maps to `--provider-tier <tier>`
- `--dry-run` - adds `--dry-run` flag

Validate:
- Type must be one of: `math`, `logic`, `pattern`, `spatial`, `verbal`, `memory`
- Difficulty must be one of: `easy`, `medium`, `hard`
- Count must be a positive integer
- Provider tier must be one of: `primary`, `fallback`

### Step 2: Build Command

Construct the command with only the specified arguments:

```bash
cd /Users/mattgioe/aiq/question-service && source venv/bin/activate && export $(grep -v '^#' .env | xargs) && python run_generation.py --async --async-judge --verbose [additional args based on input]
```

**Examples:**

No arguments (generate all types/difficulties):
```bash
cd /Users/mattgioe/aiq/question-service && source venv/bin/activate && export $(grep -v '^#' .env | xargs) && python run_generation.py --count 50 --async --async-judge --verbose
```

With type only:
```bash
cd /Users/mattgioe/aiq/question-service && source venv/bin/activate && export $(grep -v '^#' .env | xargs) && python run_generation.py --types math --count 50 --async --async-judge --verbose
```

With difficulty only:
```bash
cd /Users/mattgioe/aiq/question-service && source venv/bin/activate && export $(grep -v '^#' .env | xargs) && python run_generation.py --difficulties hard --count 50 --async --async-judge --verbose
```

With both:
```bash
cd /Users/mattgioe/aiq/question-service && source venv/bin/activate && export $(grep -v '^#' .env | xargs) && python run_generation.py --types spatial --difficulties easy --count 50 --async --async-judge --verbose
```

With provider tier (fallback):
```bash
cd /Users/mattgioe/aiq/question-service && source venv/bin/activate && export $(grep -v '^#' .env | xargs) && python run_generation.py --provider-tier fallback --count 50 --async --async-judge --verbose
```

With type and provider tier:
```bash
cd /Users/mattgioe/aiq/question-service && source venv/bin/activate && export $(grep -v '^#' .env | xargs) && python run_generation.py --types math --provider-tier fallback --count 50 --async --async-judge --verbose
```

Dry run:
```bash
cd /Users/mattgioe/aiq/question-service && source venv/bin/activate && export $(grep -v '^#' .env | xargs) && python run_generation.py --types math --count 10 --async --async-judge --verbose --dry-run
```

### Step 3: Run and Report

Execute the command and report results including:
- Number of questions generated
- Number approved by judge
- Number unique after deduplication
- Number inserted to database
- Approval rate

## Exit Codes

| Code | Meaning | Action |
|------|---------|--------|
| 0 | Success | All questions generated and inserted |
| 1 | Partial failure | Some questions failed - check logs |
| 2 | Complete failure | No questions generated - check API keys/quotas |
| 3 | Config error | Missing or invalid environment variables |
| 4 | Database error | Cannot connect to database |

## Examples

```
/run-generation
```
Generate 50 questions of all types and difficulties.

```
/run-generation --type math
```
Generate 50 math questions at all difficulty levels.

```
/run-generation --difficulty hard
```
Generate 50 hard questions of all types.

```
/run-generation --type pattern --difficulty easy --count 20
```
Generate 20 easy pattern questions.

```
/run-generation --type spatial --count 30 --dry-run
```
Generate 30 spatial questions without inserting to database (for testing).

```
/run-generation --provider-tier fallback
```
Generate 50 questions using fallback provider models instead of primary.

```
/run-generation --type math --provider-tier fallback --count 20
```
Generate 20 math questions using fallback provider models.

## Requirements

- `question-service/.env` must contain valid API keys (OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.)
- `question-service/venv` must be set up with dependencies installed
- `DATABASE_URL` must be configured in `.env`
