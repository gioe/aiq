@testable import AIQ
import Foundation

/// Mock implementation of NotificationServiceProtocol for testing
/// Thread-safe via actor isolation
actor MockNotificationService: NotificationServiceProtocol {
    // MARK: - Call Tracking Properties

    var registerDeviceTokenCalled = false
    var lastRegisteredToken: String?
    var registerCallCount = 0

    var unregisterDeviceTokenCalled = false
    var unregisterCallCount = 0

    var updateNotificationPreferencesCalled = false
    var lastPreferencesEnabled: Bool?
    var updatePreferencesCallCount = 0

    var getNotificationPreferencesCalled = false
    var getPreferencesCallCount = 0

    // MARK: - Mock Response Configuration

    var mockGetPreferencesResponse: Bool?

    var mockRegisterError: Error?
    var mockUnregisterError: Error?
    var mockUpdatePreferencesError: Error?
    var mockGetPreferencesError: Error?

    // MARK: - Delay Configuration

    /// Configurable delay for register operations (in seconds)
    /// Used to simulate slow network for concurrency testing
    var registerDelay: TimeInterval = 0

    // MARK: - Initialization

    init() {}

    // MARK: - NotificationServiceProtocol Implementation

    func registerDeviceToken(_ deviceToken: String) async throws {
        registerDeviceTokenCalled = true
        lastRegisteredToken = deviceToken
        registerCallCount += 1

        // Simulate network delay if configured
        if registerDelay > 0 {
            try await Task.sleep(nanoseconds: UInt64(registerDelay * 1_000_000_000))
        }

        if let error = mockRegisterError {
            throw error
        }
    }

    func unregisterDeviceToken() async throws {
        unregisterDeviceTokenCalled = true
        unregisterCallCount += 1

        if let error = mockUnregisterError {
            throw error
        }
    }

    func updateNotificationPreferences(enabled: Bool) async throws {
        updateNotificationPreferencesCalled = true
        lastPreferencesEnabled = enabled
        updatePreferencesCallCount += 1

        if let error = mockUpdatePreferencesError {
            throw error
        }
    }

    func getNotificationPreferences() async throws -> Bool {
        getNotificationPreferencesCalled = true
        getPreferencesCallCount += 1

        if let error = mockGetPreferencesError {
            throw error
        }

        guard let response = mockGetPreferencesResponse else {
            throw NSError(
                domain: "MockNotificationService",
                code: -1,
                userInfo: [NSLocalizedDescriptionKey: "Mock get preferences response not configured"]
            )
        }

        return response
    }

    // MARK: - Helper Methods

    /// Set mock get preferences response
    func setGetPreferencesResponse(_ enabled: Bool) {
        mockGetPreferencesResponse = enabled
    }

    /// Set mock register error
    func setRegisterError(_ error: Error?) {
        mockRegisterError = error
    }

    /// Set mock unregister error
    func setUnregisterError(_ error: Error?) {
        mockUnregisterError = error
    }

    /// Set mock update preferences error
    func setUpdatePreferencesError(_ error: Error?) {
        mockUpdatePreferencesError = error
    }

    /// Set mock get preferences error
    func setGetPreferencesError(_ error: Error?) {
        mockGetPreferencesError = error
    }

    /// Set register delay (for concurrency testing)
    func setRegisterDelay(_ delay: TimeInterval) {
        registerDelay = delay
    }

    /// Reset all tracking state
    func reset() {
        registerDelay = 0
        registerDeviceTokenCalled = false
        lastRegisteredToken = nil
        registerCallCount = 0

        unregisterDeviceTokenCalled = false
        unregisterCallCount = 0

        updateNotificationPreferencesCalled = false
        lastPreferencesEnabled = nil
        updatePreferencesCallCount = 0

        getNotificationPreferencesCalled = false
        getPreferencesCallCount = 0

        mockGetPreferencesResponse = nil

        mockRegisterError = nil
        mockUnregisterError = nil
        mockUpdatePreferencesError = nil
        mockGetPreferencesError = nil
    }

    /// Reset only call counts without affecting mock responses
    func resetCallCounts() {
        registerDeviceTokenCalled = false
        lastRegisteredToken = nil
        registerCallCount = 0

        unregisterDeviceTokenCalled = false
        unregisterCallCount = 0

        updateNotificationPreferencesCalled = false
        lastPreferencesEnabled = nil
        updatePreferencesCallCount = 0

        getNotificationPreferencesCalled = false
        getPreferencesCallCount = 0
    }
}
