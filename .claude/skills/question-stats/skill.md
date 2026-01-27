---
name: question-stats
description: Display a table showing question counts in the database, broken down by type and difficulty level.
allowed-tools: Bash
---

# Question Statistics Skill

Displays a breakdown of questions in the AIQ database by type and difficulty, including the configured provider and model for each question type.

## Usage

```
/question-stats
```

## Implementation

Run this Python script to query the database and display the results:

```bash
cd /Users/mattgioe/aiq/question-service && source venv/bin/activate && export $(grep -v '^#' .env | xargs) && python -c "
import os
import yaml
from sqlalchemy import create_engine, text

db_url = os.environ.get('DATABASE_URL')
if not db_url:
    print('ERROR: DATABASE_URL environment variable not set')
    exit(1)

engine = create_engine(db_url)

# Load generator config
with open('config/generators.yaml', 'r') as f:
    gen_config = yaml.safe_load(f)

generators = gen_config.get('generators', {})

# Query for type/difficulty breakdown
query = text('''
    SELECT
        question_type,
        difficulty_level,
        COUNT(*) as count
    FROM questions
    WHERE is_active = true
    GROUP BY question_type, difficulty_level
    ORDER BY question_type, difficulty_level
''')

with engine.connect() as conn:
    results = conn.execute(query).fetchall()

# Build the data structure for type/difficulty
types = ['pattern', 'logic', 'spatial', 'math', 'verbal', 'memory']
difficulties = ['easy', 'medium', 'hard']
data = {t: {d: 0 for d in difficulties} for t in types}
totals_by_type = {t: 0 for t in types}
totals_by_diff = {d: 0 for d in difficulties}

for row in results:
    qtype = row[0].lower() if hasattr(row[0], 'lower') else str(row[0]).lower()
    diff = row[1].lower() if hasattr(row[1], 'lower') else str(row[1]).lower()
    count = row[2]
    if qtype in data and diff in data[qtype]:
        data[qtype][diff] = count
        totals_by_type[qtype] += count
        totals_by_diff[diff] += count

grand_total = sum(totals_by_type.values())

# Print type/difficulty table with provider/model
print()
print('Question Inventory by Type and Difficulty')
print('=' * 100)
print()
print(f\"{'Type':<12} | {'Provider':<12} | {'Model':<30} | {'Easy':>6} | {'Medium':>6} | {'Hard':>6} | {'Total':>6}\")
print('-' * 100)
for t in types:
    e = data[t]['easy']
    m = data[t]['medium']
    h = data[t]['hard']
    total = totals_by_type[t]
    gen = generators.get(t, {})
    provider = gen.get('provider', '-')
    model = gen.get('model', '-')
    print(f'{t:<12} | {provider:<12} | {model:<30} | {e:>6} | {m:>6} | {h:>6} | {total:>6}')
print('-' * 100)
print(f\"{'TOTAL':<12} | {'':<12} | {'':<30} | {totals_by_diff['easy']:>6} | {totals_by_diff['medium']:>6} | {totals_by_diff['hard']:>6} | {grand_total:>6}\")
print()
"
```

## Output

The skill displays a table like this:

```
Question Inventory by Type and Difficulty
====================================================================================================

Type         | Provider     | Model                          |   Easy | Medium |   Hard |  Total
----------------------------------------------------------------------------------------------------
pattern      | google       | gemini-3-pro-preview           |     10 |     15 |      5 |     30
logic        | anthropic    | claude-sonnet-4-5-20250929     |     12 |     18 |      8 |     38
spatial      | google       | gemini-3-pro-preview           |      8 |     12 |      4 |     24
math         | xai          | grok-4                         |     15 |     20 |     10 |     45
verbal       | anthropic    | claude-sonnet-4-5-20250929     |     11 |     16 |      6 |     33
memory       | anthropic    | claude-sonnet-4-5-20250929     |      9 |     14 |      5 |     28
----------------------------------------------------------------------------------------------------
TOTAL        |              |                                |     65 |     95 |     38 |    198
```

## Requirements

- The `question-service/.env` file must contain the `DATABASE_URL` PostgreSQL connection string
- The `question-service` virtual environment must be set up with SQLAlchemy and PyYAML installed
- The `config/generators.yaml` file must exist with provider/model configuration
