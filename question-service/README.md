# IQ Tracker Question Generation Service

Autonomous service for generating novel IQ test questions using AI.

## Purpose

Continuously generates fresh, high-quality IQ test questions to prevent users from encountering repeated questions and to ensure test validity over time.

## Architecture

### Multi-LLM Design

This service employs multiple Large Language Models to generate diverse questions:

1. **Generator LLMs** - Multiple models create candidate questions
   - Diversity in question types and difficulty
   - Different models bring different strengths

2. **Arbiter LLM** - Quality control layer
   - Evaluates generated questions for:
     - Clarity and unambiguity
     - Appropriate difficulty level
     - Validity as an IQ test question
     - Novelty (not duplicating existing questions)
   - Approves or rejects candidate questions

## Question Types

(To be defined - typical IQ test categories include:)
- Pattern recognition
- Logical reasoning
- Spatial reasoning
- Mathematical problems
- Verbal reasoning
- Memory-based questions

## Tech Stack

- **Language**: Python 3.10+
- **Database**: PostgreSQL 14+ (shared with backend)
- **ORM**: SQLAlchemy
- **LLM Providers**:
  - OpenAI (GPT-4, GPT-4-turbo)
  - Anthropic (Claude 3.5 Sonnet, Claude 3 Opus)
  - Google (Gemini Pro)
- **Execution**: Scheduled job (cron/cloud scheduler)

## Process Flow

1. Service runs on a schedule (e.g., daily/weekly)
2. Generator LLMs create batches of candidate questions
3. Arbiter LLM evaluates each candidate
4. Approved questions are inserted into database
5. Questions are tagged with metadata (type, difficulty, etc.)
6. System ensures no duplicates exist

## Setup

### Prerequisites

- Python 3.10 or higher
- PostgreSQL 14 or higher (shared with backend)
- API keys for LLM providers (OpenAI, Anthropic, Google)

### 1. Database Setup

This service uses the same PostgreSQL database as the backend. Follow the database setup instructions in the [backend README](../backend/README.md#1-database-setup).

### 2. Environment Configuration

Copy the example environment file and configure it:

```bash
cp .env.example .env
```

Edit `.env` and update the following values:
- `DATABASE_URL`: Same as backend (points to `iq_tracker_dev`)
- `OPENAI_API_KEY`: Your OpenAI API key
- `ANTHROPIC_API_KEY`: Your Anthropic API key
- `GOOGLE_API_KEY`: Your Google API key
- Configure generation settings as needed

### 3. Python Environment

(To be added in Phase 1 - P1-008)

### 4. Arbiter Configuration

(To be added in Phase 6 - P6-004)

### 5. Run Question Generation

(To be added in Phase 6)

## Configuration

(To be added)

## Monitoring

(To be added - should track:)
- Questions generated per run
- Approval/rejection rates
- Question pool size
- Coverage across question types and difficulties
