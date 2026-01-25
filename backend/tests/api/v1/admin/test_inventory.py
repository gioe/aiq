"""
Tests for inventory health admin endpoint.

Tests cover:
- Complete inventory health report generation
- Custom threshold configuration
- Alert generation for low inventory
- Status classification (healthy/warning/critical)
- Empty database edge case
- Authentication requirements
"""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import DifficultyLevel, Question, QuestionType


class TestInventoryHealth:
    """Tests for GET /v1/admin/inventory-health endpoint."""

    def test_inventory_health_requires_admin_token(
        self,
        client: TestClient,
    ):
        """Test that endpoint requires admin token."""
        response = client.get("/v1/admin/inventory-health")
        assert response.status_code == 422  # Missing required header

        response = client.get(
            "/v1/admin/inventory-health",
            headers={"X-Admin-Token": "invalid-token"},
        )
        assert response.status_code == 401

    def test_inventory_health_empty_database(
        self,
        client: TestClient,
        admin_headers: dict,
    ):
        """Test inventory health with no questions."""
        response = client.get(
            "/v1/admin/inventory-health",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify structure
        assert data["total_active_questions"] == 0
        assert len(data["strata"]) == 18  # 6 types × 3 difficulties
        assert len(data["alerts"]) == 18  # All strata below healthy threshold

        # All strata should be critical with 0 count
        for stratum in data["strata"]:
            assert stratum["count"] == 0
            assert stratum["status"] == "critical"

        # Verify thresholds
        assert data["thresholds"]["healthy_min"] == 50
        assert data["thresholds"]["warning_min"] == 20

        # Verify summary
        assert data["summary"]["healthy"] == 0
        assert data["summary"]["warning"] == 0
        assert data["summary"]["critical"] == 18

    def test_inventory_health_with_questions(
        self,
        client: TestClient,
        admin_headers: dict,
        db_session: Session,
    ):
        """Test inventory health with mixed question counts."""
        # Create questions in different strata with varying counts
        # Pattern/easy: 60 (healthy)
        for _ in range(60):
            q = Question(
                question_text="Test question",
                question_type=QuestionType.PATTERN,
                difficulty_level=DifficultyLevel.EASY,
                correct_answer="A",
                is_active=True,
                quality_flag="normal",
            )
            db_session.add(q)

        # Pattern/medium: 35 (warning)
        for _ in range(35):
            q = Question(
                question_text="Test question",
                question_type=QuestionType.PATTERN,
                difficulty_level=DifficultyLevel.MEDIUM,
                correct_answer="A",
                is_active=True,
                quality_flag="normal",
            )
            db_session.add(q)

        # Spatial/hard: 15 (critical)
        for _ in range(15):
            q = Question(
                question_text="Test question",
                question_type=QuestionType.SPATIAL,
                difficulty_level=DifficultyLevel.HARD,
                correct_answer="A",
                is_active=True,
                quality_flag="normal",
            )
            db_session.add(q)

        # Logic/easy: 25 (warning)
        for _ in range(25):
            q = Question(
                question_text="Test question",
                question_type=QuestionType.LOGIC,
                difficulty_level=DifficultyLevel.EASY,
                correct_answer="A",
                is_active=True,
                quality_flag="normal",
            )
            db_session.add(q)

        db_session.commit()

        response = client.get(
            "/v1/admin/inventory-health",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify total
        assert data["total_active_questions"] == 135  # 60 + 35 + 15 + 25

        # Verify strata count (all 18 combinations should be present)
        assert len(data["strata"]) == 18

        # Find specific strata and verify status
        pattern_easy = next(
            s
            for s in data["strata"]
            if s["question_type"] == "pattern" and s["difficulty"] == "easy"
        )
        assert pattern_easy["count"] == 60
        assert pattern_easy["status"] == "healthy"

        pattern_medium = next(
            s
            for s in data["strata"]
            if s["question_type"] == "pattern" and s["difficulty"] == "medium"
        )
        assert pattern_medium["count"] == 35
        assert pattern_medium["status"] == "warning"

        spatial_hard = next(
            s
            for s in data["strata"]
            if s["question_type"] == "spatial" and s["difficulty"] == "hard"
        )
        assert spatial_hard["count"] == 15
        assert spatial_hard["status"] == "critical"

        logic_easy = next(
            s
            for s in data["strata"]
            if s["question_type"] == "logic" and s["difficulty"] == "easy"
        )
        assert logic_easy["count"] == 25
        assert logic_easy["status"] == "warning"

        # Verify summary counts
        # 1 healthy (pattern/easy), rest should be warning or critical
        assert data["summary"]["healthy"] == 1
        assert data["summary"]["warning"] + data["summary"]["critical"] == 17

        # Verify alerts exist for low inventory strata
        assert len(data["alerts"]) > 0

        # Pattern/easy should not have alert (healthy)
        pattern_easy_alerts = [
            a
            for a in data["alerts"]
            if a["question_type"] == "pattern" and a["difficulty"] == "easy"
        ]
        assert len(pattern_easy_alerts) == 0

        # Spatial/hard should have critical alert
        spatial_hard_alerts = [
            a
            for a in data["alerts"]
            if a["question_type"] == "spatial" and a["difficulty"] == "hard"
        ]
        assert len(spatial_hard_alerts) == 1
        assert spatial_hard_alerts[0]["severity"] == "critical"
        assert spatial_hard_alerts[0]["count"] == 15
        assert "Critical inventory" in spatial_hard_alerts[0]["message"]

        # Pattern/medium should have warning alert
        pattern_medium_alerts = [
            a
            for a in data["alerts"]
            if a["question_type"] == "pattern" and a["difficulty"] == "medium"
        ]
        assert len(pattern_medium_alerts) == 1
        assert pattern_medium_alerts[0]["severity"] == "warning"
        assert pattern_medium_alerts[0]["count"] == 35
        assert "Low inventory" in pattern_medium_alerts[0]["message"]

    def test_inventory_health_excludes_flagged_questions(
        self,
        client: TestClient,
        admin_headers: dict,
        db_session: Session,
    ):
        """Test that under_review and deactivated questions are excluded."""
        # Create normal questions
        for _ in range(30):
            q = Question(
                question_text="Normal question",
                question_type=QuestionType.MATH,
                difficulty_level=DifficultyLevel.MEDIUM,
                correct_answer="A",
                is_active=True,
                quality_flag="normal",
            )
            db_session.add(q)

        # Create under_review questions (should be excluded)
        for _ in range(10):
            q = Question(
                question_text="Under review question",
                question_type=QuestionType.MATH,
                difficulty_level=DifficultyLevel.MEDIUM,
                correct_answer="A",
                is_active=True,
                quality_flag="under_review",
            )
            db_session.add(q)

        # Create deactivated questions (should be excluded)
        for _ in range(5):
            q = Question(
                question_text="Deactivated question",
                question_type=QuestionType.MATH,
                difficulty_level=DifficultyLevel.MEDIUM,
                correct_answer="A",
                is_active=True,
                quality_flag="deactivated",
            )
            db_session.add(q)

        db_session.commit()

        response = client.get(
            "/v1/admin/inventory-health",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Should only count the 30 normal questions
        math_medium = next(
            s
            for s in data["strata"]
            if s["question_type"] == "math" and s["difficulty"] == "medium"
        )
        assert math_medium["count"] == 30
        assert math_medium["status"] == "warning"  # Below 50 threshold

    def test_inventory_health_excludes_inactive_questions(
        self,
        client: TestClient,
        admin_headers: dict,
        db_session: Session,
    ):
        """Test that inactive questions are excluded from inventory."""
        # Create active questions
        for _ in range(25):
            q = Question(
                question_text="Active question",
                question_type=QuestionType.VERBAL,
                difficulty_level=DifficultyLevel.EASY,
                correct_answer="A",
                is_active=True,
                quality_flag="normal",
            )
            db_session.add(q)

        # Create inactive questions (should be excluded)
        for _ in range(20):
            q = Question(
                question_text="Inactive question",
                question_type=QuestionType.VERBAL,
                difficulty_level=DifficultyLevel.EASY,
                correct_answer="A",
                is_active=False,
                quality_flag="normal",
            )
            db_session.add(q)

        db_session.commit()

        response = client.get(
            "/v1/admin/inventory-health",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Should only count the 25 active questions
        verbal_easy = next(
            s
            for s in data["strata"]
            if s["question_type"] == "verbal" and s["difficulty"] == "easy"
        )
        assert verbal_easy["count"] == 25
        assert verbal_easy["status"] == "warning"

    def test_inventory_health_custom_thresholds(
        self,
        client: TestClient,
        admin_headers: dict,
        db_session: Session,
    ):
        """Test custom threshold parameters."""
        # Create 40 questions
        for _ in range(40):
            q = Question(
                question_text="Test question",
                question_type=QuestionType.MEMORY,
                difficulty_level=DifficultyLevel.HARD,
                correct_answer="A",
                is_active=True,
                quality_flag="normal",
            )
            db_session.add(q)

        db_session.commit()

        # With default thresholds (50/20), 40 should be warning
        response = client.get(
            "/v1/admin/inventory-health",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()

        memory_hard = next(
            s
            for s in data["strata"]
            if s["question_type"] == "memory" and s["difficulty"] == "hard"
        )
        assert memory_hard["count"] == 40
        assert memory_hard["status"] == "warning"

        # With custom thresholds (30/10), 40 should be healthy
        response = client.get(
            "/v1/admin/inventory-health?healthy_min=30&warning_min=10",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()

        assert data["thresholds"]["healthy_min"] == 30
        assert data["thresholds"]["warning_min"] == 10

        memory_hard = next(
            s
            for s in data["strata"]
            if s["question_type"] == "memory" and s["difficulty"] == "hard"
        )
        assert memory_hard["count"] == 40
        assert memory_hard["status"] == "healthy"

        # Should have fewer alerts with lower thresholds
        assert len(data["alerts"]) < 18  # Not all strata will be below threshold

    def test_inventory_health_threshold_validation(
        self,
        client: TestClient,
        admin_headers: dict,
    ):
        """Test that warning_min must be <= healthy_min."""
        # Invalid: warning_min > healthy_min
        response = client.get(
            "/v1/admin/inventory-health?healthy_min=20&warning_min=50",
            headers=admin_headers,
        )
        assert response.status_code == 500
        assert "warning_min" in response.json()["detail"]
        assert "must be <=" in response.json()["detail"]

    def test_inventory_health_alert_sorting(
        self,
        client: TestClient,
        admin_headers: dict,
        db_session: Session,
    ):
        """Test that alerts are sorted by severity (critical first) then count."""
        # Create questions with various counts to generate mixed alerts
        # Critical alert (count=10)
        for _ in range(10):
            q = Question(
                question_text="Test",
                question_type=QuestionType.PATTERN,
                difficulty_level=DifficultyLevel.EASY,
                correct_answer="A",
                is_active=True,
                quality_flag="normal",
            )
            db_session.add(q)

        # Warning alert (count=30)
        for _ in range(30):
            q = Question(
                question_text="Test",
                question_type=QuestionType.LOGIC,
                difficulty_level=DifficultyLevel.MEDIUM,
                correct_answer="A",
                is_active=True,
                quality_flag="normal",
            )
            db_session.add(q)

        # Critical alert (count=5)
        for _ in range(5):
            q = Question(
                question_text="Test",
                question_type=QuestionType.SPATIAL,
                difficulty_level=DifficultyLevel.HARD,
                correct_answer="A",
                is_active=True,
                quality_flag="normal",
            )
            db_session.add(q)

        db_session.commit()

        response = client.get(
            "/v1/admin/inventory-health",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()

        # Find our specific alerts
        pattern_easy = next(
            a
            for a in data["alerts"]
            if a["question_type"] == "pattern" and a["difficulty"] == "easy"
        )
        logic_medium = next(
            a
            for a in data["alerts"]
            if a["question_type"] == "logic" and a["difficulty"] == "medium"
        )
        spatial_hard = next(
            a
            for a in data["alerts"]
            if a["question_type"] == "spatial" and a["difficulty"] == "hard"
        )

        # Critical alerts should come before warning alerts
        pattern_easy_idx = data["alerts"].index(pattern_easy)
        logic_medium_idx = data["alerts"].index(logic_medium)
        spatial_hard_idx = data["alerts"].index(spatial_hard)

        # Both critical alerts should be before the warning alert
        assert pattern_easy_idx < logic_medium_idx
        assert spatial_hard_idx < logic_medium_idx

        # Among critical alerts, lower count should come first
        assert spatial_hard_idx < pattern_easy_idx

    def test_inventory_health_strata_sorting(
        self,
        client: TestClient,
        admin_headers: dict,
        db_session: Session,
    ):
        """Test that strata are sorted by type then difficulty."""
        # Create a few questions to have non-empty strata
        for q_type in [QuestionType.PATTERN, QuestionType.VERBAL]:
            for difficulty in DifficultyLevel:
                q = Question(
                    question_text="Test",
                    question_type=q_type,
                    difficulty_level=difficulty,
                    correct_answer="A",
                    is_active=True,
                    quality_flag="normal",
                )
                db_session.add(q)

        db_session.commit()

        response = client.get(
            "/v1/admin/inventory-health",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()

        # Verify strata are sorted alphabetically by type, then by difficulty
        prev_sort_key = None

        for stratum in data["strata"]:
            current_sort_key = (stratum["question_type"], stratum["difficulty"])

            if prev_sort_key is not None:
                # Verify current comes after previous in sort order
                assert (
                    current_sort_key > prev_sort_key
                ), f"Sort order violation: {current_sort_key} should come after {prev_sort_key}"

            prev_sort_key = current_sort_key

    def test_inventory_health_response_structure(
        self,
        client: TestClient,
        admin_headers: dict,
        db_session: Session,
    ):
        """Test complete response structure matches schema."""
        # Create a single question for non-empty response
        q = Question(
            question_text="Test",
            question_type=QuestionType.MATH,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            is_active=True,
            quality_flag="normal",
        )
        db_session.add(q)
        db_session.commit()

        response = client.get(
            "/v1/admin/inventory-health",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()

        # Verify all required top-level fields
        assert "total_active_questions" in data
        assert "strata" in data
        assert "alerts" in data
        assert "thresholds" in data
        assert "summary" in data

        # Verify strata structure
        assert isinstance(data["strata"], list)
        for stratum in data["strata"]:
            assert "question_type" in stratum
            assert "difficulty" in stratum
            assert "count" in stratum
            assert "status" in stratum
            assert stratum["status"] in ["healthy", "warning", "critical"]

        # Verify alerts structure
        assert isinstance(data["alerts"], list)
        for alert in data["alerts"]:
            assert "question_type" in alert
            assert "difficulty" in alert
            assert "count" in alert
            assert "threshold" in alert
            assert "message" in alert
            assert "severity" in alert
            assert alert["severity"] in ["warning", "critical"]

        # Verify thresholds structure
        assert "healthy_min" in data["thresholds"]
        assert "warning_min" in data["thresholds"]

        # Verify summary structure
        assert "healthy" in data["summary"]
        assert "warning" in data["summary"]
        assert "critical" in data["summary"]
        assert (
            data["summary"]["healthy"]
            + data["summary"]["warning"]
            + data["summary"]["critical"]
            == 18
        )
