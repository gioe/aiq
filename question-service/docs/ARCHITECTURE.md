# Question Service Architecture

This document provides visual and detailed documentation of the question-service architecture, including pipeline flow, component interactions, and deployment configuration.

## Table of Contents

- [High-Level Overview](#high-level-overview)
- [Pipeline Flow](#pipeline-flow)
- [Component Architecture](#component-architecture)
- [LLM Provider System](#llm-provider-system)
- [Judge System](#judge-system)
- [Data Models](#data-models)
- [Deployment Architecture](#deployment-architecture)
- [Error Handling](#error-handling)

---

## High-Level Overview

The question-service generates IQ test questions through a multi-stage pipeline that leverages multiple LLM providers for generation, specialized judges for quality evaluation, and semantic deduplication to ensure uniqueness.

```mermaid
flowchart TB
    subgraph Entry["Entry Points"]
        CLI["CLI<br/>run_generation.py"]
        HTTP["HTTP Trigger<br/>trigger_server.py"]
        CRON["Scheduler<br/>Cron/Railway"]
    end

    subgraph Pipeline["Question Generation Pipeline"]
        GEN["Generation<br/>Multi-LLM"]
        EVAL["Evaluation<br/>Judge System"]
        DEDUP["Deduplication<br/>Embeddings"]
        STORE["Storage<br/>PostgreSQL"]
    end

    subgraph External["External Services"]
        LLM["LLM Providers<br/>OpenAI, Anthropic, Google, xAI"]
        DB[(PostgreSQL<br/>Database)]
        BACKEND["Backend API<br/>Metrics Reporting"]
    end

    CLI --> Pipeline
    HTTP --> Pipeline
    CRON --> CLI

    GEN --> EVAL --> DEDUP --> STORE

    GEN <--> LLM
    EVAL <--> LLM
    DEDUP <--> LLM
    STORE --> DB
    Pipeline --> BACKEND
```

---

## Pipeline Flow

### Complete Question Generation Flow

This diagram shows the detailed flow from entry point to database storage, including all decision points and error handling.

```mermaid
flowchart TD
    START([Start]) --> INIT[Initialize Components]

    INIT --> |Load Config| CONFIG[/"Settings<br/>API Keys, DB URL, Thresholds"/]
    CONFIG --> SETUP[Setup Logging & Metrics]

    SETUP --> GENLOOP[For Each Question Type + Difficulty]

    subgraph Generation["1. GENERATION STAGE"]
        GENLOOP --> SELECT[Select LLM Provider<br/>Round-robin distribution]
        SELECT --> PROMPT[Build Generation Prompt]
        PROMPT --> CALL_LLM[Call LLM API]
        CALL_LLM --> PARSE[Parse Response]
        PARSE --> VALIDATE{Valid<br/>Structure?}
        VALIDATE -->|Yes| BATCH[Add to Batch]
        VALIDATE -->|No| RETRY{Retries<br/>Left?}
        RETRY -->|Yes| CALL_LLM
        RETRY -->|No| SKIP[Skip Question]
        SKIP --> GENLOOP
        BATCH --> GENLOOP
    end

    GENLOOP --> |Batch Complete| EVALLOOP[For Each Generated Question]

    subgraph Evaluation["2. EVALUATION STAGE"]
        EVALLOOP --> JUDGE[Select Judge Model<br/>Based on Question Type]
        JUDGE --> EVAL_PROMPT[Build Evaluation Prompt]
        EVAL_PROMPT --> EVAL_CALL[Call Judge LLM]
        EVAL_CALL --> SCORE[Parse Evaluation Score]
        SCORE --> CHECK{Score >= <br/>Threshold?}
        CHECK -->|Yes| APPROVED[Mark Approved]
        CHECK -->|No| REJECTED[Mark Rejected]
        APPROVED --> EVALLOOP
        REJECTED --> EVALLOOP
    end

    EVALLOOP --> |Evaluation Complete| DEDUPLOOP[For Each Approved Question]

    subgraph Deduplication["3. DEDUPLICATION STAGE"]
        DEDUPLOOP --> EXACT[Check Exact Match<br/>SHA-256 Hash]
        EXACT --> EXACT_CHECK{Exact<br/>Match?}
        EXACT_CHECK -->|Yes| DUP_FLAG[Flag as Duplicate]
        EXACT_CHECK -->|No| EMBED[Get OpenAI Embedding]
        EMBED --> COSINE[Calculate Cosine Similarity<br/>vs Existing Questions]
        COSINE --> SIM_CHECK{Similarity ><br/>Threshold?}
        SIM_CHECK -->|Yes| DUP_FLAG
        SIM_CHECK -->|No| UNIQUE[Mark as Unique]
        DUP_FLAG --> DEDUPLOOP
        UNIQUE --> DEDUPLOOP
    end

    DEDUPLOOP --> |Deduplication Complete| STORELOOP[For Each Unique Question]

    subgraph Storage["4. STORAGE STAGE"]
        STORELOOP --> INSERT[Insert into PostgreSQL]
        INSERT --> STORE_EMBED[Store Pre-computed Embedding]
        STORE_EMBED --> STORELOOP
    end

    STORELOOP --> |Storage Complete| REPORT[Generate Run Report]

    subgraph Reporting["5. REPORTING STAGE"]
        REPORT --> METRICS[Collect Metrics]
        METRICS --> HEARTBEAT[Write Heartbeat File]
        HEARTBEAT --> BACKEND_CALL{Backend<br/>Reporting<br/>Enabled?}
        BACKEND_CALL -->|Yes| SEND_REPORT[POST to Backend API]
        BACKEND_CALL -->|No| FINISH
        SEND_REPORT --> FINISH
    end

    FINISH --> EXIT_CODE{Determine<br/>Exit Code}
    EXIT_CODE -->|Success| EXIT0([Exit 0])
    EXIT_CODE -->|Partial Fail| EXIT1([Exit 1])
    EXIT_CODE -->|Complete Fail| EXIT2([Exit 2])
    EXIT_CODE -->|Config Error| EXIT3([Exit 3])
    EXIT_CODE -->|DB Error| EXIT4([Exit 4])
    EXIT_CODE -->|Billing Error| EXIT5([Exit 5])
    EXIT_CODE -->|Auth Error| EXIT6([Exit 6])
```

### Sequence Diagram: Single Question Lifecycle

```mermaid
sequenceDiagram
    participant CLI as run_generation.py
    participant Pipeline as QuestionPipeline
    participant Gen as QuestionGenerator
    participant LLM as LLM Provider
    participant Judge as QuestionJudge
    participant Dedup as QuestionDeduplicator
    participant DB as DatabaseService
    participant Backend as Backend API

    CLI->>Pipeline: generate_questions(type, difficulty, count)

    loop For each question
        Pipeline->>Gen: generate_question(type, difficulty)
        Gen->>Gen: select_provider()
        Gen->>LLM: generate_structured_completion(prompt)
        LLM-->>Gen: JSON response
        Gen->>Gen: parse_response()
        Gen-->>Pipeline: GeneratedQuestion
    end

    loop For each generated question
        Pipeline->>Judge: evaluate_question(question)
        Judge->>Judge: get_judge_for_type(type)
        Judge->>LLM: evaluate_prompt(question)
        LLM-->>Judge: EvaluationScore
        Judge->>Judge: calculate_composite_score()
        Judge-->>Pipeline: EvaluatedQuestion
    end

    loop For each approved question
        Pipeline->>Dedup: check_duplicate(question)
        Dedup->>Dedup: check_exact_match(hash)
        Dedup->>LLM: get_embedding(text)
        LLM-->>Dedup: embedding vector
        Dedup->>DB: get_existing_embeddings()
        DB-->>Dedup: existing embeddings
        Dedup->>Dedup: calculate_cosine_similarity()
        Dedup-->>Pipeline: is_duplicate
    end

    loop For each unique question
        Pipeline->>DB: insert_question(question)
        DB-->>Pipeline: question_id
    end

    Pipeline->>Backend: POST /generation/runs
    Backend-->>Pipeline: 200 OK

    Pipeline-->>CLI: RunResult
```

---

## Component Architecture

### Core Components and Dependencies

```mermaid
flowchart TB
    subgraph Entry["Entry Layer"]
        CLI["run_generation.py<br/>CLI Entry Point"]
        TRIGGER["trigger_server.py<br/>HTTP Trigger"]
    end

    subgraph Orchestration["Orchestration Layer"]
        PIPELINE["QuestionGenerationPipeline<br/>app/pipeline.py"]
    end

    subgraph Generation["Generation Layer"]
        GENERATOR["QuestionGenerator<br/>app/generator.py"]
        PROMPTS["PromptBuilder<br/>app/prompts.py"]
    end

    subgraph Evaluation["Evaluation Layer"]
        JUDGE["QuestionJudge<br/>app/judge.py"]
        JUDGE_CFG["JudgeConfigLoader<br/>app/judge_config.py"]
    end

    subgraph Quality["Quality Layer"]
        DEDUP["QuestionDeduplicator<br/>app/deduplicator.py"]
        CACHE["EmbeddingCache<br/>In-Memory"]
    end

    subgraph Persistence["Persistence Layer"]
        DATABASE["DatabaseService<br/>app/database.py"]
    end

    subgraph Observability["Observability Layer"]
        SUMMARY["RunSummary<br/>app/run_summary.py"]
        REPORTER["RunReporter<br/>app/reporter.py"]
        ALERTING["AlertManager<br/>app/alerting.py"]
    end

    subgraph Providers["Provider Layer"]
        BASE["BaseLLMProvider<br/>app/providers/base.py"]
        OPENAI["OpenAIProvider"]
        ANTHROPIC["AnthropicProvider"]
        GOOGLE["GoogleProvider"]
        XAI["XAIProvider"]
    end

    subgraph Config["Configuration"]
        SETTINGS["Settings<br/>app/config.py"]
        YAML[("judges.yaml")]
    end

    CLI --> PIPELINE
    TRIGGER --> PIPELINE

    PIPELINE --> GENERATOR
    PIPELINE --> JUDGE
    PIPELINE --> DEDUP
    PIPELINE --> DATABASE
    PIPELINE --> METRICS

    GENERATOR --> PROMPTS
    GENERATOR --> BASE

    JUDGE --> JUDGE_CFG
    JUDGE --> BASE
    JUDGE_CFG --> YAML

    DEDUP --> CACHE
    DEDUP --> BASE

    METRICS --> REPORTER
    METRICS --> ALERTING

    BASE --> OPENAI
    BASE --> ANTHROPIC
    BASE --> GOOGLE
    BASE --> XAI

    SETTINGS --> PIPELINE
    SETTINGS --> DATABASE
```

### Class Relationships

```mermaid
classDiagram
    class QuestionGenerationPipeline {
        -generator: QuestionGenerator
        -judge: QuestionJudge
        -deduplicator: QuestionDeduplicator
        -database: DatabaseService
        -summary: RunSummary
        +generate_questions(type, difficulty, count)
        +generate_full_question_set(per_type)
    }

    class QuestionGenerator {
        -providers: Dict~str, BaseLLMProvider~
        -prompt_builder: PromptBuilder
        +generate_question(type, difficulty)
        +generate_batch(type, difficulty, count)
        -select_provider()
        -parse_response(response)
    }

    class QuestionJudge {
        -config_loader: JudgeConfigLoader
        -providers: Dict~str, BaseLLMProvider~
        +evaluate_question(question) EvaluatedQuestion
        +evaluate_batch(questions) List~EvaluatedQuestion~
        -get_judge_for_type(type) BaseLLMProvider
        -calculate_composite_score(scores) float
    }

    class QuestionDeduplicator {
        -embedding_cache: EmbeddingCache
        -similarity_threshold: float
        +check_duplicates(questions, db) List~bool~
        -check_exact_match(text) bool
        -check_semantic_similarity(question) bool
        -get_embedding(text) ndarray
    }

    class DatabaseService {
        -engine: Engine
        -session: Session
        +insert_question(question)
        +insert_questions(questions)
        +get_existing_questions()
        +store_embedding(id, embedding)
    }

    class BaseLLMProvider {
        <<abstract>>
        -api_key: str
        -model: str
        +generate_completion(prompt)*
        +generate_structured_completion(prompt)*
        #with_retry(func)
    }

    class OpenAIProvider {
        -client: OpenAI
        +generate_completion(prompt)
        +generate_structured_completion(prompt)
    }

    class AnthropicProvider {
        -client: Anthropic
        +generate_completion(prompt)
        +generate_structured_completion(prompt)
    }

    QuestionGenerationPipeline --> QuestionGenerator
    QuestionGenerationPipeline --> QuestionJudge
    QuestionGenerationPipeline --> QuestionDeduplicator
    QuestionGenerationPipeline --> DatabaseService

    QuestionGenerator --> BaseLLMProvider
    QuestionJudge --> BaseLLMProvider
    QuestionDeduplicator --> BaseLLMProvider

    BaseLLMProvider <|-- OpenAIProvider
    BaseLLMProvider <|-- AnthropicProvider
    BaseLLMProvider <|-- GoogleProvider
    BaseLLMProvider <|-- XAIProvider
```

---

## LLM Provider System

### Provider Architecture

```mermaid
flowchart TB
    subgraph Providers["LLM Provider System"]
        BASE["BaseLLMProvider<br/>Abstract Base Class"]

        subgraph Implementations["Provider Implementations"]
            OPENAI["OpenAIProvider<br/>gpt-4-turbo-preview"]
            ANTHROPIC["AnthropicProvider<br/>claude-sonnet-4-5"]
            GOOGLE["GoogleProvider<br/>gemini-pro"]
            XAI["XAIProvider<br/>grok-4"]
        end

        BASE --> OPENAI
        BASE --> ANTHROPIC
        BASE --> GOOGLE
        BASE --> XAI
    end

    subgraph Features["Provider Features"]
        RETRY["Exponential Backoff<br/>max_retries: 3<br/>base_delay: 1.0s"]
        JSON["Structured JSON Output<br/>Response Parsing"]
        ERROR["Error Classification<br/>Transient/Permanent/Critical"]
    end

    BASE --> RETRY
    BASE --> JSON
    BASE --> ERROR

    subgraph APIs["External APIs"]
        OPENAI_API["OpenAI API<br/>chat/completions"]
        ANTHROPIC_API["Anthropic API<br/>messages"]
        GOOGLE_API["Google AI API<br/>generateContent"]
        XAI_API["xAI API<br/>chat/completions"]
    end

    OPENAI --> OPENAI_API
    ANTHROPIC --> ANTHROPIC_API
    GOOGLE --> GOOGLE_API
    XAI --> XAI_API
```

### Retry Logic Flow

```mermaid
flowchart TD
    START([API Call]) --> ATTEMPT[Make Request]
    ATTEMPT --> SUCCESS{Success?}

    SUCCESS -->|Yes| RETURN([Return Response])
    SUCCESS -->|No| CLASSIFY[Classify Error]

    CLASSIFY --> TYPE{Error Type?}

    TYPE -->|Transient| RETRY_CHECK{Retries<br/>Remaining?}
    TYPE -->|Permanent| FAIL_PERM([Fail Immediately])
    TYPE -->|Critical| ALERT[Send Alert]
    ALERT --> FAIL_CRIT([Fail with Alert])

    RETRY_CHECK -->|Yes| CALC_DELAY[Calculate Delay<br/>delay = base * 2^attempt]
    RETRY_CHECK -->|No| FAIL_RETRY([Fail After Retries])

    CALC_DELAY --> JITTER[Add Jitter<br/>random(base, delay)]
    JITTER --> CAP[Cap at max_delay]
    CAP --> WAIT[Wait delay seconds]
    WAIT --> ATTEMPT
```

---

## Judge System

### Type-Specific Judge Selection

```mermaid
flowchart LR
    subgraph QuestionTypes["Question Types"]
        PATTERN["Pattern Recognition"]
        LOGIC["Logical Reasoning"]
        SPATIAL["Spatial Reasoning"]
        MATH["Mathematical"]
        VERBAL["Verbal Reasoning"]
        MEMORY["Memory"]
    end

    subgraph JudgeModels["Judge Models"]
        CLAUDE["Claude Sonnet 3.5<br/>Anthropic"]
        GROK["Grok-4<br/>xAI"]
    end

    PATTERN --> CLAUDE
    LOGIC --> CLAUDE
    SPATIAL --> CLAUDE
    VERBAL --> CLAUDE
    MEMORY --> CLAUDE
    MATH --> GROK

    subgraph Rationale["Selection Rationale"]
        CLAUDE_WHY["Claude: GPQA 67.2%, MMLU 90.4%<br/>Strong reasoning & language"]
        GROK_WHY["Grok: GSM8K 95.2%, AIME 100%<br/>Exceptional math performance"]
    end
```

### Evaluation Scoring System

```mermaid
flowchart TB
    subgraph Input["Evaluation Input"]
        QUESTION["Generated Question"]
    end

    subgraph Criteria["Evaluation Criteria"]
        CLARITY["Clarity Score<br/>Weight: 0.25"]
        DIFFICULTY["Difficulty Score<br/>Weight: 0.20"]
        VALIDITY["Validity Score<br/>Weight: 0.30"]
        FORMAT["Formatting Score<br/>Weight: 0.15"]
        CREATIVE["Creativity Score<br/>Weight: 0.10"]
    end

    subgraph Calculation["Score Calculation"]
        COMPOSITE["Composite Score<br/>= (clarity * 0.25)<br/>+ (difficulty * 0.20)<br/>+ (validity * 0.30)<br/>+ (formatting * 0.15)<br/>+ (creativity * 0.10)"]
    end

    subgraph Decision["Approval Decision"]
        THRESHOLD{Score >= 0.7?}
        APPROVED["Approved"]
        REJECTED["Rejected"]
    end

    QUESTION --> CLARITY
    QUESTION --> DIFFICULTY
    QUESTION --> VALIDITY
    QUESTION --> FORMAT
    QUESTION --> CREATIVE

    CLARITY --> COMPOSITE
    DIFFICULTY --> COMPOSITE
    VALIDITY --> COMPOSITE
    FORMAT --> COMPOSITE
    CREATIVE --> COMPOSITE

    COMPOSITE --> THRESHOLD
    THRESHOLD -->|Yes| APPROVED
    THRESHOLD -->|No| REJECTED
```

---

## Data Models

### Question Data Flow

```mermaid
flowchart LR
    subgraph Generation["Generation Phase"]
        RAW["Raw LLM Response<br/>JSON String"]
        GEN_Q["GeneratedQuestion<br/>Pydantic Model"]
    end

    subgraph Evaluation["Evaluation Phase"]
        EVAL_SCORE["EvaluationScore<br/>5 Criteria"]
        EVAL_Q["EvaluatedQuestion<br/>Question + Score"]
    end

    subgraph Storage["Storage Phase"]
        DB_MODEL["QuestionModel<br/>SQLAlchemy"]
        DB_ROW[("Database Row<br/>PostgreSQL")]
    end

    RAW --> |Parse| GEN_Q
    GEN_Q --> |Evaluate| EVAL_SCORE
    GEN_Q --> EVAL_Q
    EVAL_SCORE --> EVAL_Q
    EVAL_Q --> |Map| DB_MODEL
    DB_MODEL --> |Insert| DB_ROW
```

### Database Schema

```mermaid
erDiagram
    questions {
        int id PK
        text question_text
        enum question_type
        enum difficulty_level
        text correct_answer
        jsonb answer_options
        text explanation
        varchar source_llm
        varchar source_model
        float judge_score
        varchar prompt_version
        float[] question_embedding
        jsonb question_metadata
        timestamp created_at
        boolean is_active
    }
```

---

## Deployment Architecture

### Container Architecture

```mermaid
flowchart TB
    subgraph Docker["Docker Container"]
        subgraph Build["Build Stage"]
            PYTHON_BASE["python:3.11-slim"]
            DEPS["Install Dependencies<br/>gcc, postgresql-client"]
            PIP["pip install requirements.txt"]
        end

        subgraph Runtime["Production Stage"]
            PYTHON_PROD["python:3.11-slim"]
            APP_USER["Non-root user: appuser"]
            APP_CODE["Application Code"]
            CMD["CMD: python run_generation.py"]
        end

        Build --> Runtime
    end

    subgraph Environment["Environment Configuration"]
        DB_URL["DATABASE_URL"]
        API_KEYS["API Keys<br/>OpenAI, Anthropic, Google, xAI"]
        GEN_SETTINGS["Generation Settings<br/>count, min_score, etc."]
        ALERT_CFG["Alert Configuration<br/>SMTP, Email"]
    end

    subgraph External["External Services"]
        POSTGRES[(PostgreSQL)]
        LLM_APIS["LLM APIs"]
        BACKEND_API["Backend API"]
        SMTP["SMTP Server"]
    end

    Environment --> Docker
    Docker --> POSTGRES
    Docker --> LLM_APIS
    Docker --> BACKEND_API
    Docker --> SMTP
```

### Railway Deployment

```mermaid
flowchart TB
    subgraph Railway["Railway Platform"]
        subgraph Services["Services"]
            QS["Question Service<br/>Scheduled Job"]
            TRIGGER["Trigger Server<br/>Always Running"]
            DB_SVC["PostgreSQL<br/>Managed Database"]
        end

        subgraph Scheduling["Scheduling"]
            CRON["Cron Trigger<br/>Daily/Hourly"]
        end

        subgraph Monitoring["Monitoring"]
            LOGS["Railway Logs"]
            HEALTH["Health Checks"]
        end
    end

    subgraph External["External"]
        BACKEND["Backend API<br/>aiq-backend-production.up.railway.app"]
        LLM["LLM APIs"]
    end

    CRON --> QS
    QS --> DB_SVC
    QS --> LLM
    QS --> BACKEND
    TRIGGER --> QS
    QS --> LOGS
    HEALTH --> QS
```

---

## Error Handling

### Error Classification System

```mermaid
flowchart TB
    subgraph Errors["Error Types"]
        ERR[Error Occurred]
    end

    ERR --> CLASSIFY{Classify Error}

    subgraph Transient["Transient Errors"]
        RATE["Rate Limit Exceeded"]
        TIMEOUT["Request Timeout"]
        NETWORK["Network Connectivity"]
    end

    subgraph Permanent["Permanent Errors"]
        AUTH["Authentication Failure"]
        INVALID["Invalid API Request"]
        CONFIG_ERR["Configuration Error"]
    end

    subgraph Critical["Critical Errors"]
        BILLING["Billing/Quota Exceeded"]
        DISABLED["Account Disabled"]
    end

    CLASSIFY -->|Transient| RATE
    CLASSIFY -->|Transient| TIMEOUT
    CLASSIFY -->|Transient| NETWORK
    CLASSIFY -->|Permanent| AUTH
    CLASSIFY -->|Permanent| INVALID
    CLASSIFY -->|Permanent| CONFIG_ERR
    CLASSIFY -->|Critical| BILLING
    CLASSIFY -->|Critical| DISABLED

    subgraph Handling["Error Handling"]
        RETRY_H["Retry with Backoff"]
        FAIL_H["Fail Immediately"]
        ALERT_H["Alert + Fail"]
    end

    RATE --> RETRY_H
    TIMEOUT --> RETRY_H
    NETWORK --> RETRY_H
    AUTH --> FAIL_H
    INVALID --> FAIL_H
    CONFIG_ERR --> FAIL_H
    BILLING --> ALERT_H
    DISABLED --> ALERT_H
```

### Exit Code Decision Tree

```mermaid
flowchart TD
    START([Pipeline Complete]) --> CHECK_CONFIG{Config<br/>Error?}

    CHECK_CONFIG -->|Yes| EXIT3([Exit 3<br/>Configuration Error])
    CHECK_CONFIG -->|No| CHECK_DB{DB<br/>Error?}

    CHECK_DB -->|Yes| EXIT4([Exit 4<br/>Database Error])
    CHECK_DB -->|No| CHECK_AUTH{Auth<br/>Error?}

    CHECK_AUTH -->|Yes| EXIT6([Exit 6<br/>Authentication Error])
    CHECK_AUTH -->|No| CHECK_BILLING{Billing<br/>Error?}

    CHECK_BILLING -->|Yes| EXIT5([Exit 5<br/>Billing Error])
    CHECK_BILLING -->|No| CHECK_GEN{Questions<br/>Generated?}

    CHECK_GEN -->|No| EXIT2([Exit 2<br/>Complete Failure])
    CHECK_GEN -->|Some| CHECK_INSERT{All<br/>Inserted?}

    CHECK_INSERT -->|Yes| EXIT0([Exit 0<br/>Success])
    CHECK_INSERT -->|Partial| EXIT1([Exit 1<br/>Partial Failure])
```

---

## Related Documentation

- **[README.md](../README.md)** - Quick start guide and overview
- **[docs/OPERATIONS.md](OPERATIONS.md)** - Operations and scheduling guide
- **[docs/ALERTING.md](ALERTING.md)** - Alert configuration
- **[docs/JUDGE_SELECTION.md](JUDGE_SELECTION.md)** - Judge model selection rationale
- **[config/README.md](../config/README.md)** - Configuration reference
