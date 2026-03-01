---
name: question-stats
description: Display a table showing question counts in the database, broken down by type and difficulty level, plus sub-type distribution per question type.
allowed-tools: Bash
---

# Question Statistics Skill

Displays a breakdown of questions in the AIQ database by type and difficulty, including the configured provider and model for each question type, followed by sub-type distribution per question type.

**Important:** Always present the FULL output to the user, including both the type/difficulty inventory table AND the sub-type distribution breakdown. Do not summarize or omit the sub-type section.

## Usage

```
/question-stats
```

## Implementation

Run this Python script to query the database and display the results:

```bash
cd question-service && source venv/bin/activate && export $(grep -v '^#' .env | xargs) && python -c "
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

# Query for sub-type breakdown (uses sub_type if set, otherwise inferred_sub_type)
subtype_query = text('''
    SELECT
        question_type,
        COALESCE(sub_type, inferred_sub_type) as effective_sub_type,
        COUNT(*) as count
    FROM questions
    WHERE is_active = true
      AND COALESCE(sub_type, inferred_sub_type) IS NOT NULL
    GROUP BY question_type, COALESCE(sub_type, inferred_sub_type)
    ORDER BY question_type, count DESC
''')

with engine.connect() as conn:
    results = conn.execute(query).fetchall()
    subtype_results = conn.execute(subtype_query).fetchall()

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

# Build sub-type data: {type: [(subtype, count), ...]}
from collections import defaultdict
subtype_data = defaultdict(list)
subtype_totals = defaultdict(int)
for row in subtype_results:
    qtype = row[0].lower() if hasattr(row[0], 'lower') else str(row[0]).lower()
    st = row[1]
    count = row[2]
    subtype_data[qtype].append((st, count))
    subtype_totals[qtype] += count

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

# Print sub-type distribution per question type
print('Sub-Type Distribution by Question Type')
print('=' * 100)
for t in types:
    if t not in subtype_data or not subtype_data[t]:
        continue
    type_total = subtype_totals[t]
    print(f\"\n  {t.upper()} ({type_total} classified)\")
    for st, count in subtype_data[t]:
        pct = (count / type_total) * 100 if type_total > 0 else 0
        bar = '#' * int(pct / 2)
        print(f'    {pct:5.1f}%  {bar:<50s} {st} ({count})')
    unclassified = totals_by_type[t] - type_total
    if unclassified > 0:
        print(f'           {\"\":50s} ({unclassified} unclassified)')
print()
"
```

## Output

The skill displays two tables: a type/difficulty inventory and a sub-type distribution breakdown.

```
Question Inventory by Type and Difficulty
====================================================================================================

Type         | Provider     | Model                          |   Easy | Medium |   Hard |  Total
----------------------------------------------------------------------------------------------------
pattern      | google       | gemini-3-pro-preview           |     10 |     15 |      5 |     30
logic        | anthropic    | claude-sonnet-4-5-20250929     |     12 |     18 |      8 |     38
...
----------------------------------------------------------------------------------------------------
TOTAL        |              |                                |     65 |     95 |     38 |    198

Sub-Type Distribution by Question Type
====================================================================================================

  PATTERN (30 classified)
     33.3%  ################                                   number sequences with arithmetic progressions (10)
     20.0%  ##########                                         letter patterns using alphabetic positions (6)
     ...
```

## Requirements

- The `question-service/.env` file must contain the `DATABASE_URL` PostgreSQL connection string
- The `question-service` virtual environment must be set up with SQLAlchemy and PyYAML installed
- The `config/generators.yaml` file must exist with provider/model configuration
