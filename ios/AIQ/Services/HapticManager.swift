import Foundation
import os
import UIKit

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

/// Manager for triggering haptic feedback throughout the app
///
/// HapticManager provides a centralized way to trigger haptic feedback
/// while automatically respecting system haptic settings. Generators are
/// pre-prepared for lower latency.
///
/// Usage:
/// ```swift
/// // Resolve from ServiceContainer
/// let hapticManager = ServiceContainer.shared.resolve(HapticManagerProtocol.self)
///
/// // Trigger success haptic
/// hapticManager?.trigger(.success)
///
/// // Trigger selection haptic for UI interactions
/// hapticManager?.trigger(.selection)
///
/// // Prepare generators before expected interaction
/// hapticManager?.prepare()
/// ```
///
/// Integration:
/// HapticManager is registered in ServiceConfiguration and should be resolved
/// via dependency injection from the ServiceContainer.
@MainActor
public class HapticManager: HapticManagerProtocol {
    /// Logger for haptic events
    private static let logger = Logger(subsystem: "com.aiq.app", category: "HapticManager")

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

    /// Internal initializer for dependency injection
    ///
    /// Used by ServiceConfiguration to create the instance owned by the container.
    /// Instances should be resolved via ServiceContainer.shared.resolve(HapticManagerProtocol.self).
    public init() {
        Self.logger.debug("HapticManager initialized")
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
            Self.logger.debug("Haptic skipped (Reduce Motion enabled)")
            return
        }

        let typeDesc = String(describing: type)
        Self.logger.debug("Triggering haptic: \(typeDesc, privacy: .public)")

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
        Self.logger.debug("Preparing haptic generators")
        notificationGenerator.prepare()
        selectionGenerator.prepare()
        lightImpactGenerator.prepare()
        mediumImpactGenerator.prepare()
        heavyImpactGenerator.prepare()
    }
}
