# Reusable Components Plan

## Vision

Build a personal "app factory" - a collection of templates and packages that eliminate repetitive setup work, allowing faster iteration on new project ideas.

**Goal:** Never build auth, API structure, or database setup from scratch again.

**Key Principle:** Extract patterns incrementally as they prove useful across multiple projects, rather than over-engineering upfront.

---

## The Strategy

### Phase 1: Templates (Start Here)
Create starter templates from proven code (like this IQ tracker project).

### Phase 2: Packages
Extract truly reusable utilities into pip-installable packages.

### Phase 3: Arsenal
Build a comprehensive toolbox that grows with each project.

---

## Implementation Roadmap

### Stage 1: Create FastAPI Starter Template (2-3 hours)

**Goal:** A ready-to-clone template for new FastAPI projects.

**Steps:**

1. **Create new repo: `fastapi-starter-template`**
   ```bash
   mkdir ~/fastapi-starter-template
   cd ~/fastapi-starter-template
   git init
   ```

2. **Copy core components from iq-tracker:**
   ```
   fastapi-starter-template/
   ├── app/
   │   ├── core/              # FROM: iq-tracker/backend/app/core/
   │   │   ├── config.py      # Settings management
   │   │   ├── security.py    # JWT + password hashing
   │   │   └── auth.py        # FastAPI dependencies
   │   ├── models/            # FROM: iq-tracker/backend/app/models/
   │   │   ├── base.py        # SQLAlchemy base, get_db
   │   │   └── models.py      # User model (template)
   │   ├── schemas/           # FROM: iq-tracker/backend/app/schemas/
   │   │   └── auth.py        # Auth request/response schemas
   │   ├── api/
   │   │   └── v1/
   │   │       ├── api.py     # Router aggregation
   │   │       ├── auth.py    # Auth endpoints
   │   │       ├── user.py    # User profile endpoints
   │   │       └── health.py  # Health check
   │   └── main.py            # FastAPI app initialization
   ├── alembic/               # FROM: iq-tracker/backend/alembic/
   │   ├── env.py
   │   └── versions/
   │       └── initial_user_model.py
   ├── tests/                 # FROM: iq-tracker/backend/tests/
   │   ├── __init__.py
   │   └── test_placeholder.py
   ├── .github/
   │   └── workflows/
   │       └── ci.yml         # FROM: iq-tracker/.github/workflows/backend-ci.yml
   ├── requirements.txt       # FROM: iq-tracker/backend/requirements.txt
   ├── .env.example          # FROM: iq-tracker/backend/.env.example
   ├── pyproject.toml        # FROM: iq-tracker/backend/pyproject.toml
   ├── .gitignore
   └── README.md             # New: Usage instructions
   ```

3. **Replace project-specific values with template variables:**
   - Project name: `{{PROJECT_NAME}}`
   - Database name: `{{DB_NAME}}`
   - Description: `{{DESCRIPTION}}`
   - API prefix: Keep as `/v1/` (standard)

4. **Remove IQ-tracker-specific code:**
   - Delete: Question, TestSession, Response, TestResult models
   - Delete: Question-related endpoints
   - Keep: User model, auth endpoints, user profile endpoints

5. **Create setup script (`setup.sh`):**
   ```bash
   #!/bin/bash

   echo "🚀 FastAPI Project Setup"
   echo ""
   read -p "Project name (e.g., recipe-app): " PROJECT_NAME
   read -p "Database name (e.g., recipe_db): " DB_NAME
   read -p "Short description: " DESCRIPTION

   # Replace template variables
   find . -type f -not -path "./.git/*" -exec sed -i "" "s/{{PROJECT_NAME}}/$PROJECT_NAME/g" {} \;
   find . -type f -not -path "./.git/*" -exec sed -i "" "s/{{DB_NAME}}/$DB_NAME/g" {} \;
   find . -type f -not -path "./.git/*" -exec sed -i "" "s/{{DESCRIPTION}}/$DESCRIPTION/g" {} \;

   # Setup Python environment
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt

   # Setup database
   createdb $DB_NAME
   alembic upgrade head

   echo ""
   echo "✅ $PROJECT_NAME is ready!"
   echo ""
   echo "Next steps:"
   echo "  1. Update .env with your settings"
   echo "  2. source venv/bin/activate"
   echo "  3. uvicorn app.main:app --reload"
   ```

6. **Write comprehensive README.md:**
   ```markdown
   # FastAPI Starter Template

   A production-ready FastAPI template with authentication, user management, and database setup.

   ## Features
   - ✅ JWT authentication (access + refresh tokens)
   - ✅ User registration and login
   - ✅ User profile management
   - ✅ PostgreSQL + SQLAlchemy + Alembic
   - ✅ Pydantic validation
   - ✅ Password hashing (bcrypt)
   - ✅ API documentation (Swagger/OpenAPI)
   - ✅ Pre-commit hooks (black, flake8, mypy)
   - ✅ GitHub Actions CI/CD

   ## Quick Start

   ```bash
   # 1. Clone or use as template
   git clone <your-template-repo> my-new-app
   cd my-new-app

   # 2. Run setup
   chmod +x setup.sh
   ./setup.sh

   # 3. Start coding your app-specific features!
   ```

   ## What to Customize

   ### Add Your Models
   ```python
   # app/models/models.py
   class Recipe(Base):
       __tablename__ = "recipes"
       # Your app-specific model
   ```

   ### Add Your Endpoints
   ```python
   # app/api/v1/recipes.py
   router = APIRouter()

   @router.get("/recipes")
   def get_recipes(): ...
   ```

   ### Register Your Router
   ```python
   # app/api/v1/api.py
   from app.api.v1 import recipes
   api_router.include_router(recipes.router, prefix="/recipes")
   ```

   ## Project Structure
   (Include detailed structure explanation)
   ```

7. **Test the template:**
   - Use it to create a dummy project
   - Time the setup process
   - Note any friction points
   - Iterate

8. **Push to GitHub as a template repository:**
   - Enable "Template repository" in GitHub settings
   - Tag with topics: `fastapi`, `template`, `starter`, `authentication`

**Deliverable:** A GitHub template repository that can be cloned for any new FastAPI project.

---

### Stage 2: Extract Core Utilities Package (After 2-3 projects)

**Goal:** Create `fastapi-auth-toolkit` - a pip-installable package with the most reusable auth utilities.

**When:** After you've used the template 2-3 times and know what's truly universal.

**Steps:**

1. **Create package structure:**
   ```
   fastapi-auth-toolkit/
   ├── src/
   │   └── fastapi_auth_toolkit/
   │       ├── __init__.py
   │       ├── security.py      # Password + JWT functions
   │       ├── dependencies.py  # get_current_user, etc.
   │       ├── schemas.py       # Base auth schemas
   │       └── middleware.py    # Optional: rate limiting, etc.
   ├── tests/
   ├── pyproject.toml
   ├── README.md
   └── LICENSE
   ```

2. **Extract from template:**
   - Copy `security.py` functions (fully reusable)
   - Copy `dependencies.py` (mostly reusable)
   - Create base Pydantic schemas

3. **Make it configurable:**
   ```python
   # fastapi_auth_toolkit/__init__.py
   class AuthConfig:
       jwt_secret: str
       jwt_algorithm: str = "HS256"
       access_token_expire_minutes: int = 30
       refresh_token_expire_days: int = 7

   def setup_auth(config: AuthConfig):
       """Configure the auth toolkit with your settings."""
       # Store config globally or return configured functions
   ```

4. **Install locally during development:**
   ```bash
   # In the package directory
   pip install -e .

   # In your projects
   pip install git+https://github.com/yourusername/fastapi-auth-toolkit.git
   ```

5. **Usage in projects:**
   ```python
   from fastapi_auth_toolkit import hash_password, create_access_token
   from fastapi_auth_toolkit.dependencies import get_current_user

   # Use directly
   hashed = hash_password("secret123")
   token = create_access_token({"user_id": 1})

   # In endpoints
   @router.get("/protected")
   def protected_route(current_user: User = Depends(get_current_user)):
       return {"user": current_user.email}
   ```

**Deliverable:** A pip-installable package with core auth utilities.

---

### Stage 3: Build Your Dev Toolbox (Ongoing)

**Goal:** A comprehensive personal repository of templates, packages, and utilities.

**Structure:**
```
my-dev-toolbox/
├── templates/
│   ├── fastapi-starter/              # Stage 1 output
│   ├── fastapi-nextjs-fullstack/     # Future: full-stack template
│   ├── django-api/                   # Future: if you use Django
│   └── flask-minimal/                # Future: lightweight projects
│
├── packages/
│   ├── fastapi-auth-toolkit/         # Stage 2 output
│   ├── my-email-sender/              # Future: email utilities
│   ├── my-s3-uploader/               # Future: file upload utilities
│   └── my-db-toolkit/                # Future: database utilities
│
├── snippets/
│   ├── fastapi/
│   │   ├── middleware-examples.py
│   │   ├── exception-handlers.py
│   │   ├── background-tasks.py
│   │   └── websocket-setup.py
│   ├── docker/
│   │   ├── Dockerfile.fastapi
│   │   ├── Dockerfile.nextjs
│   │   └── docker-compose.yml
│   ├── github-actions/
│   │   ├── deploy-to-fly.yml
│   │   ├── run-tests.yml
│   │   └── docker-build.yml
│   └── alembic/
│       └── common-migrations/
│
├── scripts/
│   ├── create-fastapi-project.sh     # Automate project creation
│   ├── setup-postgres.sh             # Database setup
│   ├── deploy-to-fly.sh              # Deployment automation
│   └── backup-db.sh                  # Database backup
│
└── README.md                          # Master index of everything
```

**Grow incrementally:**
- After each project, extract patterns that repeated
- Add new templates for different tech stacks
- Build packages for truly reusable logic
- Document everything

---

## What to Extract from IQ Tracker

### Highly Reusable (Extract to template & package)

**From `backend/app/core/`:**
- ✅ `config.py` - Settings pattern (template)
- ✅ `security.py` - JWT + password hashing (package)
- ✅ `auth.py` - FastAPI dependencies (package)

**From `backend/app/models/`:**
- ✅ `base.py` - SQLAlchemy setup (template)
- ✅ `User` model (template - base to customize)

**From `backend/app/schemas/`:**
- ✅ `auth.py` - Auth schemas (template/package)

**From `backend/app/api/v1/`:**
- ✅ `auth.py` - Auth endpoints (template)
- ✅ `user.py` - User profile endpoints (template)
- ✅ `health.py` - Health check (template)
- ✅ `api.py` - Router pattern (template)

**From `backend/app/`:**
- ✅ `main.py` - FastAPI setup (template)

**From `backend/`:**
- ✅ `requirements.txt` - Base dependencies (template)
- ✅ `.env.example` - Environment template (template)
- ✅ `pyproject.toml` - Tool configs (template)
- ✅ `alembic/` - Migration setup (template)

**From `.github/workflows/`:**
- ✅ `backend-ci.yml` - CI/CD pipeline (template)

**From root:**
- ✅ `.pre-commit-config.yaml` - Code quality (template)

### Project-Specific (Keep in IQ tracker only)

**From `backend/app/models/`:**
- ❌ `Question`, `TestSession`, `Response`, `TestResult` models
- ❌ Question-related enums

**From `backend/app/api/v1/`:**
- ❌ Question serving endpoints (future)
- ❌ Test management endpoints (future)
- ❌ IQ scoring logic (future)

---

## Other Components to Templatize (Future)

As you build more projects, consider extracting these patterns:

| Component | When to Extract | Type |
|-----------|----------------|------|
| Email sending | After 2nd project using email | Package |
| File uploads (S3/local) | After 1st project with uploads | Package |
| Background jobs (Celery/RQ) | After 2nd project with async tasks | Template |
| Rate limiting middleware | After 1st production app | Package |
| Logging setup (structured) | After 1st production app | Template |
| Docker setup | After 2nd containerized project | Template |
| Payment integration (Stripe) | After 1st paid app | Package |
| Admin dashboard | After 2nd project needing admin | Template |
| Social auth (Google/GitHub) | When you need it | Template/Package |
| Email verification flow | After 1st public-facing app | Template |
| Password reset flow | After 1st public-facing app | Template |
| API versioning pattern | After 1st breaking change | Template |

---

## Getting Started Checklist

When you're ready to implement this:

### Prerequisites
- [ ] IQ tracker project is complete (or at a stable point)
- [ ] You have GitHub account set up
- [ ] You have 2-3 hours of focused time

### Stage 1 Tasks
- [ ] Create `fastapi-starter-template` repo
- [ ] Copy files from iq-tracker (see structure above)
- [ ] Remove IQ-specific code
- [ ] Add template variables `{{PROJECT_NAME}}`, etc.
- [ ] Write `setup.sh` script
- [ ] Write comprehensive README
- [ ] Test by creating a dummy project
- [ ] Enable as GitHub template repository
- [ ] Document lessons learned

### Stage 2 Tasks (After 2-3 projects)
- [ ] Create `fastapi-auth-toolkit` package structure
- [ ] Extract `security.py` to package
- [ ] Extract `dependencies.py` to package
- [ ] Add configuration system
- [ ] Write package README
- [ ] Install in 2 existing projects to validate
- [ ] Refine API based on usage

### Stage 3 (Ongoing)
- [ ] Create `my-dev-toolbox` repo as central hub
- [ ] Move templates into organized structure
- [ ] Add snippets as you discover patterns
- [ ] Add automation scripts
- [ ] Document everything in master README
- [ ] Review and improve quarterly

---

## Success Metrics

You'll know this is working when:

1. **Time to "Hello World"**:
   - Without template: 2-3 days
   - With template: 2-3 hours
   - **Goal: 10x faster**

2. **Excitement to start new projects**:
   - Before: "Ugh, I have to set up auth again"
   - After: "I can clone my template and start coding features!"

3. **Project count**:
   - Track how many projects you ship
   - Template should remove barrier to experimentation

4. **Code reuse**:
   - Measure: Do you copy-paste or git clone?
   - Goal: Git clone > copy-paste

---

## Resources & References

### Creating Python Packages
- [Python Packaging Guide](https://packaging.python.org/)
- [Poetry Documentation](https://python-poetry.org/) (modern alternative to setup.py)
- [Publishing to PyPI](https://packaging.python.org/tutorials/packaging-projects/)

### Template Repositories
- [GitHub Template Repositories](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-template-repository)
- [Cookiecutter](https://cookiecutter.readthedocs.io/) (advanced templating)

### Inspiration (Other People's Toolboxes)
- [Full Stack FastAPI PostgreSQL](https://github.com/tiangolo/full-stack-fastapi-postgresql) by FastAPI creator
- [Awesome FastAPI](https://github.com/mjhea0/awesome-fastapi) - curated templates

### FastAPI Patterns
- [FastAPI Best Practices](https://github.com/zhanymkanov/fastapi-best-practices)
- [SQLAlchemy Patterns](https://docs.sqlalchemy.org/en/14/orm/patterns.html)

---

## Notes & Observations

### What Works Well
- Templates for structural patterns (API setup, project layout)
- Packages for pure utility functions (JWT, hashing)
- Snippets for one-off patterns (middleware, exception handlers)

### What Doesn't Work
- Over-abstracting too early (wait for 3rd use)
- Rigid frameworks (flexibility > DRY for personal projects)
- Complex configuration (keep it simple)
- Packaging everything (some things are better as templates)

### Key Principles
1. **Optimize for speed of new project setup**
2. **Extract after patterns prove useful (not before)**
3. **Prefer flexibility over DRY for personal projects**
4. **Document future-you will thank you**
5. **Test templates by actually using them**

---

## Version History

- **v1.0** (2024-11-05): Initial vision document created during IQ Tracker Phase 2 development

---

## Next Actions

When you're ready to start:

1. **Read this document fully**
2. **Decide which stage to begin with** (recommend Stage 1)
3. **Block 2-3 hours of focused time**
4. **Follow the checklist**
5. **Test the output immediately**
6. **Iterate based on real usage**

Remember: **Don't over-engineer.** Start with a simple template, use it on a real project, and improve as you learn what actually helps vs. what sounds good in theory.

---

*This document captures the vision for building a personal "app factory" that reduces the barrier to starting new projects. Update this document as you learn what works and what doesn't.*
