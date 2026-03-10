import Combine
import Foundation

/// ViewModel for managing onboarding flow state
/// Does NOT inherit from BaseViewModel as this is simple navigation state with no API calls
@MainActor
class OnboardingViewModel: ObservableObject {
    // MARK: - Published Properties

    /// Current page index (0-3)
    @Published var currentPage: Int = 0

    /// Whether onboarding has been completed
    @Published var hasCompletedOnboarding: Bool = false

    /// Whether the user skipped onboarding (used to show info card on dashboard)
    @Published var didSkipOnboarding: Bool = false

    // MARK: - Private Properties

    private let storage: OnboardingStorageProtocol

    // MARK: - Constants

    /// Total number of onboarding pages
    private let totalPages = Constants.Onboarding.totalPages

    // MARK: - Initialization

    init(storage: OnboardingStorageProtocol = OnboardingStorage()) {
        self.storage = storage
        hasCompletedOnboarding = storage.hasCompletedOnboarding
        didSkipOnboarding = storage.didSkipOnboarding
    }

    // MARK: - Public Methods

    /// Navigate to the next page
    func nextPage() {
        guard currentPage < totalPages - 1 else { return }
        currentPage += 1
    }

    /// Skip the onboarding flow and mark as completed
    func skipOnboarding() {
        didSkipOnboarding = true
        storage.didSkipOnboarding = true
        completeOnboarding()
    }

    /// Mark onboarding as completed
    func completeOnboarding() {
        hasCompletedOnboarding = true
        storage.hasCompletedOnboarding = true
    }

    /// Returns true if the current page is the final onboarding page.
    ///
    /// Used to determine when to show the "Get Started" button instead of "Next",
    /// and to hide the skip option on the last page.
    var isLastPage: Bool {
        currentPage == totalPages - 1
    }

    /// Returns true if the skip button should be displayed.
    ///
    /// The skip button is shown on all pages except the last page, allowing users
    /// to bypass the remaining onboarding content and proceed directly to the app.
    var shouldShowSkip: Bool {
        !isLastPage
    }
}
