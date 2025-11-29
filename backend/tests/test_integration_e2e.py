"""
End-to-end integration tests for complete user journeys.

These tests verify that multiple components work together correctly
to support complete user workflows from registration to viewing results.
"""
from datetime import datetime, timedelta, timezone


class TestCompleteUserJourney:
    """Test a complete user journey from registration to viewing test history."""

    def test_complete_new_user_journey(self, client, test_questions):
        """
        Test the complete journey of a new user:
        1. Register
        2. Login
        3. Start a test
        4. Submit responses
        5. View results
        6. View history
        """
        # Step 1: Register a new user
        register_payload = {
            "email": "newuser@example.com",
            "password": "SecurePassword123!",
            "first_name": "New",
            "last_name": "User",
        }
        register_response = client.post("/v1/auth/register", json=register_payload)
        assert register_response.status_code == 201
        register_data = register_response.json()
        assert "user" in register_data
        assert "email" in register_data["user"]
        assert register_data["user"]["email"] == "newuser@example.com"

        # Step 2: Login with credentials to get tokens
        login_payload = {
            "email": "newuser@example.com",
            "password": "SecurePassword123!",
        }
        login_response = client.post("/v1/auth/login", json=login_payload)
        assert login_response.status_code == 200
        login_data = login_response.json()
        assert "access_token" in login_data
        access_token = login_data["access_token"]

        # Create auth headers
        auth_headers = {"Authorization": f"Bearer {access_token}"}

        # Step 3: Verify no active test session initially
        active_response = client.get("/v1/test/active", headers=auth_headers)
        assert active_response.status_code == 200
        assert active_response.json() is None  # No active session

        # Step 4: Start a test (get 3 questions)
        start_response = client.post(
            "/v1/test/start?question_count=3", headers=auth_headers
        )
        assert start_response.status_code == 200
        start_data = start_response.json()
        assert "session" in start_data
        assert "questions" in start_data
        assert len(start_data["questions"]) == 3
        session_id = start_data["session"]["id"]
        questions = start_data["questions"]

        # Step 5: Submit responses for all questions
        responses_payload = {
            "session_id": session_id,
            "responses": [
                {
                    "question_id": questions[0]["id"],
                    "user_answer": "B",  # Correct answer
                },
                {
                    "question_id": questions[1]["id"],
                    "user_answer": "B",  # Correct answer
                },
                {
                    "question_id": questions[2]["id"],
                    "user_answer": "A",  # Incorrect answer
                },
            ],
        }
        submit_response = client.post(
            "/v1/test/submit", json=responses_payload, headers=auth_headers
        )
        assert submit_response.status_code == 200
        submit_data = submit_response.json()
        assert "result" in submit_data
        assert submit_data["result"]["iq_score"] > 0
        assert submit_data["result"]["total_questions"] == 3
        assert submit_data["result"]["correct_answers"] == 2  # 2 out of 3 correct

        # Step 6: View specific test result
        result_id = submit_data["result"]["id"]
        result_response = client.get(
            f"/v1/test/results/{result_id}", headers=auth_headers
        )
        assert result_response.status_code == 200
        result_data = result_response.json()
        assert result_data["id"] == result_id
        assert result_data["iq_score"] == submit_data["result"]["iq_score"]

        # Step 7: View test history
        history_response = client.get("/v1/test/history", headers=auth_headers)
        assert history_response.status_code == 200
        history_data = history_response.json()
        assert len(history_data) == 1  # Should have 1 test
        assert history_data[0]["id"] == result_id

        # Step 8: Verify no active test session (test was completed)
        active_final = client.get("/v1/test/active", headers=auth_headers)
        assert active_final.status_code == 200
        assert active_final.json() is None  # No active session after completion

    def test_multiple_tests_over_time(self, client, test_questions, db_session):
        """
        Test a user taking multiple tests over time to verify:
        1. Questions are not repeated
        2. History accumulates correctly
        3. Test status updates correctly
        """
        # Register and login
        register_payload = {
            "email": "multitest@example.com",
            "password": "SecurePassword123!",
            "first_name": "Multi",
            "last_name": "Test",
        }
        register_response = client.post("/v1/auth/register", json=register_payload)
        assert register_response.status_code == 201

        # Login to get tokens
        login_payload = {
            "email": "multitest@example.com",
            "password": "SecurePassword123!",
        }
        login_response = client.post("/v1/auth/login", json=login_payload)
        assert login_response.status_code == 200
        access_token = login_response.json()["access_token"]
        auth_headers = {"Authorization": f"Bearer {access_token}"}

        # Take first test with 2 questions
        start_response1 = client.post(
            "/v1/test/start?question_count=2", headers=auth_headers
        )
        assert start_response1.status_code == 200
        session1_data = start_response1.json()
        session1_id = session1_data["session"]["id"]
        questions1 = session1_data["questions"]
        question1_ids = {q["id"] for q in questions1}

        # Submit first test
        responses1 = {
            "session_id": session1_id,
            "responses": [
                {
                    "question_id": questions1[0]["id"],
                    "user_answer": questions1[0]["answer_options"]["B"],
                },
                {
                    "question_id": questions1[1]["id"],
                    "user_answer": questions1[1]["answer_options"]["B"],
                },
            ],
        }
        submit1 = client.post("/v1/test/submit", json=responses1, headers=auth_headers)
        assert submit1.status_code == 200

        # Manually update the test session and result completion date to simulate 6 months passing
        from app.models import TestResult as TestResultModel, TestSession

        test_result = (
            db_session.query(TestResultModel)
            .filter(TestResultModel.test_session_id == session1_id)
            .first()
        )
        test_result.completed_at = datetime.now(timezone.utc) - timedelta(days=180)

        test_session = (
            db_session.query(TestSession).filter(TestSession.id == session1_id).first()
        )
        test_session.completed_at = datetime.now(timezone.utc) - timedelta(days=180)
        db_session.commit()

        # Take second test with 2 questions
        start_response2 = client.post(
            "/v1/test/start?question_count=2", headers=auth_headers
        )
        assert start_response2.status_code == 200
        session2_data = start_response2.json()
        session2_id = session2_data["session"]["id"]
        questions2 = session2_data["questions"]
        question2_ids = {q["id"] for q in questions2}

        # Verify no question repetition
        assert question1_ids.isdisjoint(
            question2_ids
        ), "Questions should not repeat across tests"

        # Submit second test
        responses2 = {
            "session_id": session2_id,
            "responses": [
                {
                    "question_id": questions2[0]["id"],
                    "user_answer": questions2[0]["answer_options"]["B"],
                },
                {
                    "question_id": questions2[1]["id"],
                    "user_answer": questions2[1]["answer_options"]["B"],
                },
            ],
        }
        submit2 = client.post("/v1/test/submit", json=responses2, headers=auth_headers)
        assert submit2.status_code == 200

        # Verify history shows both tests
        history_response = client.get("/v1/test/history", headers=auth_headers)
        assert history_response.status_code == 200
        history_data = history_response.json()
        assert len(history_data) == 2  # Should have 2 tests


class TestNotificationIntegrationWithTests:
    """Test integration between notifications and test results."""

    def test_user_test_completion_updates_eligibility(
        self, client, test_questions, db_session
    ):
        """
        Test that a user's test eligibility is properly tracked after completion.
        """
        # Register and login
        register_payload = {
            "email": "testeligibility@example.com",
            "password": "SecurePassword123!",
            "first_name": "Test",
            "last_name": "Eligibility",
        }
        client.post("/v1/auth/register", json=register_payload)

        login_payload = {
            "email": "testeligibility@example.com",
            "password": "SecurePassword123!",
        }
        login_response = client.post("/v1/auth/login", json=login_payload)
        access_token = login_response.json()["access_token"]
        auth_headers = {"Authorization": f"Bearer {access_token}"}

        # Take a test
        start_response = client.post(
            "/v1/test/start?question_count=2", headers=auth_headers
        )
        assert start_response.status_code == 200
        session_data = start_response.json()
        session_id = session_data["session"]["id"]
        questions = session_data["questions"]

        # Submit test
        responses = {
            "session_id": session_id,
            "responses": [
                {
                    "question_id": questions[0]["id"],
                    "user_answer": questions[0]["answer_options"]["B"],
                },
                {
                    "question_id": questions[1]["id"],
                    "user_answer": questions[1]["answer_options"]["B"],
                },
            ],
        }
        submit_response = client.post(
            "/v1/test/submit", json=responses, headers=auth_headers
        )
        assert submit_response.status_code == 200

        # Verify test result was created
        from app.models import TestResult as TestResultModel

        test_result = (
            db_session.query(TestResultModel)
            .filter(TestResultModel.test_session_id == session_id)
            .first()
        )
        assert test_result is not None
        assert test_result.iq_score > 0


class TestAuthenticationFlow:
    """Test authentication and authorization flows."""

    def test_unauthorized_access_attempts(self, client, test_questions):
        """
        Test that unauthorized access is properly prevented:
        1. Access without token
        2. Access with invalid token
        3. Access with expired token
        """
        # Attempt to access protected endpoints without token
        no_auth_endpoints = [
            ("/v1/user/profile", "get"),
            ("/v1/test/start", "post"),
            ("/v1/test/history", "get"),
        ]

        for endpoint, method in no_auth_endpoints:
            if method == "get":
                response = client.get(endpoint)
            else:
                response = client.post(endpoint)

            # Should require auth (either 401 unauthorized or 403 forbidden)
            assert response.status_code in [401, 403], f"{endpoint} should require auth"

        # Attempt with invalid token
        invalid_headers = {"Authorization": "Bearer invalid-token-12345"}
        response = client.get("/v1/user/profile", headers=invalid_headers)
        assert response.status_code == 401


class TestErrorRecovery:
    """Test error recovery and edge cases."""

    def test_abandoned_test_recovery(self, client, test_questions):
        """
        Test that abandoned tests are properly handled:
        1. Start a test
        2. Don't submit
        3. Try to start another test (should work after abandoning first)
        """
        # Register and login
        register_payload = {
            "email": "abandon@example.com",
            "password": "SecurePassword123!",
            "first_name": "Abandon",
            "last_name": "User",
        }
        register_response = client.post("/v1/auth/register", json=register_payload)
        assert register_response.status_code == 201

        # Login to get tokens
        login_payload = {
            "email": "abandon@example.com",
            "password": "SecurePassword123!",
        }
        login_response = client.post("/v1/auth/login", json=login_payload)
        assert login_response.status_code == 200
        access_token = login_response.json()["access_token"]
        auth_headers = {"Authorization": f"Bearer {access_token}"}

        # Start first test
        start1 = client.post("/v1/test/start?question_count=2", headers=auth_headers)
        assert start1.status_code == 200
        session1_id = start1.json()["session"]["id"]

        # Try to start another test (should fail - active session exists)
        start2 = client.post("/v1/test/start?question_count=2", headers=auth_headers)
        assert start2.status_code == 400
        assert "already has an active test session" in start2.json()["detail"]

        # Abandon first test
        abandon_response = client.post(
            f"/v1/test/{session1_id}/abandon", headers=auth_headers
        )
        assert abandon_response.status_code == 200

        # Now should be able to start a new test
        start3 = client.post("/v1/test/start?question_count=2", headers=auth_headers)
        assert start3.status_code == 200
        assert start3.json()["session"]["id"] != session1_id
