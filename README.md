# AIQ

An iOS application that tracks users' IQ scores over time through periodic testing with AI-generated questions.

## Project Structure

This is a monorepo containing all components of the AIQ application:

```
aiq/
├── ios/                    # SwiftUI iOS application
├── backend/                # Backend API server
├── question-service/       # AI-powered question generation service
├── shared/                 # Placeholder for shared resources
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

See **[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)** for a complete development environment setup guide.

### Component-Specific Documentation

For detailed component information, see individual READMEs:
- [Backend API](backend/README.md) - FastAPI server, database, and migrations
- [Question Service](question-service/README.md) - AI question generation service
- [iOS App](ios/README.md) - SwiftUI iOS application

## Development

See **[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)** for:
- Prerequisites and installation
- Development workflow and git practices
- Code quality standards
- Testing procedures
- Troubleshooting guide

## Deployment

See **[RAILWAY_DEPLOYMENT.md](RAILWAY_DEPLOYMENT.md)** for production deployment on Railway.

Additional deployment documentation:
- [docs/deployment/RAILWAY.md](docs/deployment/RAILWAY.md) - Railway-specific configuration
- [docs/deployment/AWS.md](docs/deployment/AWS.md) - AWS deployment guide
- [docs/deployment/SERVICES.md](docs/deployment/SERVICES.md) - Service architecture
