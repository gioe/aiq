#!/usr/bin/env python3
"""
Create Demo Account for App Store Review (TASK-506)

This script creates a demo account for Apple App Store Review team with
representative test history data.

Usage:
    # Create demo account in production
    DATABASE_URL="postgresql://..." python scripts/create_demo_account.py

    # Dry run (shows what would be created without making changes)
    DATABASE_URL="postgresql://..." python scripts/create_demo_account.py --dry-run

    # Display credentials only (after account is created)
    python scripts/create_demo_account.py --show-credentials
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.models.models import (  # noqa: E402
    User,
    TestSession,
    TestResult,
    Response,
    UserQuestion,
    Question,
    TestStatus,
    EducationLevel,
)

# =============================================================================
# Demo Account Configuration
# =============================================================================

# Demo account email (can be overridden via DEMO_ACCOUNT_EMAIL env var)
DEMO_ACCOUNT_EMAIL = os.environ.get("DEMO_ACCOUNT_EMAIL", "demo-reviewer@aiq-app.com")

# SECURITY: Password MUST be provided via environment variable
# Never hardcode passwords in source code
DEMO_ACCOUNT_PASSWORD = os.environ.get("DEMO_ACCOUNT_PASSWORD")

# Marker to identify demo accounts (prevents accidental deletion)
DEMO_ACCOUNT_MARKER = "APP_STORE_REVIEW_DEMO"


def get_demo_account_config() -> dict:
    """Get demo account configuration, validating required fields."""
    if not DEMO_ACCOUNT_PASSWORD:
        print("ERROR: DEMO_ACCOUNT_PASSWORD environment variable is required")
        print("Set it via: export DEMO_ACCOUNT_PASSWORD='your-secure-password'")
        sys.exit(1)

    return {
        "email": DEMO_ACCOUNT_EMAIL,
        "password": DEMO_ACCOUNT_PASSWORD,
        "first_name": "App Store",
        "last_name": "Reviewer",
        "birth_year": 1990,
        "education_level": EducationLevel.BACHELORS,
        "country": "United States",
        "region": "California",
    }


def print_credentials():
    """Print the demo account credentials info."""
    print("\n" + "=" * 60)
    print("DEMO ACCOUNT INFO FOR APP STORE REVIEW")
    print("=" * 60)
    print(f"\nEmail: {DEMO_ACCOUNT_EMAIL}")
    print("Password: [Set via DEMO_ACCOUNT_PASSWORD environment variable]")
    print("\n" + "-" * 60)
    print("INSTRUCTIONS FOR APP STORE CONNECT:")
    print("-" * 60)
    print(
        """
1. Go to App Store Connect > Your App > App Information
2. Scroll to "App Review Information" section
3. Under "Sign-in Information", enter:
   - User name: {email}
   - Password: <retrieve from 1Password or DEMO_ACCOUNT_PASSWORD env var>
4. In "Notes for Review", add:
   "This is a demo account with pre-populated test history.
   Use it to explore all app features including test results
   and historical data."

IMPORTANT: This account should NOT be deleted from production.
It is marked for monitoring with marker: {marker}
""".format(
            email=DEMO_ACCOUNT_EMAIL,
            marker=DEMO_ACCOUNT_MARKER,
        )
    )
    print("=" * 60 + "\n")


def get_database_session():
    """Create a database session from DATABASE_URL environment variable."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable is required")
        print(
            "Example: DATABASE_URL='postgresql://user:pass@host:5432/db' python scripts/create_demo_account.py"
        )
        sys.exit(1)

    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    return Session()


def create_demo_user(db, dry_run: bool = False) -> Optional[User]:
    """Create the demo user account."""
    config = get_demo_account_config()

    # Check if account already exists
    existing = db.query(User).filter(User.email == config["email"]).first()
    if existing:
        print(f"Demo account already exists with ID: {existing.id}")
        return existing

    if dry_run:
        print("[DRY RUN] Would create demo user:")
        print(f"  Email: {config['email']}")
        print(f"  Name: {config['first_name']} {config['last_name']}")
        return None

    # Create the user
    user = User(
        email=config["email"],
        password_hash=hash_password(config["password"]),
        first_name=config["first_name"],
        last_name=config["last_name"],
        birth_year=config["birth_year"],
        education_level=config["education_level"],
        country=config["country"],
        region=config["region"],
        notification_enabled=True,
        created_at=datetime.now(timezone.utc),
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    print(f"Created demo user with ID: {user.id}")
    return user


def create_test_history(db, user: User, dry_run: bool = False) -> None:
    """Create representative test history for the demo account.

    Creates 2 completed test sessions with realistic data:
    - Test 1: From 8 months ago with score of 112
    - Test 2: From 2 months ago with score of 115

    This shows the app's ability to track cognitive trends over time.
    """
    # Check if test history already exists
    existing_results = (
        db.query(TestResult).filter(TestResult.user_id == user.id).count()
    )
    if existing_results > 0:
        print(
            f"User already has {existing_results} test results. Skipping history creation."
        )
        return

    # Get some questions from the database to use
    questions = db.query(Question).filter(Question.is_active.is_(True)).limit(40).all()
    if len(questions) < 40:
        print(
            f"WARNING: Only {len(questions)} active questions found. Need at least 40 for 2 tests."
        )
        if len(questions) < 20:
            print("ERROR: Not enough questions to create test history")
            return

    if dry_run:
        print("[DRY RUN] Would create 2 completed test sessions:")
        print("  Test 1: 8 months ago, IQ score ~112")
        print("  Test 2: 2 months ago, IQ score ~115")
        return

    # Test session configurations
    test_configs = [
        {
            "date_offset_days": -240,  # 8 months ago
            "iq_score": 112,
            "correct_ratio": 0.65,  # 13/20 correct
            "completion_time": 1200,  # 20 minutes
        },
        {
            "date_offset_days": -60,  # 2 months ago
            "iq_score": 115,
            "correct_ratio": 0.70,  # 14/20 correct
            "completion_time": 1080,  # 18 minutes
        },
    ]

    question_offset = 0

    for i, config in enumerate(test_configs):
        test_date = datetime.now(timezone.utc) + timedelta(
            days=config["date_offset_days"]
        )
        test_questions = questions[question_offset : question_offset + 20]
        question_offset += 20

        if len(test_questions) < 20:
            print(f"Not enough questions for test {i+1}. Skipping.")
            continue

        # Create test session
        session = TestSession(
            user_id=user.id,
            status=TestStatus.COMPLETED,
            started_at=test_date,
            completed_at=test_date + timedelta(seconds=config["completion_time"]),
            composition_metadata=json.dumps(
                {
                    "strategy": "demo_account",
                    "marker": DEMO_ACCOUNT_MARKER,
                }
            ),
        )
        db.add(session)
        db.flush()

        # Calculate how many should be correct
        num_correct = int(20 * config["correct_ratio"])

        # Create responses
        for j, question in enumerate(test_questions):
            is_correct = j < num_correct

            # Mark question as seen
            user_question = UserQuestion(
                user_id=user.id,
                question_id=question.id,
                test_session_id=session.id,
                seen_at=test_date,
            )
            db.add(user_question)

            # Create response
            response = Response(
                test_session_id=session.id,
                user_id=user.id,
                question_id=question.id,
                user_answer=question.correct_answer
                if is_correct
                else "Demo incorrect answer",
                is_correct=is_correct,
                answered_at=test_date + timedelta(seconds=j * 50),
                time_spent_seconds=50 + (j % 10) * 5,  # Vary between 50-95 seconds
            )
            db.add(response)

        # Create test result
        result = TestResult(
            test_session_id=session.id,
            user_id=user.id,
            iq_score=config["iq_score"],
            percentile_rank=79 if config["iq_score"] == 112 else 84,
            total_questions=20,
            correct_answers=num_correct,
            completion_time_seconds=config["completion_time"],
            completed_at=test_date + timedelta(seconds=config["completion_time"]),
            standard_error=4.5,
            ci_lower=config["iq_score"] - 9,
            ci_upper=config["iq_score"] + 9,
            validity_status="valid",
            validity_flags=None,
        )
        db.add(result)

        print(
            f"Created test session {i+1}: Date={test_date.date()}, Score={config['iq_score']}"
        )

    db.commit()
    print("Test history created successfully!")


def verify_account(db, email: str) -> bool:
    """Verify the demo account exists and has data."""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        print(f"Account not found: {email}")
        return False

    results = db.query(TestResult).filter(TestResult.user_id == user.id).all()

    print("\n" + "=" * 60)
    print("DEMO ACCOUNT VERIFICATION")
    print("=" * 60)
    print(f"\nUser ID: {user.id}")
    print(f"Email: {user.email}")
    print(f"Name: {user.first_name} {user.last_name}")
    print(f"Created: {user.created_at}")
    print(f"\nTest Results: {len(results)}")

    for result in results:
        print(
            f"  - Session {result.test_session_id}: Score={result.iq_score}, "
            f"Date={result.completed_at.date() if result.completed_at else 'N/A'}"
        )

    print("\n" + "=" * 60)

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Create demo account for App Store Review"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be created without making changes",
    )
    parser.add_argument(
        "--show-credentials",
        action="store_true",
        help="Display the demo account credentials only",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify the demo account exists and has data",
    )

    args = parser.parse_args()

    if args.show_credentials:
        print_credentials()
        return

    # Need database for other operations
    db = get_database_session()

    try:
        if args.verify:
            verify_account(db, DEMO_ACCOUNT_EMAIL)
            return

        if args.dry_run:
            print("\n[DRY RUN MODE - No changes will be made]\n")

        # Step 1: Create demo user
        print("Step 1: Creating demo user account...")
        user = create_demo_user(db, dry_run=args.dry_run)

        if user:
            # Step 2: Create test history
            print("\nStep 2: Creating test history...")
            create_test_history(db, user, dry_run=args.dry_run)

        if not args.dry_run and user:
            # Verify and show credentials
            verify_account(db, DEMO_ACCOUNT_EMAIL)
            print_credentials()

        print("\nDemo account setup complete!")

    finally:
        db.close()


if __name__ == "__main__":
    main()
