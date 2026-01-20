//
//  UITestMockNetworkMonitor.swift
//  AIQ
//
//  Created by Claude Code on 1/19/26.
//

import Foundation

#if DEBUG

    /// Mock NetworkMonitor for UI tests
    ///
    /// This mock provides a simple implementation that reports the network
    /// as always connected. For UI tests, we don't need actual network
    /// connectivity monitoring since all API calls are mocked.
    final class UITestMockNetworkMonitor: NetworkMonitorProtocol {
        /// Always returns true for UI tests (network is "connected")
        var isConnected: Bool = true

        init() {}
    }

#endif
