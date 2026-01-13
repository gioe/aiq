@testable import AIQ
import Foundation
import UserNotifications

/// Mock implementation of UserNotificationCenterProtocol for testing
/// This prevents the real OS permission dialog from appearing during tests
@MainActor
final class MockUserNotificationCenter: UserNotificationCenterProtocol {
    // MARK: - Configuration

    /// Whether requestAuthorization should return granted
    var authorizationGranted: Bool = false

    /// Error to throw from requestAuthorization (if any)
    var authorizationError: Error?

    /// Authorization status to return from getAuthorizationStatus
    var authorizationStatus: UNAuthorizationStatus = .notDetermined

    /// Error to throw from add (if any)
    var addNotificationError: Error?

    // MARK: - Call Tracking

    /// Whether requestAuthorization was called
    var requestAuthorizationCalled = false

    /// Number of times requestAuthorization was called
    var requestAuthorizationCallCount = 0

    /// Options passed to last requestAuthorization call
    var lastAuthorizationOptions: UNAuthorizationOptions?

    /// Whether getAuthorizationStatus was called
    var getAuthorizationStatusCalled = false

    /// Number of times getAuthorizationStatus was called
    var getAuthorizationStatusCallCount = 0

    /// Whether add was called
    var addNotificationCalled = false

    /// Number of times add was called
    var addNotificationCallCount = 0

    /// Requests added via add method
    var addedRequests: [UNNotificationRequest] = []

    // MARK: - UserNotificationCenterProtocol Implementation

    func requestAuthorization(options: UNAuthorizationOptions) async throws -> Bool {
        requestAuthorizationCalled = true
        requestAuthorizationCallCount += 1
        lastAuthorizationOptions = options

        if let error = authorizationError {
            throw error
        }

        return authorizationGranted
    }

    func getAuthorizationStatus() async -> UNAuthorizationStatus {
        getAuthorizationStatusCalled = true
        getAuthorizationStatusCallCount += 1
        return authorizationStatus
    }

    func add(_ request: UNNotificationRequest) async throws {
        addNotificationCalled = true
        addNotificationCallCount += 1
        addedRequests.append(request)

        if let error = addNotificationError {
            throw error
        }
    }

    // MARK: - Helper Methods

    /// Reset all tracking state
    func reset() {
        authorizationGranted = false
        authorizationError = nil
        authorizationStatus = .notDetermined
        addNotificationError = nil
        requestAuthorizationCalled = false
        requestAuthorizationCallCount = 0
        lastAuthorizationOptions = nil
        getAuthorizationStatusCalled = false
        getAuthorizationStatusCallCount = 0
        addNotificationCalled = false
        addNotificationCallCount = 0
        addedRequests = []
    }
}
