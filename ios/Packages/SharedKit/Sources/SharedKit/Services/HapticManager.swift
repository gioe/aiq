import Foundation
import os

/// Types of haptic feedback available in the app
///
/// Each type maps to appropriate UIKit haptic generators:
/// - `success`, `error`, `warning`: Use notification feedback
/// - `selection`: Uses selection feedback for subtle UI interactions
/// - `light`, `medium`, `heavy`: Use impact feedback with varying intensity
public enum HapticType {
    /// Positive outcome (e.g., test completed, answer correct)
    case success
    /// Negative outcome (e.g., network error, validation failure)
    case error
    /// Caution needed (e.g., warning message, destructive action)
    case warning
    /// Subtle feedback for UI selections (e.g., tab switch, toggle)
    case selection
    /// Light impact for subtle interactions
    case light
    /// Medium impact for standard interactions
    case medium
    /// Heavy impact for significant interactions
    case heavy
}

/// Protocol for haptic feedback management
///
/// Allows the haptic manager to be mocked in tests and injected via the DI container.
@MainActor
public protocol HapticManagerProtocol {
    /// Trigger haptic feedback
    ///
    /// Automatically respects system haptic settings. If the user has disabled
    /// haptics at the system level, this method does nothing.
    ///
    /// - Parameter type: The type of haptic feedback to trigger
    func trigger(_ type: HapticType)

    /// Prepare haptic generators for lower latency
    ///
    /// Call this before a known interaction (e.g., when a view appears)
    /// to reduce latency when `trigger` is called.
    func prepare()
}

#if canImport(UIKit)
    import UIKit

    /// Manager for triggering haptic feedback throughout the app
    ///
    /// HapticManager provides a centralized way to trigger haptic feedback
    /// while automatically respecting system haptic settings. Generators are
    /// pre-prepared for lower latency.
    ///
    /// Usage:
    /// ```swift
    /// // Create instance (typically injected via DI)
    /// let hapticManager = HapticManager()
    ///
    /// // Trigger success haptic
    /// hapticManager.trigger(.success)
    ///
    /// // Trigger selection haptic for UI interactions
    /// hapticManager.trigger(.selection)
    ///
    /// // Prepare generators before expected interaction
    /// hapticManager.prepare()
    /// ```
    @MainActor
    public class HapticManager: HapticManagerProtocol {
        /// Logger for haptic events
        private let logger: Logger

        /// Notification feedback generator for success/error/warning
        private let notificationGenerator = UINotificationFeedbackGenerator()

        /// Selection feedback generator for subtle UI interactions
        private let selectionGenerator = UISelectionFeedbackGenerator()

        /// Light impact generator
        private let lightImpactGenerator = UIImpactFeedbackGenerator(style: .light)

        /// Medium impact generator
        private let mediumImpactGenerator = UIImpactFeedbackGenerator(style: .medium)

        /// Heavy impact generator
        private let heavyImpactGenerator = UIImpactFeedbackGenerator(style: .heavy)

        /// Initialize with an optional logger subsystem identifier
        ///
        /// - Parameter subsystem: The subsystem identifier for logging. Defaults to the package bundle identifier.
        public init(subsystem: String = "com.sharedkit") {
            logger = Logger(subsystem: subsystem, category: "HapticManager")
            logger.debug("HapticManager initialized")
            prepare()
        }

        /// Trigger haptic feedback
        ///
        /// Automatically respects system haptic and accessibility settings.
        /// If the user has disabled haptics at the system level or enabled
        /// Reduce Motion in accessibility settings, this method does nothing.
        ///
        /// - Parameter type: The type of haptic feedback to trigger
        public func trigger(_ type: HapticType) {
            // Respect accessibility settings - users with motion sensitivity
            guard !UIAccessibility.isReduceMotionEnabled else {
                logger.debug("Haptic skipped (Reduce Motion enabled)")
                return
            }

            let typeDesc = String(describing: type)
            logger.debug("Triggering haptic: \(typeDesc, privacy: .public)")

            switch type {
            case .success:
                notificationGenerator.notificationOccurred(.success)
            case .error:
                notificationGenerator.notificationOccurred(.error)
            case .warning:
                notificationGenerator.notificationOccurred(.warning)
            case .selection:
                selectionGenerator.selectionChanged()
            case .light:
                lightImpactGenerator.impactOccurred()
            case .medium:
                mediumImpactGenerator.impactOccurred()
            case .heavy:
                heavyImpactGenerator.impactOccurred()
            }
        }

        /// Prepare haptic generators for lower latency
        ///
        /// Calling prepare() puts the Taptic Engine in a prepared state.
        /// This reduces latency when `trigger` is subsequently called.
        /// The prepared state times out after a few seconds of inactivity.
        public func prepare() {
            logger.debug("Preparing haptic generators")
            notificationGenerator.prepare()
            selectionGenerator.prepare()
            lightImpactGenerator.prepare()
            mediumImpactGenerator.prepare()
            heavyImpactGenerator.prepare()
        }
    }
#else
    /// No-op haptic manager for non-UIKit platforms (macOS, Linux).
    @MainActor
    public class HapticManager: HapticManagerProtocol {
        public init(subsystem _: String = "com.sharedkit") {}
        public func trigger(_: HapticType) {}
        public func prepare() {}
    }
#endif
