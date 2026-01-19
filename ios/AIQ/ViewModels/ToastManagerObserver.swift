import Combine
import Foundation
import SwiftUI

/// Observable wrapper for ToastManagerProtocol
///
/// This class enables SwiftUI views to observe any `ToastManagerProtocol` implementation
/// through `@StateObject` or `@ObservedObject`. It subscribes to the protocol's
/// Combine publishers and exposes the state as `@Published` properties.
///
/// ## Usage
///
/// ```swift
/// struct SomeView: View {
///     @StateObject private var toastObserver = ToastManagerObserver()
///
///     var body: some View {
///         if let toast = toastObserver.currentToast {
///             ToastView(toast: toast)
///         }
///     }
/// }
/// ```
///
/// ## Thread Safety
///
/// This class uses `@MainActor` to ensure all property updates occur on the main thread,
/// which is required for SwiftUI view updates.
///
/// ## Concrete Type Casting Limitation
///
/// Due to Swift protocol limitations, subscribing to `@Published` properties requires casting
/// to the concrete `ToastManager` type. If a mock implementation is registered that doesn't
/// inherit from `ToastManager`, state updates won't propagate via Combine subscriptions.
/// The observer will still capture the initial state correctly, but dynamic updates require
/// the concrete type. This is the same pattern used by `AuthStateObserver`.
@MainActor
final class ToastManagerObserver: ObservableObject {
    // MARK: - Published State

    @Published private(set) var currentToast: ToastData?

    // MARK: - Private Properties

    private let manager: any ToastManagerProtocol
    private var cancellables = Set<AnyCancellable>()

    // MARK: - Initialization

    /// Creates an observer for the ToastManager resolved from the service container
    ///
    /// - Parameter container: The service container to resolve the ToastManager from.
    ///                        Defaults to the shared container.
    init(container: ServiceContainer = .shared) {
        guard let resolvedManager = container.resolve(ToastManagerProtocol.self) else {
            fatalError("ToastManagerProtocol not registered in ServiceContainer")
        }
        manager = resolvedManager

        // Set initial state
        currentToast = manager.currentToast

        // Subscribe to changes if the manager is an ObservableObject
        // We need to cast to ToastManager to access its @Published property
        if let toastManager = manager as? ToastManager {
            toastManager.$currentToast
                .receive(on: DispatchQueue.main)
                .sink { [weak self] value in
                    self?.currentToast = value
                }
                .store(in: &cancellables)
        }
    }

    /// Creates an observer with an explicit ToastManager (for testing)
    ///
    /// - Parameter manager: The toast manager to observe
    init(manager: any ToastManagerProtocol) {
        self.manager = manager

        // Set initial state
        currentToast = manager.currentToast

        // Subscribe to changes if the manager is an ObservableObject
        if let toastManager = manager as? ToastManager {
            toastManager.$currentToast
                .receive(on: DispatchQueue.main)
                .sink { [weak self] value in
                    self?.currentToast = value
                }
                .store(in: &cancellables)
        }
    }

    // MARK: - Actions (Delegate to ToastManager)

    /// Show a toast message
    ///
    /// - Parameters:
    ///   - message: The message to display
    ///   - type: The type of toast (error, warning, or info)
    func show(_ message: String, type: ToastType) {
        manager.show(message, type: type)
    }

    /// Manually dismiss the current toast
    func dismiss() {
        manager.dismiss()
    }
}
