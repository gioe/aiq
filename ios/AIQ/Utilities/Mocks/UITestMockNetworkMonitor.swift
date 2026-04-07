//
//  UITestMockNetworkMonitor.swift
//  AIQ
//
//  Created by Claude Code on 1/19/26.
//

import AIQSharedKit
import Combine
import Foundation

#if DebugBuild

    /// Mock NetworkMonitor for UI tests
    ///
    /// This mock provides a simple implementation that reports the network
    /// as always connected. For UI tests, we don't need actual network
    /// connectivity monitoring since all API calls are mocked.
    final class UITestMockNetworkMonitor: NetworkMonitorProtocol {
        /// Always returns true for UI tests (network is "connected")
        var isConnected: Bool = true

        /// Always-connected publisher for UI tests
        var connectivityPublisher: AnyPublisher<Bool, Never> {
            Just(true).eraseToAnyPublisher()
        }

        init() {}
    }

#endif
