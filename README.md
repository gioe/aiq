# IQ Tracker

An iOS application that tracks users' IQ scores over time through periodic testing with AI-generated questions.

## Project Structure

This is a monorepo containing all components of the IQ Tracker application:

```
iq-tracker/
├── ios/                    # SwiftUI iOS application
├── backend/                # Backend API server
├── question-service/       # AI-powered question generation service
├── shared/                 # Shared schemas, types, and documentation
├── .github/workflows/      # CI/CD pipelines
└── README.md              # This file
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
- Multi-LLM architecture with quality arbiter
- Ensures continuous supply of fresh questions
- Prevents question repetition per user

## Getting Started

### Quick Start

See **[DEVELOPMENT.md](DEVELOPMENT.md)** for a complete development environment setup guide.

### Component-Specific Documentation

For detailed component information, see individual READMEs:
- [Backend API](backend/README.md) - FastAPI server, database, and migrations
- [Question Service](question-service/README.md) - AI question generation service
- [iOS App](ios/README.md) - SwiftUI iOS application

## Development

See **[DEVELOPMENT.md](DEVELOPMENT.md)** for:
- Prerequisites and installation
- Development workflow and git practices
- Code quality standards
- Testing procedures
- Troubleshooting guide

For project planning and task tracking, see **[PLAN.md](PLAN.md)**

For extracting reusable components for future projects, see **[REUSABLE_COMPONENTS_PLAN.md](REUSABLE_COMPONENTS_PLAN.md)**

## Deployment

(Deployment instructions to be added)
