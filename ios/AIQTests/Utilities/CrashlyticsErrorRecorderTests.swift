import XCTest

@testable import AIQ

final class CrashlyticsErrorRecorderTests: XCTestCase {
    // MARK: - ErrorContext Tests

    func testErrorContextRawValues_Authentication() {
        XCTAssertEqual(
            CrashlyticsErrorRecorder.ErrorContext.login.rawValue,
            "auth_login"
        )
        XCTAssertEqual(
            CrashlyticsErrorRecorder.ErrorContext.logout.rawValue,
            "auth_logout"
        )
        XCTAssertEqual(
            CrashlyticsErrorRecorder.ErrorContext.registration.rawValue,
            "auth_registration"
        )
        XCTAssertEqual(
            CrashlyticsErrorRecorder.ErrorContext.tokenRefresh.rawValue,
            "auth_token_refresh"
        )
    }

    func testErrorContextRawValues_TestOperations() {
        XCTAssertEqual(
            CrashlyticsErrorRecorder.ErrorContext.startTest.rawValue,
            "test_start"
        )
        XCTAssertEqual(
            CrashlyticsErrorRecorder.ErrorContext.submitTest.rawValue,
            "test_submit"
        )
        XCTAssertEqual(
            CrashlyticsErrorRecorder.ErrorContext.abandonTest.rawValue,
            "test_abandon"
        )
        XCTAssertEqual(
            CrashlyticsErrorRecorder.ErrorContext.resumeTest.rawValue,
            "test_resume"
        )
        XCTAssertEqual(
            CrashlyticsErrorRecorder.ErrorContext.fetchQuestions.rawValue,
            "test_fetch_questions"
        )
    }

    func testErrorContextRawValues_DashboardAndHistory() {
        XCTAssertEqual(
            CrashlyticsErrorRecorder.ErrorContext.fetchDashboard.rawValue,
            "dashboard_fetch"
        )
        XCTAssertEqual(
            CrashlyticsErrorRecorder.ErrorContext.fetchHistory.rawValue,
            "history_fetch"
        )
        XCTAssertEqual(
            CrashlyticsErrorRecorder.ErrorContext.fetchActiveSession.rawValue,
            "dashboard_active_session"
        )
    }

    func testErrorContextRawValues_Notifications() {
        XCTAssertEqual(
            CrashlyticsErrorRecorder.ErrorContext.notificationPreferences.rawValue,
            "notification_preferences"
        )
        XCTAssertEqual(
            CrashlyticsErrorRecorder.ErrorContext.notificationPermission.rawValue,
            "notification_permission"
        )
    }

    func testErrorContextRawValues_Storage() {
        XCTAssertEqual(
            CrashlyticsErrorRecorder.ErrorContext.localSave.rawValue,
            "storage_local_save"
        )
        XCTAssertEqual(
            CrashlyticsErrorRecorder.ErrorContext.localLoad.rawValue,
            "storage_local_load"
        )
    }

    func testErrorContextRawValues_Analytics() {
        XCTAssertEqual(
            CrashlyticsErrorRecorder.ErrorContext.analytics.rawValue,
            "analytics_event"
        )
    }

    func testErrorContextRawValues_Navigation() {
        XCTAssertEqual(
            CrashlyticsErrorRecorder.ErrorContext.deepLinkParse.rawValue,
            "navigation_deeplink_parse"
        )
        XCTAssertEqual(
            CrashlyticsErrorRecorder.ErrorContext.deepLinkNavigation.rawValue,
            "navigation_deeplink_navigation"
        )
    }

    func testErrorContextRawValues_Generic() {
        XCTAssertEqual(
            CrashlyticsErrorRecorder.ErrorContext.unknown.rawValue,
            "unknown"
        )
    }

    // MARK: - Error Categorization Tests

    func testErrorContextCategorization_AllAuthContexts() {
        let authContexts: [CrashlyticsErrorRecorder.ErrorContext] = [
            .login,
            .logout,
            .registration,
            .tokenRefresh
        ]

        for context in authContexts {
            XCTAssertTrue(
                context.rawValue.hasPrefix("auth_"),
                "Auth context '\(context.rawValue)' should have 'auth_' prefix"
            )
        }
    }

    func testErrorContextCategorization_AllTestContexts() {
        let testContexts: [CrashlyticsErrorRecorder.ErrorContext] = [
            .startTest,
            .submitTest,
            .abandonTest,
            .resumeTest,
            .fetchQuestions
        ]

        for context in testContexts {
            XCTAssertTrue(
                context.rawValue.hasPrefix("test_"),
                "Test context '\(context.rawValue)' should have 'test_' prefix"
            )
        }
    }

    func testErrorContextCategorization_AllDashboardContexts() {
        let dashboardContexts: [CrashlyticsErrorRecorder.ErrorContext] = [
            .fetchDashboard,
            .fetchHistory,
            .fetchActiveSession
        ]

        for context in dashboardContexts {
            XCTAssertTrue(
                context.rawValue.contains("dashboard") || context.rawValue.contains("history"),
                "Dashboard/History context '\(context.rawValue)' should contain 'dashboard' or 'history'"
            )
        }
    }

    func testErrorContextCategorization_AllNotificationContexts() {
        let notificationContexts: [CrashlyticsErrorRecorder.ErrorContext] = [
            .notificationPreferences,
            .notificationPermission
        ]

        for context in notificationContexts {
            XCTAssertTrue(
                context.rawValue.hasPrefix("notification_"),
                "Notification context '\(context.rawValue)' should have 'notification_' prefix"
            )
        }
    }

    func testErrorContextCategorization_AllStorageContexts() {
        let storageContexts: [CrashlyticsErrorRecorder.ErrorContext] = [
            .localSave,
            .localLoad
        ]

        for context in storageContexts {
            XCTAssertTrue(
                context.rawValue.hasPrefix("storage_"),
                "Storage context '\(context.rawValue)' should have 'storage_' prefix"
            )
        }
    }

    func testErrorContextCategorization_AllNavigationContexts() {
        let navigationContexts: [CrashlyticsErrorRecorder.ErrorContext] = [
            .deepLinkParse,
            .deepLinkNavigation
        ]

        for context in navigationContexts {
            XCTAssertTrue(
                context.rawValue.hasPrefix("navigation_"),
                "Navigation context '\(context.rawValue)' should have 'navigation_' prefix"
            )
        }
    }

    // MARK: - recordError Method Tests - APIError Detection

    func testRecordError_WithAPIError_Unauthorized() {
        let error = APIError.unauthorized(message: "Token expired")

        // Should not crash in DEBUG mode
        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .login
            )
        )
    }

    func testRecordError_WithAPIError_ServerError() {
        let error = APIError.serverError(statusCode: 500, message: "Internal server error")

        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .fetchDashboard
            )
        )
    }

    func testRecordError_WithAPIError_NetworkError() {
        let urlError = URLError(.notConnectedToInternet)
        let error = APIError.networkError(urlError)

        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .submitTest
            )
        )
    }

    func testRecordError_WithAPIError_Timeout() {
        let error = APIError.timeout

        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .fetchQuestions
            )
        )
    }

    func testRecordError_WithAPIError_BadRequest() {
        let error = APIError.badRequest(message: "Invalid request")

        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .registration
            )
        )
    }

    func testRecordError_WithAPIError_NotFound() {
        let error = APIError.notFound(message: "Resource not found")

        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .fetchHistory
            )
        )
    }

    func testRecordError_WithAPIError_ActiveSessionConflict() {
        let error = APIError.activeSessionConflict(
            sessionId: 123,
            message: "User already has an active test session (ID: 123)"
        )

        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .startTest
            )
        )
    }

    func testRecordError_WithAPIError_DecodingError() {
        let decodingError = DecodingError.dataCorrupted(
            DecodingError.Context(
                codingPath: [],
                debugDescription: "Invalid JSON"
            )
        )
        let error = APIError.decodingError(decodingError)

        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .fetchDashboard
            )
        )
    }

    func testRecordError_WithAPIError_InvalidURL() {
        let error = APIError.invalidURL

        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .fetchQuestions
            )
        )
    }

    func testRecordError_WithAPIError_InvalidResponse() {
        let error = APIError.invalidResponse

        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .submitTest
            )
        )
    }

    func testRecordError_WithAPIError_Forbidden() {
        let error = APIError.forbidden(message: "Access denied")

        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .fetchActiveSession
            )
        )
    }

    func testRecordError_WithAPIError_NoInternetConnection() {
        let error = APIError.noInternetConnection

        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .login
            )
        )
    }

    func testRecordError_WithAPIError_Unknown() {
        let error = APIError.unknown(message: "Unknown error occurred")

        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .unknown
            )
        )
    }

    func testRecordError_WithAPIError_UnprocessableEntity() {
        let error = APIError.unprocessableEntity(message: "Invalid data")

        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .registration
            )
        )
    }

    // MARK: - recordError Method Tests - ContextualError Detection

    func testRecordError_WithContextualError_Login() {
        let apiError = APIError.unauthorized(message: "Invalid credentials")
        let error = ContextualError(error: apiError, operation: .login)

        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .login
            )
        )
    }

    func testRecordError_WithContextualError_Register() {
        let apiError = APIError.badRequest(message: "Email already exists")
        let error = ContextualError(error: apiError, operation: .register)

        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .registration
            )
        )
    }

    func testRecordError_WithContextualError_FetchQuestions() {
        let apiError = APIError.networkError(URLError(.timedOut))
        let error = ContextualError(error: apiError, operation: .fetchQuestions)

        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .fetchQuestions
            )
        )
    }

    func testRecordError_WithContextualError_SubmitTest() {
        let apiError = APIError.serverError(statusCode: 503, message: "Service unavailable")
        let error = ContextualError(error: apiError, operation: .submitTest)

        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .submitTest
            )
        )
    }

    func testRecordError_WithContextualError_RefreshToken() {
        let apiError = APIError.unauthorized(message: "Refresh token expired")
        let error = ContextualError(error: apiError, operation: .refreshToken)

        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .tokenRefresh
            )
        )
    }

    func testRecordError_WithContextualError_FetchProfile() {
        let apiError = APIError.notFound(message: "Profile not found")
        let error = ContextualError(error: apiError, operation: .fetchProfile)

        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .fetchDashboard
            )
        )
    }

    func testRecordError_WithContextualError_UpdateProfile() {
        let apiError = APIError.unprocessableEntity(message: "Invalid profile data")
        let error = ContextualError(error: apiError, operation: .updateProfile)

        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .fetchDashboard
            )
        )
    }

    func testRecordError_WithContextualError_FetchHistory() {
        let apiError = APIError.forbidden(message: "Access denied")
        let error = ContextualError(error: apiError, operation: .fetchHistory)

        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .fetchHistory
            )
        )
    }

    func testRecordError_WithContextualError_Logout() {
        let apiError = APIError.networkError(URLError(.notConnectedToInternet))
        let error = ContextualError(error: apiError, operation: .logout)

        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .logout
            )
        )
    }

    func testRecordError_WithContextualError_DeleteAccount() {
        let apiError = APIError.unauthorized(message: "Session expired")
        let error = ContextualError(error: apiError, operation: .deleteAccount)

        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .unknown
            )
        )
    }

    func testRecordError_WithContextualError_Generic() {
        let apiError = APIError.unknown(message: "Unknown error")
        let error = ContextualError(error: apiError, operation: .generic)

        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .unknown
            )
        )
    }

    // MARK: - recordError Method Tests - Generic Error Types

    func testRecordError_WithGenericNSError() {
        let error = NSError(
            domain: "com.aiq.test",
            code: 1001,
            userInfo: [NSLocalizedDescriptionKey: "Test error"]
        )

        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .unknown
            )
        )
    }

    func testRecordError_WithURLError() {
        let error = URLError(.cannotConnectToHost)

        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .fetchDashboard
            )
        )
    }

    func testRecordError_WithCustomError() {
        struct CustomError: Error {
            let message: String
        }

        let error = CustomError(message: "Custom error occurred")

        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .analytics
            )
        )
    }

    // MARK: - recordError Method Tests - AdditionalInfo

    func testRecordError_WithAdditionalInfo_SingleValue() {
        let error = APIError.networkError(URLError(.timedOut))
        let additionalInfo = ["retry_count": 3]

        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .fetchQuestions,
                additionalInfo: additionalInfo
            )
        )
    }

    func testRecordError_WithAdditionalInfo_MultipleValues() {
        let error = APIError.serverError(statusCode: 500)
        let additionalInfo: [String: Any] = [
            "endpoint": "/api/test/submit",
            "retry_count": 2,
            "user_id": "12345",
            "timestamp": Date().timeIntervalSince1970
        ]

        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .submitTest,
                additionalInfo: additionalInfo
            )
        )
    }

    func testRecordError_WithAdditionalInfo_EmptyDictionary() {
        let error = APIError.unauthorized()
        let additionalInfo: [String: Any] = [:]

        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .login,
                additionalInfo: additionalInfo
            )
        )
    }

    func testRecordError_WithoutAdditionalInfo() {
        let error = APIError.notFound()

        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .fetchHistory
            )
        )
    }

    // MARK: - recordError Method Tests - Error Context Combinations

    func testRecordError_AllContexts_WithAPIError() {
        let allContexts: [CrashlyticsErrorRecorder.ErrorContext] = [
            .login, .logout, .registration, .tokenRefresh,
            .startTest, .submitTest, .abandonTest, .resumeTest, .fetchQuestions,
            .fetchDashboard, .fetchHistory, .fetchActiveSession,
            .notificationPreferences, .notificationPermission,
            .localSave, .localLoad,
            .analytics,
            .deepLinkParse, .deepLinkNavigation,
            .unknown
        ]

        let error = APIError.networkError(URLError(.networkConnectionLost))

        for context in allContexts {
            XCTAssertNoThrow(
                CrashlyticsErrorRecorder.recordError(error, context: context),
                "Should not throw for context: \(context.rawValue)"
            )
        }
    }

    func testRecordError_AllContexts_WithContextualError() {
        let allContexts: [CrashlyticsErrorRecorder.ErrorContext] = [
            .login, .logout, .registration, .tokenRefresh,
            .startTest, .submitTest, .abandonTest, .resumeTest, .fetchQuestions,
            .fetchDashboard, .fetchHistory, .fetchActiveSession,
            .notificationPreferences, .notificationPermission,
            .localSave, .localLoad,
            .analytics,
            .deepLinkParse, .deepLinkNavigation,
            .unknown
        ]

        let apiError = APIError.timeout
        let error = ContextualError(error: apiError, operation: .generic)

        for context in allContexts {
            XCTAssertNoThrow(
                CrashlyticsErrorRecorder.recordError(error, context: context),
                "Should not throw for context: \(context.rawValue)"
            )
        }
    }

    // MARK: - recordError Method Tests - Retryable Error Behavior

    func testRecordError_WithRetryableAPIErrors() {
        let retryableErrors: [APIError] = [
            .networkError(URLError(.timedOut)),
            .timeout,
            .noInternetConnection,
            .serverError(statusCode: 503)
        ]

        for error in retryableErrors {
            XCTAssertTrue(
                error.isRetryable,
                "Error should be retryable: \(error)"
            )

            XCTAssertNoThrow(
                CrashlyticsErrorRecorder.recordError(
                    error,
                    context: .fetchDashboard
                )
            )
        }
    }

    func testRecordError_WithNonRetryableAPIErrors() {
        let nonRetryableErrors: [APIError] = [
            .badRequest(message: "Bad request"),
            .unauthorized(message: "Unauthorized"),
            .forbidden(message: "Forbidden"),
            .invalidURL,
            .invalidResponse,
            .notFound(message: "Not found"),
            .activeSessionConflict(sessionId: 1, message: "Conflict"),
            .decodingError(DecodingError.dataCorrupted(
                DecodingError.Context(codingPath: [], debugDescription: "Corrupt")
            )),
            .unknown(message: "Unknown")
        ]

        for error in nonRetryableErrors {
            XCTAssertFalse(
                error.isRetryable,
                "Error should not be retryable: \(error)"
            )

            XCTAssertNoThrow(
                CrashlyticsErrorRecorder.recordError(
                    error,
                    context: .fetchDashboard
                )
            )
        }
    }

    func testRecordError_WithRetryableContextualError() {
        let retryableAPIError = APIError.networkError(URLError(.networkConnectionLost))
        let error = ContextualError(error: retryableAPIError, operation: .fetchQuestions)

        XCTAssertTrue(error.isRetryable)

        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .fetchQuestions
            )
        )
    }

    func testRecordError_WithNonRetryableContextualError() {
        let nonRetryableAPIError = APIError.unauthorized(message: "Unauthorized")
        let error = ContextualError(error: nonRetryableAPIError, operation: .login)

        XCTAssertFalse(error.isRetryable)

        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .login
            )
        )
    }

    // MARK: - setUserId Method Tests

    func testSetUserId_WithValidUserId() {
        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.setUserId("user123")
        )
    }

    func testSetUserId_WithEmptyString() {
        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.setUserId("")
        )
    }

    func testSetUserId_WithNil() {
        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.setUserId(nil)
        )
    }

    func testSetUserId_WithNumericId() {
        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.setUserId("12345")
        )
    }

    func testSetUserId_WithUUID() {
        let uuid = UUID().uuidString
        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.setUserId(uuid)
        )
    }

    func testSetUserId_WithSpecialCharacters() {
        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.setUserId("user@example.com")
        )
    }

    // MARK: - log(key:value:) Method Tests

    func testLog_WithValidKeyValue() {
        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.log(key: "test_key", value: "test_value")
        )
    }

    func testLog_WithEmptyKey() {
        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.log(key: "", value: "value")
        )
    }

    func testLog_WithEmptyValue() {
        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.log(key: "key", value: "")
        )
    }

    func testLog_WithNumericValue() {
        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.log(key: "count", value: "42")
        )
    }

    func testLog_WithBooleanValue() {
        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.log(key: "is_enabled", value: "true")
        )
    }

    func testLog_WithJSONValue() {
        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.log(
                key: "user_data",
                value: "{\"id\": 123, \"name\": \"Test\"}"
            )
        )
    }

    func testLog_WithMultipleInvocations() {
        XCTAssertNoThrow {
            CrashlyticsErrorRecorder.log(key: "key1", value: "value1")
            CrashlyticsErrorRecorder.log(key: "key2", value: "value2")
            CrashlyticsErrorRecorder.log(key: "key3", value: "value3")
        }
    }

    func testLog_WithSpecialCharacters() {
        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.log(
                key: "special_chars",
                value: "!@#$%^&*()_+-=[]{}|;':\",./<>?"
            )
        )
    }

    // MARK: - logBreadcrumb Method Tests

    func testLogBreadcrumb_WithValidMessage() {
        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.logBreadcrumb("User tapped login button")
        )
    }

    func testLogBreadcrumb_WithEmptyMessage() {
        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.logBreadcrumb("")
        )
    }

    func testLogBreadcrumb_WithLongMessage() {
        let longMessage = String(repeating: "a", count: 1000)
        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.logBreadcrumb(longMessage)
        )
    }

    func testLogBreadcrumb_WithMultilineMessage() {
        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.logBreadcrumb(
                """
                User navigation flow:
                1. Opened app
                2. Viewed dashboard
                3. Started test
                """
            )
        )
    }

    func testLogBreadcrumb_WithUnicodeCharacters() {
        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.logBreadcrumb("用户登录成功")
        )
    }

    func testLogBreadcrumb_WithSpecialCharacters() {
        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.logBreadcrumb(
                "User email: test@example.com, action: login"
            )
        )
    }

    func testLogBreadcrumb_WithJSONFormat() {
        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.logBreadcrumb(
                "{\"event\": \"button_tap\", \"button_id\": \"login\"}"
            )
        )
    }

    func testLogBreadcrumb_MultipleConsecutiveCalls() {
        XCTAssertNoThrow {
            CrashlyticsErrorRecorder.logBreadcrumb("Step 1: User opened app")
            CrashlyticsErrorRecorder.logBreadcrumb("Step 2: User viewed dashboard")
            CrashlyticsErrorRecorder.logBreadcrumb("Step 3: User started test")
            CrashlyticsErrorRecorder.logBreadcrumb("Step 4: User submitted test")
        }
    }

    // MARK: - Integration Tests - Combined Operations

    func testIntegration_TypicalErrorReportingFlow() {
        // Simulate a typical error reporting flow
        XCTAssertNoThrow {
            CrashlyticsErrorRecorder.setUserId("user123")
            CrashlyticsErrorRecorder.log(key: "screen", value: "login")
            CrashlyticsErrorRecorder.logBreadcrumb("User entered credentials")
            CrashlyticsErrorRecorder.logBreadcrumb("User tapped login button")

            let error = APIError.unauthorized(message: "Invalid credentials")
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .login,
                additionalInfo: ["attempt_count": 1]
            )
        }
    }

    func testIntegration_TestSubmissionFlow() {
        XCTAssertNoThrow {
            CrashlyticsErrorRecorder.setUserId("user456")
            CrashlyticsErrorRecorder.log(key: "test_session_id", value: "789")
            CrashlyticsErrorRecorder.logBreadcrumb("User started test")
            CrashlyticsErrorRecorder.logBreadcrumb("User answered 10 questions")
            CrashlyticsErrorRecorder.logBreadcrumb("User attempted to submit test")

            let error = APIError.networkError(URLError(.timedOut))
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .submitTest,
                additionalInfo: [
                    "question_count": 10,
                    "elapsed_time": 300
                ]
            )
        }
    }

    func testIntegration_DashboardLoadFlow() {
        XCTAssertNoThrow {
            CrashlyticsErrorRecorder.logBreadcrumb("User navigated to dashboard")
            CrashlyticsErrorRecorder.log(key: "previous_screen", value: "onboarding")

            let apiError = APIError.serverError(statusCode: 503, message: "Service unavailable")
            let contextualError = ContextualError(error: apiError, operation: .fetchProfile)

            CrashlyticsErrorRecorder.recordError(
                contextualError,
                context: .fetchDashboard,
                additionalInfo: ["retry_count": 2]
            )
        }
    }

    // MARK: - Edge Cases and Stress Tests

    func testEdgeCase_RapidConsecutiveErrorRecording() {
        let errors: [Error] = [
            APIError.networkError(URLError(.timedOut)),
            APIError.unauthorized(message: "Session expired"),
            APIError.serverError(statusCode: 500),
            APIError.notFound(message: "Not found")
        ]

        XCTAssertNoThrow {
            for error in errors {
                CrashlyticsErrorRecorder.recordError(error, context: .unknown)
            }
        }
    }

    func testEdgeCase_LargeAdditionalInfoDictionary() {
        var largeInfo: [String: Any] = [:]
        for i in 0 ..< 100 {
            largeInfo["key_\(i)"] = "value_\(i)"
        }

        let error = APIError.unknown(message: "Test error")

        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .unknown,
                additionalInfo: largeInfo
            )
        )
    }

    func testEdgeCase_AdditionalInfoWithComplexTypes() {
        let additionalInfo: [String: Any] = [
            "string": "test",
            "int": 42,
            "double": 3.14,
            "bool": true,
            "date": Date(),
            "array": [1, 2, 3],
            "dict": ["nested": "value"]
        ]

        let error = APIError.unknown(message: "Test")

        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .unknown,
                additionalInfo: additionalInfo
            )
        )
    }

    func testEdgeCase_VeryLongErrorMessage() {
        let longMessage = String(repeating: "a", count: 10000)
        let error = APIError.badRequest(message: longMessage)

        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .unknown
            )
        )
    }

    func testEdgeCase_ConcurrentErrorRecording() {
        let expectation = expectation(description: "Concurrent error recording")
        expectation.expectedFulfillmentCount = 10

        for i in 0 ..< 10 {
            DispatchQueue.global().async {
                let error = APIError.serverError(statusCode: 500, message: "Error \(i)")
                CrashlyticsErrorRecorder.recordError(error, context: .unknown)
                expectation.fulfill()
            }
        }

        waitForExpectations(timeout: 5.0)
    }

    // MARK: - AdditionalInfo Merging Logic Tests

    func testAdditionalInfoMerging_NewValueOverridesExisting() {
        // In DEBUG mode, we can't directly test the merge behavior in Crashlytics,
        // but we can verify the method doesn't crash with conflicting keys
        let additionalInfo: [String: Any] = [
            "context": "custom_context", // Should override the default "context" key
            "errorType": "CustomErrorType", // Should override the default "errorType" key
            "custom_key": "custom_value"
        ]

        let error = APIError.unknown(message: "Test")

        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .unknown,
                additionalInfo: additionalInfo
            )
        )
    }

    func testAdditionalInfoMerging_WithAPIErrorSpecificKeys() {
        // Test that additionalInfo can override API error-specific keys
        let additionalInfo: [String: Any] = [
            "isRetryable": false, // Override the APIError.isRetryable value
            "custom_field": "value"
        ]

        let error = APIError.networkError(URLError(.timedOut)) // isRetryable = true

        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .fetchQuestions,
                additionalInfo: additionalInfo
            )
        )
    }

    func testAdditionalInfoMerging_WithContextualErrorSpecificKeys() {
        // Test that additionalInfo can override ContextualError-specific keys
        let additionalInfo: [String: Any] = [
            "operation": "custom_operation", // Override the operation key
            "isRetryable": true
        ]

        let apiError = APIError.unauthorized(message: "Unauthorized")
        let error = ContextualError(error: apiError, operation: .login)

        XCTAssertNoThrow(
            CrashlyticsErrorRecorder.recordError(
                error,
                context: .login,
                additionalInfo: additionalInfo
            )
        )
    }
}
