import AIQSharedKit
import Foundation

/// ViewModel for managing the pre-test onboarding flow state
/// Does NOT inherit from BaseViewModel as this is simple navigation state with no API calls
@MainActor
class PreTestOnboardingViewModel: ObservableObject {
    // MARK: - Published Properties

    /// Current page index
    @Published var currentPage: Int = 0

    // MARK: - Private Properties

    /// Total number of pages (3 without notification page, 4 with)
    let totalPages: Int

    // MARK: - Initialization

    /// Creates a view model for the pre-test onboarding flow
    /// - Parameter showNotificationPage: Whether to include the notification permission page
    init(showNotificationPage: Bool) {
        totalPages = showNotificationPage ? 4 : 3
    }

    // MARK: - Public Methods

    /// Navigate to the next page
    func nextPage() {
        guard currentPage < totalPages - 1 else { return }
        currentPage += 1
    }

    /// Returns true if the current page is the final page
    var isLastPage: Bool {
        currentPage == totalPages - 1
    }

    /// Returns true if the current page is the notification page (page index 3)
    var isNotificationPage: Bool {
        totalPages == 4 && currentPage == 3
    }
}
