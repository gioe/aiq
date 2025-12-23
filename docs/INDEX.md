# AIQ Documentation

This is the central documentation hub for the AIQ project.

## Quick Start

- [Development Setup](DEVELOPMENT.md) - Get your environment running
- [Project Roadmap](../PLAN.md) - Task tracking and progress
- [Architecture Overview](./architecture/OVERVIEW.md) - System design and data models

## Component Documentation

Each component has its own README with quick start guides:

- [Backend (FastAPI)](../backend/README.md) - API server and database
- [iOS App](../ios/README.md) - SwiftUI mobile application
- [Question Service](../question-service/README.md) - AI-powered question generation

## Architecture

- [System Overview](./architecture/OVERVIEW.md) - Complete architecture documentation including data models, API design, and component interactions

## Deployment

- [Railway (Production)](./deployment/RAILWAY.md) - Current production deployment guide
- [Service URLs & Config](./deployment/SERVICES.md) - Production and development endpoints
- [AWS Reference](./deployment/AWS.md) - AWS/Terraform deployment (reference only, not currently used)

## Methodology

- [IQ Scoring](./methodology/IQ_SCORING.md) - Scientific foundations and scoring approach
- [Psychometric Gaps](./methodology/gaps/INDEX.md) - Future improvements roadmap

## Testing

- [E2E Test Plan](./testing/E2E_PLAN.md) - End-to-end test scenarios
- [E2E Test Summary](./testing/E2E_SUMMARY.md) - Test execution results

## Security

- [Security Audit](./security/AUDIT.md) - Security assessment and findings

## Implementation Plans

Detailed plans for major features:

### Complete
- [Backend Code Quality](./plans/complete/PLAN-BACKEND-CODE-QUALITY.md) - 40 code quality improvements covering security, performance, and maintainability ✅
- [Empirical Calibration](../backend/plans/PLAN-EMPIRICAL-ITEM-CALIBRATION.md) - Difficulty label validation and recalibration based on empirical p-values ✅
- [Distractor Analysis](./plans/complete/PLAN-DISTRACTOR-ANALYSIS.md) - Multiple-choice distractor effectiveness analysis ✅
- [Item Discrimination Analysis](./plans/complete/PLAN-ITEM-DISCRIMINATION-ANALYSIS.md) - Auto-flagging and exclusion of questions with poor discrimination ✅
- [Reliability Estimation](./plans/complete/PLAN-RELIABILITY-ESTIMATION.md) - Cronbach's alpha, test-retest, and split-half reliability metrics ✅
- [Standard Error of Measurement](./plans/complete/PLAN-STANDARD-ERROR-OF-MEASUREMENT.md) - SEM calculation and confidence intervals for IQ scores ✅

### In Progress
- [Question Generation Tracking](./plans/QUESTION_GENERATION_TRACKING.md) - Question metrics system
- [In-Progress Test Detection](./plans/IN_PROGRESS_TEST.md) - Active session handling
- [Reusable Components](./plans/REUSABLE_COMPONENTS.md) - Future tooling extraction

## Claude Code Commands

Custom slash commands are available in [.claude/commands/](../.claude/commands/):

| Command | Description |
|---------|-------------|
| `/task P#-###` | Work on a specific task |
| `/plan <gap-file>` | Plan implementation for a gap |
| `/healthcheck` | Test backend health |
| `/generate-questions` | Trigger question generation |
| `/ios` | Build and run iOS app |

## Additional Resources

- [CLAUDE.md](../CLAUDE.md) - Development commands and patterns (also used by AI assistants)
- [README.md](../README.md) - Project overview
