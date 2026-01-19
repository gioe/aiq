import Foundation
import os
import SwiftUI

/// Data model for a toast message
struct ToastData: Identifiable, Equatable {
    let id = UUID()
    let message: String
    let type: ToastType
}

/// Protocol for toast notification management
///
/// Allows the toast manager to be mocked in tests and injected via the DI container.
@MainActor
protocol ToastManagerProtocol: ObservableObject {
    /// Currently displayed toast, if any
    var currentToast: ToastData? { get }

    /// Show a toast message
    ///
    /// - Parameters:
    ///   - message: The message to display
    ///   - type: The type of toast (error, warning, or info)
    func show(_ message: String, type: ToastType)

    /// Manually dismiss the current toast
    func dismiss()
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
class ToastManager: ObservableObject, ToastManagerProtocol {
    /// Shared singleton instance
    static let shared = ToastManager()

    /// Currently displayed toast, if any
    @Published private(set) var currentToast: ToastData?

    /// Auto-dismiss work item for cancellation
    private var dismissWorkItem: DispatchWorkItem?

    /// Duration before auto-dismissing (seconds)
    private let autoDismissDelay: TimeInterval = 4.0

    /// Logger for toast events
    private static let logger = Logger(subsystem: "com.aiq.app", category: "ToastManager")

    /// Internal initializer for dependency injection
    ///
    /// Used by ServiceConfiguration to create the instance owned by the container.
    /// The `shared` singleton is retained for backward compatibility but new code
    /// should resolve ToastManagerProtocol from the ServiceContainer.
    init() {}

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

        // Cancel existing dismiss work item if any
        dismissWorkItem?.cancel()

        // Set the new toast
        currentToast = ToastData(message: message, type: type)

        // Schedule auto-dismiss using DispatchQueue for reliable main thread execution
        let workItem = DispatchWorkItem { [weak self] in
            self?.dismiss()
        }
        dismissWorkItem = workItem
        DispatchQueue.main.asyncAfter(deadline: .now() + autoDismissDelay, execute: workItem)
    }

    /// Manually dismiss the current toast
    func dismiss() {
        Self.logger.info("Dismissing toast")
        dismissWorkItem?.cancel()
        dismissWorkItem = nil
        currentToast = nil
    }
}
