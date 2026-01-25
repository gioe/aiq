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

### Generation Failures
The script has built-in error handling and exit codes:
- Exit 0: Success
- Exit 1: Partial failure (some questions generated)
- Exit 2: Complete failure (no questions generated)
- Exit 3: Configuration error
- Exit 4: Database error

Report the exit code and any error messages to the user.

## Notes

- This skill runs generation **locally** using the question-service in your dev environment
- For production generation, use `/generate-questions` which triggers the Railway service
- Generation uses async mode for improved performance
- Questions are judged and deduplicated before insertion
- Check `question-service/logs/` for detailed logs after generation
