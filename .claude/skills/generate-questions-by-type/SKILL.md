---
name: generate-questions-by-type
description: Generate questions of a specific type using the local question-service. Supports type filtering, count, and difficulty options for targeted question generation.
allowed-tools: Bash
---

# Generate Questions by Type

Generate IQ test questions of a specific type using the local question-service.

## Usage

```
/generate-questions-by-type <type> [count] [difficulty]
```

## Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `type` | Yes | - | Question type: `math`, `logic`, `pattern`, `spatial`, `verbal`, `memory` |
| `count` | No | 50 | Number of questions to generate |
| `difficulty` | No | all | Difficulty level: `easy`, `medium`, `hard` |

## Valid Question Types

- `math` - Mathematical reasoning and calculations
- `logic` - Logical deduction and reasoning
- `pattern` - Pattern recognition and sequences
- `spatial` - Spatial reasoning and visualization
- `verbal` - Verbal reasoning and language
- `memory` - Memory and recall tasks

## Prerequisites

Before using this skill, ensure the following requirements are met:

1. **Working Directory**: This skill must be invoked from the **repository root** (the directory containing the `question-service` subdirectory). The `cd question-service` commands assume this directory structure.

2. **Virtual Environment**: The question-service virtual environment must be set up:
   ```bash
   cd question-service && python -m venv venv && source venv/bin/activate && pip install -r requirements.txt
   ```

3. **Environment Variables**: Required API keys must be configured in `question-service/.env`:
   - `OPENAI_API_KEY` - For question generation
   - `ANTHROPIC_API_KEY` - For question judging

## Implementation

When this skill is invoked, follow these steps:

### Step 1: Validate Arguments

Parse the arguments to extract type, count, and difficulty:
- If no arguments provided, show usage and exit
- Validate that type is one of: `math`, `logic`, `pattern`, `spatial`, `verbal`, `memory`
- If invalid type, show error with valid options and exit
- If count provided, validate it's a positive integer
- If difficulty provided, validate it's one of: `easy`, `medium`, `hard`

### Step 2: Check Environment

Verify the question-service environment is ready:
```bash
cd question-service && test -d venv && echo "venv exists" || echo "venv missing"
```

If venv is missing, inform the user they need to set up the question-service first.

### Step 3: Execute Generation

Run the generation script with the validated parameters:

```bash
cd question-service && source venv/bin/activate && python run_generation.py --types <type> --count <count> --async --async-judge --verbose
```

If difficulty is specified, note that the current `run_generation.py` script does not support a `--difficulty` flag. Inform the user that difficulty filtering is not yet implemented and proceed with generation of all difficulty levels.

### Step 4: Report Results

After execution:
- Show the generation summary from the script output
- Report how many questions were generated and inserted
- Note any errors or warnings

## Examples

### Generate 50 math questions (default count)
```
/generate-questions-by-type math
```
Executes:
```bash
cd question-service && source venv/bin/activate && python run_generation.py --types math --count 50 --async --async-judge --verbose
```

### Generate 100 logic questions
```
/generate-questions-by-type logic 100
```
Executes:
```bash
cd question-service && source venv/bin/activate && python run_generation.py --types logic --count 100 --async --async-judge --verbose
```

### Generate 25 spatial questions (difficulty not yet supported)
```
/generate-questions-by-type spatial 25 hard
```
Notes that difficulty filtering is not yet supported, then executes:
```bash
cd question-service && source venv/bin/activate && python run_generation.py --types spatial --count 25 --async --async-judge --verbose
```

## Error Handling

### Invalid Type
```
Error: Invalid question type 'foo'.
Valid types: math, logic, pattern, spatial, verbal, memory
```

### Invalid Count
```
Error: Count must be a positive integer. Got: 'abc'
```

### Missing venv
```
Error: Question service virtual environment not found.
Please run: cd question-service && python -m venv venv && source venv/bin/activate && pip install -r requirements.txt
```

### Exit Code Handling

The `run_generation.py` script returns exit codes that indicate the result. **Handle each exit code as follows:**

| Exit Code | Meaning | Action |
|-----------|---------|--------|
| 0 | Success | Report the number of questions generated and inserted. No action needed. |
| 1 | Partial failure | Some questions were generated but others failed. Report the count of successful insertions and warn the user to check logs at `question-service/logs/` for details on failures. Suggest retrying with a smaller count if many failures occurred. |
| 2 | Complete failure | No questions were generated. Check the error output for the cause. Common causes: API rate limits, network issues, or invalid prompts. Suggest the user wait and retry, or check API quotas. |
| 3 | Configuration error | Environment or argument configuration is invalid. Check that `.env` file exists with valid API keys. Verify all required environment variables are set. |
| 4 | Database error | Cannot connect to or write to the database. Verify database connectivity and check that the `question-service/questions.db` file exists and is writable. |

**Example handling:**

```bash
cd question-service && source venv/bin/activate && python run_generation.py --types math --count 50 --async --async-judge --verbose
EXIT_CODE=$?

case $EXIT_CODE in
  0) echo "Generation completed successfully." ;;
  1) echo "Partial failure. Check logs at question-service/logs/ for details." ;;
  2) echo "Complete failure. Check API quotas and retry." ;;
  3) echo "Configuration error. Verify .env file and environment variables." ;;
  4) echo "Database error. Check database file permissions and connectivity." ;;
esac
```

## Notes

- This skill runs generation **locally** using the question-service in your dev environment
- For production generation, use `/generate-questions` which triggers the Railway service
- Generation uses async mode for improved performance
- Questions are judged and deduplicated before insertion
- Check `question-service/logs/` for detailed logs after generation
