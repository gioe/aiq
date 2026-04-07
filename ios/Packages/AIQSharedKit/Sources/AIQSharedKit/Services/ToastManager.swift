import Foundation
import os
import SwiftUI

/// Data model for a toast message
public struct ToastData: Identifiable, Equatable {
    public let id = UUID()
    public let message: String
    public let type: ToastType

    public init(message: String, type: ToastType) {
        self.message = message
        self.type = type
    }
}

/// Protocol for toast notification management
///
/// Allows the toast manager to be mocked in tests and injected via the DI container.
@MainActor
public protocol ToastManagerProtocol: ObservableObject {
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

/// Manager for displaying toast notifications globally
///
/// ToastManager provides a centralized way to show brief, non-intrusive messages
/// to users from anywhere in the app. Toasts auto-dismiss after 4 seconds.
/// Resolve via ServiceContainer rather than using a shared singleton.
///
/// Usage:
/// ```swift
/// // Show error toast
/// toastManager.show("Unable to open link", type: .error)
///
/// // Show warning toast
/// toastManager.show("Feature not available", type: .warning)
///
/// // Show info toast
/// toastManager.show("Test saved", type: .info)
/// ```
@MainActor
public class ToastManager: ObservableObject, ToastManagerProtocol {
    /// Currently displayed toast, if any
    @Published public private(set) var currentToast: ToastData?

    /// Auto-dismiss work item for cancellation
    private var dismissWorkItem: DispatchWorkItem?

    /// Duration before auto-dismissing (seconds)
    private let autoDismissDelay: TimeInterval = 4.0

    /// Logger for toast events
    private let logger: Logger

    /// Optional haptic manager for providing feedback when toasts appear
    private let hapticManager: HapticManagerProtocol?

    /// Initialize with an optional haptic manager and logger subsystem
    ///
    /// - Parameters:
    ///   - hapticManager: Optional haptic manager for feedback on toast display.
    ///   - loggerSubsystem: The subsystem identifier for logging. Defaults to the package bundle identifier.
    public init(
        hapticManager: HapticManagerProtocol? = nil,
        loggerSubsystem: String = "com.sharedkit"
    ) {
        self.hapticManager = hapticManager
        logger = Logger(subsystem: loggerSubsystem, category: "ToastManager")
    }

    /// Show a toast message
    ///
    /// If a toast is already displayed, it will be replaced with the new one.
    ///
    /// - Parameters:
    ///   - message: The message to display
    ///   - type: The type of toast (error, warning, or info)
    public func show(_ message: String, type: ToastType) {
        let typeDesc = String(describing: type)
        logger.info("Showing toast: \(message, privacy: .public) (type: \(typeDesc, privacy: .public))")

        // Map toast types to haptics: info uses selection for subtle feedback
        let hapticType: HapticType = switch type {
        case .error: .error
        case .warning: .warning
        case .info: .selection
        }
        hapticManager?.trigger(hapticType)

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
    public func dismiss() {
        logger.info("Dismissing toast")
        dismissWorkItem?.cancel()
        dismissWorkItem = nil
        currentToast = nil
    }
}
