//
//  UITestMockToastManager.swift
//  AIQ
//
//  Created by Claude Code on 1/19/26.
//

import Foundation

#if DEBUG

    /// Mock ToastManager for UI tests
    ///
    /// This mock provides a no-op implementation of toast notifications.
    /// For UI tests, we don't need actual toast display since we're testing
    /// specific flows rather than toast behavior.
    @MainActor
    final class UITestMockToastManager: ObservableObject, ToastManagerProtocol {
        /// Current toast (always nil for mock)
        @Published var currentToast: ToastData?

        init() {}

        /// No-op implementation for showing toasts in UI tests
        func show(_: String, type _: ToastType) {
            // No-op for UI tests
        }

        /// No-op implementation for dismissing toasts in UI tests
        func dismiss() {
            // No-op for UI tests
        }
    }

#endif
