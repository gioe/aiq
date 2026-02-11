import Foundation

/// Protocol for onboarding storage
protocol OnboardingStorageProtocol: AnyObject {
    var hasCompletedOnboarding: Bool { get set }
    var didSkipOnboarding: Bool { get set }
}

/// UserDefaults-based implementation for storing onboarding state
class OnboardingStorage: OnboardingStorageProtocol {
    private let userDefaults: UserDefaults
    private let completedKey = "hasCompletedOnboarding"
    private let skippedKey = "didSkipOnboarding"

    init(userDefaults: UserDefaults = .standard) {
        self.userDefaults = userDefaults
    }

    var hasCompletedOnboarding: Bool {
        get { userDefaults.bool(forKey: completedKey) }
        set { userDefaults.set(newValue, forKey: completedKey) }
    }

    var didSkipOnboarding: Bool {
        get { userDefaults.bool(forKey: skippedKey) }
        set { userDefaults.set(newValue, forKey: skippedKey) }
    }
}
