import Foundation

#if DEBUG

    /// Mock HapticManager for UI tests
    ///
    /// This mock provides a no-op haptic manager that doesn't trigger
    /// haptic feedback during UI tests.
    @MainActor
    final class UITestMockHapticManager: HapticManagerProtocol {
        /// Tracks the last triggered haptic type for test assertions
        private(set) var lastTriggeredType: HapticType?

        /// Counts how many times trigger was called
        private(set) var triggerCallCount: Int = 0

        /// Counts how many times prepare was called
        private(set) var prepareCallCount: Int = 0

        init() {}

        func trigger(_ type: HapticType) {
            lastTriggeredType = type
            triggerCallCount += 1
        }

        func prepare() {
            prepareCallCount += 1
        }

        /// Reset tracking state for test isolation
        func reset() {
            lastTriggeredType = nil
            triggerCallCount = 0
            prepareCallCount = 0
        }
    }

#endif
