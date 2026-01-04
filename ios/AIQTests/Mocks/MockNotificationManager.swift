@testable import AIQ
import Foundation
import UserNotifications

/// Mock implementation of NotificationManager for testing
@MainActor
class MockNotificationManager: ObservableObject {
    // MARK: - Published Properties

    @Published var authorizationStatus: UNAuthorizationStatus = .notDetermined
    @Published var isDeviceTokenRegistered: Bool = false

    // MARK: - Call Tracking

    var requestAuthorizationCalled = false
    var requestAuthorizationCallCount = 0
    var checkAuthorizationStatusCalled = false
    var didReceiveDeviceTokenCalled = false
    var lastDeviceToken: String?
    var didFailToRegisterCalled = false
    var lastRegistrationError: Error?
    var unregisterDeviceTokenCalled = false
    var retryDeviceTokenRegistrationCalled = false

    // MARK: - Mock Configuration

    var mockAuthorizationGranted: Bool = true
    var mockAuthorizationStatus: UNAuthorizationStatus = .authorized
    var shouldFailAuthorization: Bool = false

    // MARK: - Initialization

    init() {}

    // MARK: - Public Methods

    func requestAuthorization() async -> Bool {
        requestAuthorizationCalled = true
        requestAuthorizationCallCount += 1

        if shouldFailAuthorization {
            return false
        }

        authorizationStatus = mockAuthorizationGranted ? .authorized : .denied
        return mockAuthorizationGranted
    }

    func checkAuthorizationStatus() async {
        checkAuthorizationStatusCalled = true
        authorizationStatus = mockAuthorizationStatus
    }

    func didReceiveDeviceToken(_ deviceToken: Data) {
        didReceiveDeviceTokenCalled = true
        let tokenString = deviceToken.map { String(format: "%02.2hhx", $0) }.joined()
        lastDeviceToken = tokenString
    }

    func didFailToRegisterForRemoteNotifications(error: Error) {
        didFailToRegisterCalled = true
        lastRegistrationError = error
        isDeviceTokenRegistered = false
    }

    func unregisterDeviceToken() async {
        unregisterDeviceTokenCalled = true
        isDeviceTokenRegistered = false
    }

    func retryDeviceTokenRegistration() async {
        retryDeviceTokenRegistrationCalled = true
    }

    // MARK: - Helper Methods

    func setAuthorizationStatus(_ status: UNAuthorizationStatus) {
        authorizationStatus = status
        mockAuthorizationStatus = status
    }

    func setDeviceTokenRegistered(_ registered: Bool) {
        isDeviceTokenRegistered = registered
    }

    func reset() {
        requestAuthorizationCalled = false
        requestAuthorizationCallCount = 0
        checkAuthorizationStatusCalled = false
        didReceiveDeviceTokenCalled = false
        lastDeviceToken = nil
        didFailToRegisterCalled = false
        lastRegistrationError = nil
        unregisterDeviceTokenCalled = false
        retryDeviceTokenRegistrationCalled = false

        authorizationStatus = .notDetermined
        isDeviceTokenRegistered = false
        mockAuthorizationGranted = true
        mockAuthorizationStatus = .authorized
        shouldFailAuthorization = false
    }
}
