# AIQ - Development Guide

Complete guide for setting up and developing the AIQ project.

## Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.10+** - Required for backend and question-service
- **PostgreSQL 14+** - Database server
- **Xcode 14+** - Required for iOS development (macOS only)
- **Git** - Version control

### Verify Prerequisites

```bash
python3 --version   # Should be 3.10 or higher
psql --version      # Should be 14 or higher
xcodebuild -version # Should be 14 or higher
git --version
```

## Quick Start

Follow these steps to get the entire project running locally:

### 1. Clone the Repository

```bash
git clone https://github.com/gioe/aiq.git
cd aiq
```

### 2. Set Up PostgreSQL Database

#### Install PostgreSQL (if not already installed)

**macOS (using Homebrew):**
```bash
brew install postgresql@14
brew services start postgresql@14
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib
sudo systemctl start postgresql
```

**Windows:**
Download and install from [postgresql.org](https://www.postgresql.org/download/windows/)

#### Create Databases

```bash
# Connect to PostgreSQL
psql -U <your-username> -d postgres

# Create databases
CREATE DATABASE aiq_dev;
CREATE DATABASE aiq_test;

# Verify creation
\l

# Exit
\q
```

Replace `<your-username>` with your system username.

### 3. Set Up Backend

```bash
cd backend

# Copy environment file
cp .env.example .env

# Edit .env and update:
# - DATABASE_USER (your PostgreSQL username)
# - DATABASE_PASSWORD (if set)
# - DATABASE_URL (update username/password if needed)
# - SECRET_KEY (generate a secure random string)
# - JWT_SECRET_KEY (generate a different secure random string)

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start development server
uvicorn app.main:app --reload

# Server will be available at http://localhost:8000
# API docs at http://localhost:8000/v1/docs
```

Keep this terminal open with the server running.

### 4. Set Up Question Service

```bash
# Open a new terminal
cd question-service

# Copy environment file
cp .env.example .env

# Edit .env and update:
# - DATABASE_URL (same as backend)
# - OPENAI_API_KEY (your OpenAI API key)
# - ANTHROPIC_API_KEY (your Anthropic API key)
# - GOOGLE_API_KEY (your Google API key)

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt
```

**Note**: Question generation functionality will be implemented in Phase 6.

### 5. Set Up iOS App

```bash
cd ios

# Open Xcode project
open AIQ.xcodeproj
```

In Xcode:
1. Select your development team in project settings
2. Choose a simulator or connected device
3. Build and run (⌘+R)

## Project Structure

```
aiq/
├── backend/              # FastAPI backend server
│   ├── app/              # Application code
│   ├── alembic/          # Database migrations
│   ├── venv/             # Python virtual environment
│   └── requirements.txt  # Python dependencies
│
├── question-service/     # AI question generation service
│   ├── venv/             # Python virtual environment
│   └── requirements.txt  # Python dependencies
│
├── ios/                  # iOS application
│   ├── AIQ.xcodeproj
│   └── AIQ/        # Swift source files
│
├── shared/               # Shared documentation and schemas
├── PLAN.md              # Detailed project plan and roadmap
├── DEVELOPMENT.md       # This file
└── README.md            # Project overview
```

## Development Workflow

### Git Workflow

1. **Always pull latest main before starting work:**
   ```bash
   git checkout main
   git pull origin main
   ```

2. **Create a feature branch:**
   ```bash
   git checkout -b feature/P#-###-brief-description
   ```
   Example: `feature/P2-003-jwt-auth`

3. **Make your changes** (multiple commits are fine)

4. **Update PLAN.md** to check off the task (final commit)

5. **Push and create Pull Request:**
   ```bash
   git push -u origin feature/P#-###-brief-description
   gh pr create
   ```

6. **After PR is merged:**
   ```bash
   git checkout main
   git pull origin main
   git branch -d feature/P#-###-brief-description
   ```

See `PLAN.md` for detailed workflow documentation.

### Code Quality Standards

Both Python projects (backend and question-service) use:
- **black** - Code formatting
- **flake8** - Linting
- **mypy** - Static type checking

**Backend:**
```bash
cd backend
source venv/bin/activate
black . --check
flake8 .
mypy app/
```

**Question Service:**
```bash
cd question-service
source venv/bin/activate
black . --check
flake8 .
mypy .
```

iOS project will use:
- **SwiftLint** - Linting (to be configured in P1-012)
- **SwiftFormat** - Code formatting (to be configured in P1-012)

### Code Review Patterns

We have documented common code review issues and their fixes based on analysis of 50+ follow-up tasks from previous PRs. Review these resources before submitting code:

- **[Code Review Patterns Reference](docs/code-review-patterns.md)** - Comprehensive examples of common issues and fixes, sourced from actual PR review comments

Key patterns to watch for:
1. **Magic numbers** - Extract numeric thresholds to named constants with documentation
2. **Type safety** - Use enums, Literal types, and TypedDict instead of strings and Dict[str, Any]
3. **Database performance** - Include LIMIT clauses, avoid N+1 queries, use indexes
4. **Error handling** - Wrap database operations in try-except with proper context
5. **Test quality** - Use pytest.approx() for floats, cover edge cases, write strong assertions

See `CLAUDE.md` for detailed guidelines on each pattern with code examples.

### Pre-commit Hooks

Pre-commit hooks automatically check code quality before each commit. Install them once:

```bash
pip install pre-commit
pre-commit install
```

**Custom hooks for code review patterns:**

| Hook | Description | Files Checked |
|------|-------------|---------------|
| `check-float-comparisons` | Detects direct float equality in tests (use `pytest.approx()`) | `test_*.py` files |
| `check-magic-numbers` | Flags numeric literals in comparisons that should be constants | Non-test `.py` files in `app/` |

**If a hook fails:**
```bash
# See what files failed
git status

# View the specific error
pre-commit run check-float-comparisons --files backend/tests/test_example.py

# Run all hooks on all files (useful for first-time setup)
pre-commit run --all-files
```

### PR Checklist

All PRs include a code quality checklist in `.github/PULL_REQUEST_TEMPLATE.md`. Before submitting:

1. **Review the checklist** - Each item addresses common review issues
2. **Check applicable items** - Mark items that apply to your changes
3. **N/A items** - You can note items that don't apply (e.g., no database queries)

Key checklist sections:
- **Constants and Configuration** - No magic numbers
- **Type Safety** - Proper use of enums and TypedDict
- **Database Performance** - LIMIT clauses, indexes, no N+1
- **Error Handling** - Try-except with context
- **Caching** - TTL and invalidation (if applicable)
- **Testing** - pytest.approx(), edge cases, strong assertions

### Review Patterns Slash Command

Use the `/review-patterns` command with Claude Code to automatically check your changes for common issues:

```bash
# Review staged changes
/review-patterns

# Review specific files
/review-patterns files=backend/app/api/v1/admin.py,backend/app/core/scoring.py
```

The command checks for:
- Magic numbers in comparisons
- String literals that could use enums
- Dict[str, Any] return types that should use TypedDict
- Database queries without LIMIT
- N+1 query patterns
- Missing caching for expensive operations
- Missing error handling on database operations
- Float comparisons without pytest.approx()
- Weak test assertions
- Short time.sleep() values that may cause CI flakiness

Output includes file, line number, pattern violated, and suggested fix with code examples.

### Running Tests

**Backend:**
```bash
cd backend
source venv/bin/activate
pytest
```

**Question Service:**
```bash
cd question-service
source venv/bin/activate
pytest
```

**iOS:**
```bash
cd ios
xcodebuild test -scheme AIQ -destination 'platform=iOS Simulator,name=iPhone 15'
```

## Common Tasks

### Backend Development

**Check database connection:**
```bash
cd backend
source venv/bin/activate
python -c "from app.core.database import engine; print('Connected:', engine.url)"
```

**Create a new migration:**
```bash
cd backend
source venv/bin/activate
alembic revision --autogenerate -m "Description of changes"
```

**View migration history:**
```bash
cd backend
source venv/bin/activate
alembic history
alembic current
```

**Reset database (caution - deletes all data):**
```bash
cd backend
source venv/bin/activate
alembic downgrade base
alembic upgrade head
```

### Accessing API Documentation

With the backend server running:
- **Swagger UI**: http://localhost:8000/v1/docs
- **ReDoc**: http://localhost:8000/v1/redoc
- **OpenAPI JSON**: http://localhost:8000/v1/openapi.json

### Database Management

**Connect to database:**
```bash
psql -U <your-username> -d aiq_dev
```

**View tables:**
```sql
\dt
```

**View table structure:**
```sql
\d users
\d questions
```

**Query data:**
```sql
SELECT * FROM users;
SELECT * FROM questions LIMIT 10;
```

## Environment Variables

### Backend (.env)

Key variables:
- `DATABASE_URL` - PostgreSQL connection string
- `SECRET_KEY` - Application secret (generate random string)
- `JWT_SECRET_KEY` - JWT token secret (generate random string)
- `DEBUG` - Enable debug mode (True for development)

### Question Service (.env)

Key variables:
- `DATABASE_URL` - Same PostgreSQL database as backend
- `OPENAI_API_KEY` - OpenAI API key
- `ANTHROPIC_API_KEY` - Anthropic API key
- `GOOGLE_API_KEY` - Google API key

**Note**: Never commit `.env` files to git. They are gitignored. Always use `.env.example` as a template.

## Troubleshooting

### Backend won't start

**Issue**: Database connection errors

**Solution**:
- Verify PostgreSQL is running: `psql -U <username> -d aiq_dev -c "SELECT 1;"`
- Check DATABASE_URL in `.env` file
- Ensure database exists: `psql -l`

**Issue**: Import errors or missing modules

**Solution**:
- Verify venv is activated (prompt should show `(venv)`)
- Reinstall dependencies: `pip install -r requirements.txt`

### iOS won't build

**Issue**: Signing errors

**Solution**:
- Open project in Xcode
- Go to project settings → Signing & Capabilities
- Select your Apple Developer team
- Change bundle identifier if needed

### Database migrations fail

**Issue**: Alembic migration errors

**Solution**:
- Check current migration: `alembic current`
- View pending migrations: `alembic heads`
- Reset if needed: `alembic downgrade base` then `alembic upgrade head`

## Getting Help

- **Project Plan**: See `PLAN.md` for detailed roadmap and task list
- **Component READMEs**: Each directory has its own README with specific setup instructions
- **Issues**: Report bugs at https://github.com/gioe/aiq/issues
- **Pull Requests**: Follow the workflow in `PLAN.md`

## Next Steps

After completing setup:

1. Review `PLAN.md` to understand the project roadmap
2. Check the "Current Status" section to see what's been completed
3. Look at "Next Steps" to see what tasks are coming up
4. Pick a task and create a feature branch to start contributing

Happy coding! 🚀
