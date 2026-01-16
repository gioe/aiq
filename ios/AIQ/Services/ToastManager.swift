import Foundation
import os
import SwiftUI

/// Data model for a toast message
struct ToastData: Identifiable, Equatable {
    let id = UUID()
    let message: String
    let type: ToastType
}

/// Singleton manager for displaying toast notifications globally
///
/// ToastManager provides a centralized way to show brief, non-intrusive messages
/// to users from anywhere in the app. Toasts auto-dismiss after 4 seconds.
///
/// Usage:
/// ```swift
/// // Show error toast
/// ToastManager.shared.show("Unable to open link", type: .error)
///
/// // Show warning toast
/// ToastManager.shared.show("Feature not available", type: .warning)
///
/// // Show info toast
/// ToastManager.shared.show("Test saved", type: .info)
/// ```
///
/// Integration:
/// RootView observes `currentToast` and displays a ToastView overlay when non-nil.
@MainActor
class ToastManager: ObservableObject {
    /// Shared singleton instance
    static let shared = ToastManager()

    /// Currently displayed toast, if any
    @Published private(set) var currentToast: ToastData?

    /// Auto-dismiss timer
    private var dismissTimer: Timer?

    /// Duration before auto-dismissing (seconds)
    private let autoDismissDelay: TimeInterval = 4.0

    /// Logger for toast events
    private static let logger = Logger(subsystem: "com.aiq.app", category: "ToastManager")

    private init() {}

    /// Show a toast message
    ///
    /// If a toast is already displayed, it will be replaced with the new one.
    ///
    /// - Parameters:
    ///   - message: The message to display
    ///   - type: The type of toast (error, warning, or info)
    func show(_ message: String, type: ToastType) {
        let typeDesc = String(describing: type)
        Self.logger.info("Showing toast: \(message, privacy: .public) (type: \(typeDesc, privacy: .public))")

        // Cancel existing timer if any
        dismissTimer?.invalidate()

        // Set the new toast
        currentToast = ToastData(message: message, type: type)

        // Schedule auto-dismiss
        dismissTimer = Timer.scheduledTimer(withTimeInterval: autoDismissDelay, repeats: false) { [weak self] _ in
            Task { @MainActor in
                self?.dismiss()
            }
        }
    }

    /// Manually dismiss the current toast
    func dismiss() {
        Self.logger.info("Dismissing toast")
        dismissTimer?.invalidate()
        dismissTimer = nil
        currentToast = nil
    }
}
