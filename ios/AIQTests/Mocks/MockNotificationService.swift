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

    var mockRegisterResponse: DeviceTokenResponse?
    var mockUnregisterResponse: DeviceTokenResponse?
    var mockUpdatePreferencesResponse: NotificationPreferencesResponse?
    var mockGetPreferencesResponse: NotificationPreferencesResponse?

    var mockRegisterError: Error?
    var mockUnregisterError: Error?
    var mockUpdatePreferencesError: Error?
    var mockGetPreferencesError: Error?

    // MARK: - Initialization

    init() {}

    // MARK: - NotificationServiceProtocol Implementation

    func registerDeviceToken(_ deviceToken: String) async throws -> DeviceTokenResponse {
        registerDeviceTokenCalled = true
        lastRegisteredToken = deviceToken
        registerCallCount += 1

        if let error = mockRegisterError {
            throw error
        }

        guard let response = mockRegisterResponse else {
            throw NSError(
                domain: "MockNotificationService",
                code: -1,
                userInfo: [NSLocalizedDescriptionKey: "Mock register response not configured"]
            )
        }

        return response
    }

    func unregisterDeviceToken() async throws -> DeviceTokenResponse {
        unregisterDeviceTokenCalled = true
        unregisterCallCount += 1

        if let error = mockUnregisterError {
            throw error
        }

        guard let response = mockUnregisterResponse else {
            throw NSError(
                domain: "MockNotificationService",
                code: -1,
                userInfo: [NSLocalizedDescriptionKey: "Mock unregister response not configured"]
            )
        }

        return response
    }

    func updateNotificationPreferences(enabled: Bool) async throws -> NotificationPreferencesResponse {
        updateNotificationPreferencesCalled = true
        lastPreferencesEnabled = enabled
        updatePreferencesCallCount += 1

        if let error = mockUpdatePreferencesError {
            throw error
        }

        guard let response = mockUpdatePreferencesResponse else {
            throw NSError(
                domain: "MockNotificationService",
                code: -1,
                userInfo: [NSLocalizedDescriptionKey: "Mock update preferences response not configured"]
            )
        }

        return response
    }

    func getNotificationPreferences() async throws -> NotificationPreferencesResponse {
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

    /// Set mock register response
    func setRegisterResponse(_ response: DeviceTokenResponse) {
        mockRegisterResponse = response
    }

    /// Set mock unregister response
    func setUnregisterResponse(_ response: DeviceTokenResponse) {
        mockUnregisterResponse = response
    }

    /// Set mock update preferences response
    func setUpdatePreferencesResponse(_ response: NotificationPreferencesResponse) {
        mockUpdatePreferencesResponse = response
    }

    /// Set mock get preferences response
    func setGetPreferencesResponse(_ response: NotificationPreferencesResponse) {
        mockGetPreferencesResponse = response
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

    /// Reset all tracking state
    func reset() {
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

        mockRegisterResponse = nil
        mockUnregisterResponse = nil
        mockUpdatePreferencesResponse = nil
        mockGetPreferencesResponse = nil

        mockRegisterError = nil
        mockUnregisterError = nil
        mockUpdatePreferencesError = nil
        mockGetPreferencesError = nil
    }
}
