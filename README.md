# AIQ

An iOS application that tracks users' IQ scores over time through periodic testing with AI-generated questions.

## Project Structure

This is a monorepo containing all components of the AIQ application:

```
aiq/
├── ios/                 # SwiftUI iOS application
├── backend/             # Backend API server
├── question-service/    # AI-powered question generation service
├── libs/                # Shared Python packages (domain types, observability)
├── scripts/             # Pre-commit hooks (float checks, magic numbers)
├── docs/                # Project documentation
├── deployment/          # AWS Terraform configs (legacy)
├── website/             # Privacy policy, terms of service
├── .claude/             # Claude Code config, skills, and scripts
├── .github/             # CI/CD workflows, PR template, Dependabot
└── README.md            # This file
```

## Components

### iOS App (`ios/`)
- Native iOS application built with SwiftUI (iOS 16+)
- Gamified IQ test experience with intuitive UI
- Historical score tracking and trend visualization
- Push notification support for periodic test reminders
- Comprehensive design system with unified styling
- Full accessibility support (VoiceOver, Dynamic Type)
- Built-in analytics and performance monitoring

### Backend (`backend/`)
- FastAPI REST API server with async support
- JWT-based authentication and user management
- Question serving and response storage
- IQ score calculation and analytics
- Push notification scheduling (APNs integration)
- Rate limiting and security features
- Comprehensive logging and monitoring

### Question Service (`question-service/`)
- Autonomous service for generating novel IQ test questions
- Multi-LLM architecture with quality judge
- Ensures continuous supply of fresh questions
- Prevents question repetition per user

## Getting Started

For detailed component information, see individual READMEs:
- [Backend API](backend/README.md) - FastAPI server, database, and migrations
- [Question Service](question-service/README.md) - AI question generation service
- [iOS App](ios/README.md) - SwiftUI iOS application

## Deployment

- [Backend Deployment](backend/DEPLOYMENT.md) - Railway production deployment
- [Question Service Deployment](question-service/docs/RAILWAY_DEPLOYMENT.md) - Railway cron service
- [AWS Infrastructure](deployment/README.md) - Terraform configs (legacy)
