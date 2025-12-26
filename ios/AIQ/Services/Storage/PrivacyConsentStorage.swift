import Foundation

/// Protocol for privacy consent storage
protocol PrivacyConsentStorageProtocol {
    func hasAcceptedConsent() -> Bool
    func getConsentTimestamp() -> Date?
    func saveConsent()
    func clearConsent()
}

/// UserDefaults-based implementation for storing privacy consent
class PrivacyConsentStorage: PrivacyConsentStorageProtocol {
    static let shared = PrivacyConsentStorage()

    private let userDefaults: UserDefaults
    private let consentKey = "com.aiq.privacyConsentAccepted"
    private let timestampKey = "com.aiq.privacyConsentTimestamp"

    init(userDefaults: UserDefaults = .standard) {
        self.userDefaults = userDefaults
    }

    func hasAcceptedConsent() -> Bool {
        userDefaults.bool(forKey: consentKey)
    }

    func getConsentTimestamp() -> Date? {
        guard let timestamp = userDefaults.object(forKey: timestampKey) as? Date else {
            return nil
        }
        return timestamp
    }

    func saveConsent() {
        userDefaults.set(true, forKey: consentKey)
        userDefaults.set(Date(), forKey: timestampKey)
    }

    func clearConsent() {
        userDefaults.removeObject(forKey: consentKey)
        userDefaults.removeObject(forKey: timestampKey)
    }
}
