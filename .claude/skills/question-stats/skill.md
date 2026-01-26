---
name: question-stats
description: Display a table showing question counts in the database, broken down by type and difficulty level.
allowed-tools: Bash
---

# Question Statistics Skill

Displays a breakdown of questions in the AIQ database by type and difficulty.

## Usage

```
/question-stats
```

## Implementation

Run this Python script to query the database and display the results:

```bash
cd /Users/mattgioe/aiq/question-service && source venv/bin/activate && export $(grep -v '^#' .env | xargs) && python -c "
import os
from sqlalchemy import create_engine, text

db_url = os.environ.get('DATABASE_URL')
if not db_url:
    print('ERROR: DATABASE_URL environment variable not set')
    exit(1)

engine = create_engine(db_url)

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

# Build the data structure
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

# Print table
print()
print('Question Inventory by Type and Difficulty')
print('=' * 60)
print()
print(f\"{'Type':<12} | {'Easy':>8} | {'Medium':>8} | {'Hard':>8} | {'Total':>8}\")
print('-' * 60)
for t in types:
    e = data[t]['easy']
    m = data[t]['medium']
    h = data[t]['hard']
    total = totals_by_type[t]
    print(f'{t:<12} | {e:>8} | {m:>8} | {h:>8} | {total:>8}')
print('-' * 60)
print(f\"{'TOTAL':<12} | {totals_by_diff['easy']:>8} | {totals_by_diff['medium']:>8} | {totals_by_diff['hard']:>8} | {grand_total:>8}\")
print()
"
```

## Output

The skill displays a table like this:

```
Question Inventory by Type and Difficulty
============================================================

Type         |     Easy |   Medium |     Hard |    Total
------------------------------------------------------------
pattern      |       10 |       15 |        5 |       30
logic        |       12 |       18 |        8 |       38
spatial      |        8 |       12 |        4 |       24
math         |       15 |       20 |       10 |       45
verbal       |       11 |       16 |        6 |       33
memory       |        9 |       14 |        5 |       28
------------------------------------------------------------
TOTAL        |       65 |       95 |       38 |      198
```

## Requirements

- The `question-service/.env` file must contain the `DATABASE_URL` PostgreSQL connection string
- The `question-service` virtual environment must be set up with SQLAlchemy installed
