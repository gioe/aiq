import Combine
import Foundation
import UIKit

/// Manages the 30-minute countdown timer for IQ tests
@MainActor
class TestTimerManager: ObservableObject {
    // MARK: - Published Properties

    /// Remaining time in seconds (starts at 30 minutes = 1800 seconds)
    @Published private(set) var remainingSeconds: Int = 1800

    /// Whether to show the warning banner (shown at 5 minutes remaining)
    @Published private(set) var showWarning: Bool = false

    /// Whether the timer has expired
    @Published private(set) var hasExpired: Bool = false

    // MARK: - Constants

    /// Total time limit in seconds (30 minutes)
    static let totalTimeSeconds: Int = 1800

    /// Warning threshold in seconds (5 minutes)
    static let warningThresholdSeconds: Int = 300

    // MARK: - Private Properties

    private var timer: Timer?
    private var backgroundEntryTime: Date?
    private var wasRunningBeforeBackground: Bool = false

    // MARK: - Computed Properties

    /// Formatted time string in MM:SS format
    var formattedTime: String {
        let minutes = remainingSeconds / 60
        let seconds = remainingSeconds % 60
        return String(format: "%02d:%02d", minutes, seconds)
    }

    /// Progress from 0.0 (time up) to 1.0 (full time)
    var progress: Double {
        Double(remainingSeconds) / Double(Self.totalTimeSeconds)
    }

    /// Color for the timer based on remaining time
    var timerColor: TimerColorState {
        if remainingSeconds <= 60 {
            .critical // Last minute - red
        } else if remainingSeconds <= Self.warningThresholdSeconds {
            .warning // Last 5 minutes - orange/yellow
        } else {
            .normal // Normal - default color
        }
    }

    // MARK: - Initialization

    init() {
        setupBackgroundNotifications()
    }

    deinit {
        NotificationCenter.default.removeObserver(self)
        timer?.invalidate()
    }

    // MARK: - Timer Control

    /// Starts the countdown timer
    func start() {
        guard timer == nil else { return } // Already running

        timer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.tick()
            }
        }

        // Ensure timer runs even when scrolling
        if let timer {
            RunLoop.main.add(timer, forMode: .common)
        }

        #if DEBUG
            print("⏱️ Test timer started: \(formattedTime) remaining")
        #endif
    }

    /// Pauses the timer (used when app backgrounds)
    func pause() {
        timer?.invalidate()
        timer = nil

        #if DEBUG
            print("⏸️ Test timer paused: \(formattedTime) remaining")
        #endif
    }

    /// Resumes the timer after being paused
    func resume() {
        guard timer == nil, !hasExpired else { return }
        start()

        #if DEBUG
            print("▶️ Test timer resumed: \(formattedTime) remaining")
        #endif
    }

    /// Stops and resets the timer
    func stop() {
        timer?.invalidate()
        timer = nil
        hasExpired = false

        #if DEBUG
            print("⏹️ Test timer stopped")
        #endif
    }

    /// Resets the timer to full time
    func reset() {
        stop()
        remainingSeconds = Self.totalTimeSeconds
        showWarning = false
        hasExpired = false

        #if DEBUG
            print("🔄 Test timer reset to \(formattedTime)")
        #endif
    }

    // MARK: - Private Methods

    private func tick() {
        guard remainingSeconds > 0 else {
            handleTimerExpired()
            return
        }

        remainingSeconds -= 1

        // Check if we should show warning
        if remainingSeconds == Self.warningThresholdSeconds {
            showWarning = true
            #if DEBUG
                print("⚠️ 5 minutes remaining warning triggered")
            #endif
        }

        // Check if timer has expired
        if remainingSeconds == 0 {
            handleTimerExpired()
        }
    }

    private func handleTimerExpired() {
        timer?.invalidate()
        timer = nil
        hasExpired = true

        #if DEBUG
            print("🚨 Test timer expired!")
        #endif
    }

    // MARK: - Background Handling

    private func setupBackgroundNotifications() {
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(handleAppWillResignActive),
            name: UIApplication.willResignActiveNotification,
            object: nil
        )
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(handleAppDidBecomeActive),
            name: UIApplication.didBecomeActiveNotification,
            object: nil
        )
    }

    @objc private func handleAppWillResignActive() {
        // Record whether timer was running and when we went to background
        wasRunningBeforeBackground = timer != nil
        backgroundEntryTime = Date()

        // Pause the timer
        if wasRunningBeforeBackground {
            pause()
        }

        #if DEBUG
            print("📱 App backgrounded - timer was \(wasRunningBeforeBackground ? "running" : "stopped")")
        #endif
    }

    @objc private func handleAppDidBecomeActive() {
        // Calculate elapsed time while backgrounded
        if let backgroundTime = backgroundEntryTime {
            let elapsedSeconds = Int(Date().timeIntervalSince(backgroundTime))

            // Subtract elapsed time from remaining (but don't go below 0)
            remainingSeconds = max(0, remainingSeconds - elapsedSeconds)

            // Check if we should now show warning
            if remainingSeconds <= Self.warningThresholdSeconds && !showWarning {
                showWarning = true
            }

            // Check if timer expired while backgrounded
            if remainingSeconds == 0 {
                handleTimerExpired()
            }

            #if DEBUG
                print("📱 App foregrounded - \(elapsedSeconds)s elapsed, \(formattedTime) remaining")
            #endif
        }

        backgroundEntryTime = nil

        // Resume if it was running before
        if wasRunningBeforeBackground && !hasExpired {
            resume()
        }
        wasRunningBeforeBackground = false
    }
}

// MARK: - Timer Color State

enum TimerColorState {
    case normal
    case warning
    case critical
}
