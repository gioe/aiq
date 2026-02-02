import Foundation
import os

/// Result of a deep link navigation attempt
enum DeepLinkNavigationResult: Equatable {
    /// Successfully navigated to the specified tab
    case navigated(tab: TabDestination)

    /// Navigation was dropped due to concurrent processing
    case dropped

    /// Invalid deep link that couldn't be processed
    case invalid

    /// Navigation failed (e.g., API error when fetching test results)
    case failed(DeepLink)
}

/// Callback type for updating the selected tab
///
/// MainTabView provides this closure to allow the service to update
/// the @AppStorage selectedTab binding without importing SwiftUI.
typealias TabSelectionHandler = (TabDestination) -> Void

/// Protocol for deep link navigation service (enables testing)
@MainActor
protocol DeepLinkNavigationServiceProtocol {
    /// Navigate to a deep link destination
    ///
    /// - Parameters:
    ///   - deepLink: The parsed deep link to navigate to
    ///   - source: The source of the deep link for analytics tracking
    ///   - originalURL: The original URL string for analytics tracking
    /// - Returns: The result of the navigation attempt
    func navigate(
        to deepLink: DeepLink,
        source: DeepLinkSource,
        originalURL: String
    ) async -> DeepLinkNavigationResult
}

/// Service responsible for handling deep link navigation
///
/// This service extracts the navigation logic from MainTabView into a testable,
/// standalone component. It coordinates tab switching, router navigation, and
/// error handling for all deep link types.
///
/// The service manages a concurrent processing guard to prevent multiple deep links
/// from being processed simultaneously. Concurrent deep links are dropped rather than
/// queued, as each deep link represents user intent at a specific moment.
///
/// Usage:
/// ```swift
/// let service = DeepLinkNavigationService(
///     router: router,
///     deepLinkHandler: deepLinkHandler,
///     tabSelectionHandler: { newTab in
///         selectedTab = newTab
///     }
/// )
///
/// let result = await service.navigate(to: deepLink, source: .pushNotification, originalURL: urlString)
/// ```
@MainActor
final class DeepLinkNavigationService: DeepLinkNavigationServiceProtocol {
    // MARK: - Properties

    /// Logger for navigation events
    private static let logger = Logger(subsystem: "com.aiq.app", category: "DeepLinkNavigation")

    /// App router for managing navigation stacks
    private let router: AppRouter

    /// Deep link handler for async navigation (test results, resume test)
    private let deepLinkHandler: DeepLinkHandler

    /// Callback to update the selected tab in MainTabView
    private let tabSelectionHandler: TabSelectionHandler

    /// Tracks whether a deep link is currently being processed to prevent concurrent handling
    ///
    /// Thread-safety: This service is @MainActor, ensuring all access happens on the main thread.
    /// MainTabView's notification handlers use `.receive(on: DispatchQueue.main)` to ensure
    /// main thread execution before calling this service.
    private var isProcessingDeepLink = false

    // MARK: - Initialization

    /// Initialize the navigation service
    ///
    /// - Parameters:
    ///   - router: The app router for managing navigation stacks
    ///   - deepLinkHandler: The deep link handler for async navigation
    ///   - tabSelectionHandler: Callback to update the selected tab in MainTabView
    init(
        router: AppRouter,
        deepLinkHandler: DeepLinkHandler,
        tabSelectionHandler: @escaping TabSelectionHandler
    ) {
        self.router = router
        self.deepLinkHandler = deepLinkHandler
        self.tabSelectionHandler = tabSelectionHandler
    }

    // MARK: - Public API

    /// Navigate to a deep link destination
    ///
    /// This method coordinates tab switching, router navigation, and error handling
    /// for all deep link types. It implements a concurrent processing guard to prevent
    /// multiple deep links from being handled simultaneously.
    ///
    /// - Parameters:
    ///   - deepLink: The parsed deep link to navigate to
    ///   - source: The source of the deep link for analytics tracking
    ///   - originalURL: The original URL string for analytics tracking
    /// - Returns: The result of the navigation attempt
    ///
    /// - Note: Concurrent deep links are dropped (not queued) while one is being processed.
    ///   This is intentional because deep links represent user intent at a specific moment.
    ///   Processing an older deep link after a newer one completes would create unexpected
    ///   navigation and poor UX.
    func navigate(
        to deepLink: DeepLink,
        source: DeepLinkSource = .unknown,
        originalURL: String = ""
    ) async -> DeepLinkNavigationResult {
        // Guard against concurrent deep link processing.
        // The flag is set before Task creation to prevent race conditions.
        guard !isProcessingDeepLink else {
            let deepLinkDescription = String(describing: deepLink)
            Self.logger.info("Dropping deep link (concurrent): \(deepLinkDescription, privacy: .public)")
            return .dropped
        }

        isProcessingDeepLink = true
        defer { isProcessingDeepLink = false }

        switch deepLink {
        case .settings:
            return await handleSettingsNavigation(source: source, originalURL: originalURL)

        case .testResults, .resumeTest:
            return await handleTestNavigation(
                deepLink,
                source: source,
                originalURL: originalURL
            )

        case .invalid:
            Self.logger.warning("Received invalid deep link: \(String(describing: deepLink), privacy: .public)")
            return .invalid
        }
    }

    // MARK: - Private Helpers

    /// Handle settings deep link navigation
    ///
    /// Settings navigation is handled at the tab level (switching to the settings tab)
    /// rather than pushing a route onto the navigation stack.
    private func handleSettingsNavigation(
        source: DeepLinkSource,
        originalURL: String
    ) async -> DeepLinkNavigationResult {
        // Switch to the settings tab
        tabSelectionHandler(.settings)
        router.currentTab = .settings
        router.popToRoot(in: .settings) // Pop to root in case there's a navigation stack

        // Track successful navigation for settings (handled here, not in DeepLinkHandler)
        deepLinkHandler.trackNavigationSuccess(
            .settings,
            source: source,
            originalURL: originalURL
        )

        return .navigated(tab: .settings)
    }

    /// Handle test-related deep link navigation (.testResults, .resumeTest)
    ///
    /// Test navigation requires switching to the dashboard tab and then performing
    /// async navigation via DeepLinkHandler.
    private func handleTestNavigation(
        _ deepLink: DeepLink,
        source: DeepLinkSource,
        originalURL: String
    ) async -> DeepLinkNavigationResult {
        // Switch to Dashboard tab first for test-related deep links
        // This ensures navigation happens in the correct tab context
        tabSelectionHandler(.dashboard)
        router.currentTab = .dashboard
        router.popToRoot(in: .dashboard) // Clear any existing navigation stack

        // Delegate to DeepLinkHandler for async navigation (may require API calls)
        let success = await deepLinkHandler.handleNavigation(
            deepLink,
            router: router,
            tab: .dashboard,
            source: source,
            originalURL: originalURL
        )

        if !success {
            handleNavigationFailure(deepLink: deepLink)
            return .failed(deepLink)
        }

        return .navigated(tab: .dashboard)
    }

    /// Handle navigation failure by logging and showing user-friendly error toast
    private func handleNavigationFailure(deepLink: DeepLink) {
        let linkDesc = String(describing: deepLink)
        Self.logger.error("Failed to handle deep link: \(linkDesc, privacy: .public)")

        // Show user-friendly error toast based on deep link type
        let message = switch deepLink {
        case .testResults:
            // Navigation failed due to API error (couldn't fetch test results)
            "toast.deeplink.navigation.failed".localized
        case .resumeTest:
            // Resume test not yet implemented
            "toast.deeplink.resume.unavailable".localized
        default:
            "toast.deeplink.navigation.failed".localized
        }

        ToastManager.shared.show(message, type: .error)
    }
}
