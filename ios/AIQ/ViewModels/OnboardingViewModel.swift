import SwiftUI

/// ViewModel for managing onboarding flow state
/// Does NOT inherit from BaseViewModel as this is simple navigation state with no API calls
@MainActor
class OnboardingViewModel: ObservableObject {
    // MARK: - Published Properties

    /// Current page index (0-3)
    @Published var currentPage: Int = 0

    /// Whether onboarding has been completed
    @AppStorage("hasCompletedOnboarding") var hasCompletedOnboarding: Bool = false

    // MARK: - Constants

    /// Total number of onboarding pages
    private let totalPages = 4

    // MARK: - Public Methods

    /// Navigate to the next page
    func nextPage() {
        guard currentPage < totalPages - 1 else { return }
        currentPage += 1
    }

    /// Skip the onboarding flow and mark as completed
    func skipOnboarding() {
        completeOnboarding()
    }

    /// Mark onboarding as completed
    func completeOnboarding() {
        hasCompletedOnboarding = true
    }

    /// Check if the current page is the last page
    var isLastPage: Bool {
        currentPage == totalPages - 1
    }

    /// Check if skip button should be shown (pages 0-2, not on last page)
    var shouldShowSkip: Bool {
        !isLastPage
    }
}
