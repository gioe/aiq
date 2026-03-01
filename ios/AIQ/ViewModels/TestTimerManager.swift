import Combine
import Foundation
import UIKit

/// Manages the 30-minute countdown timer for IQ tests
@MainActor
class TestTimerManager: ObservableObject {
    // MARK: - Published Properties

    /// Remaining time in seconds (starts at 30 minutes)
    @Published private(set) var remainingSeconds: Int = Constants.Timing.totalTestTimeSeconds

    /// Whether to show the warning banner (shown at 5 minutes remaining)
    @Published private(set) var showWarning: Bool = false

    /// Whether the timer has expired
    @Published private(set) var hasExpired: Bool = false

    // MARK: - Constants

    /// Total time limit in seconds (30 minutes)
    static let totalTimeSeconds: Int = Constants.Timing.totalTestTimeSeconds

    /// Warning threshold in seconds (5 minutes)
    static let warningThresholdSeconds: Int = Constants.Timing.warningThresholdSeconds

    // MARK: - Private Properties

    private var timer: Timer?
    private var backgroundEntryTime: Date?
    private var wasRunningBeforeBackground: Bool = false

    /// Reference point for wall-clock based timing (eliminates drift)
    private var sessionStartTime: Date?

    /// Accumulated time from previous segments (used when pausing/resuming)
    private var accumulatedElapsedSeconds: Int = 0

    /// When the current timing segment started
    private var currentSegmentStartTime: Date?

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
        if remainingSeconds <= Constants.Timing.criticalThresholdSeconds {
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
        timer?.invalidate()
    }

    // MARK: - Timer Control

    /// Configures and starts the timer based on a session start time.
    /// Calculates elapsed time and sets remaining time accordingly.
    /// Uses wall-clock reference to eliminate timer drift over 30 minutes.
    /// - Parameter sessionStartedAt: The timestamp when the test session started
    /// - Returns: `true` if timer started successfully, `false` if time has already expired
    @discardableResult
    func startWithSessionTime(_ sessionStartedAt: Date) -> Bool {
        // Store the session start time as our reference point
        sessionStartTime = sessionStartedAt
        accumulatedElapsedSeconds = 0

        let elapsedSeconds = Int(Date().timeIntervalSince(sessionStartedAt))
        let remaining = Self.totalTimeSeconds - elapsedSeconds

        #if DEBUG
            print("[TIMER] Session started at: \(sessionStartedAt)")
            print("[TIMER] Elapsed since start: \(elapsedSeconds)s")
            print("[TIMER] Remaining time: \(remaining)s")
        #endif

        // Check if time has already expired
        if remaining <= 0 {
            remainingSeconds = 0
            hasExpired = true
            showWarning = true
            #if DEBUG
                print("[ERROR] Test time already expired! Elapsed: \(elapsedSeconds)s")
            #endif
            return false
        }

        // Set remaining time
        remainingSeconds = remaining

        // Check if we're already in warning territory
        if remaining <= Self.warningThresholdSeconds {
            showWarning = true
        }

        // Start the timer
        start()
        return true
    }

    /// Starts the countdown timer from current remainingSeconds value
    func start() {
        guard timer == nil else { return } // Already running

        // Record when this timing segment started
        currentSegmentStartTime = Date()

        // Use a faster interval for more responsive UI updates
        // while still using wall-clock reference for accuracy
        timer = Timer.scheduledTimer(
            withTimeInterval: Constants.Timing.timerUpdateInterval,
            repeats: true
        ) { [weak self] _ in
            Task { @MainActor in
                self?.tick()
            }
        }

        // Ensure timer runs even when scrolling
        if let timer {
            RunLoop.main.add(timer, forMode: .common)
        }

        #if DEBUG
            print("[TIMER] Test timer started: \(formattedTime) remaining")
        #endif
    }

    /// Pauses the timer (used when app backgrounds)
    func pause() {
        // Accumulate elapsed time from current segment before pausing
        if let segmentStart = currentSegmentStartTime {
            accumulatedElapsedSeconds += Int(Date().timeIntervalSince(segmentStart))
        }
        currentSegmentStartTime = nil

        timer?.invalidate()
        timer = nil

        #if DEBUG
            print("[TIMER] Test timer paused: \(formattedTime) remaining")
        #endif
    }

    /// Resumes the timer after being paused
    func resume() {
        guard timer == nil, !hasExpired else { return }
        start()

        #if DEBUG
            print("[TIMER] Test timer resumed: \(formattedTime) remaining")
        #endif
    }

    /// Stops and resets the timer
    func stop() {
        timer?.invalidate()
        timer = nil
        hasExpired = false

        #if DEBUG
            print("[TIMER] Test timer stopped")
        #endif
    }

    /// Resets the timer to full time
    func reset() {
        stop()
        remainingSeconds = Self.totalTimeSeconds
        showWarning = false
        hasExpired = false
        sessionStartTime = nil
        accumulatedElapsedSeconds = 0
        currentSegmentStartTime = nil

        #if DEBUG
            print("[TIMER] Test timer reset to \(formattedTime)")
        #endif
    }

    // MARK: - Private Methods

    /// Calculate remaining time using wall-clock reference to eliminate drift
    private func tick() {
        // Calculate total elapsed time using wall-clock
        var totalElapsed = accumulatedElapsedSeconds
        if let segmentStart = currentSegmentStartTime {
            totalElapsed += Int(Date().timeIntervalSince(segmentStart))
        }

        // If we have a session start time, use it directly for maximum accuracy
        if let sessionStart = sessionStartTime {
            totalElapsed = Int(Date().timeIntervalSince(sessionStart))
        }

        let newRemaining = max(0, Self.totalTimeSeconds - totalElapsed)

        // Only update if value changed (avoids unnecessary UI updates)
        guard newRemaining != remainingSeconds else { return }

        let previousRemaining = remainingSeconds
        remainingSeconds = newRemaining

        // Check if we crossed the warning threshold
        if previousRemaining > Self.warningThresholdSeconds && remainingSeconds <= Self.warningThresholdSeconds {
            showWarning = true
            #if DEBUG
                print("[TIMER] 5 minutes remaining warning triggered")
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
            print("[TIMER] Test timer expired!")
        #endif
    }

    // MARK: - Background Handling

    private func setupBackgroundNotifications() {
        NotificationCenter.default.addObserver(
            forName: UIApplication.willResignActiveNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            Task { @MainActor in self?.handleAppWillResignActive() }
        }
        NotificationCenter.default.addObserver(
            forName: UIApplication.didBecomeActiveNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            Task { @MainActor in self?.handleAppDidBecomeActive() }
        }
    }

    private func handleAppWillResignActive() {
        // Record whether timer was running
        wasRunningBeforeBackground = timer != nil
        backgroundEntryTime = Date()

        // Pause the timer (this accumulates elapsed time from current segment)
        if wasRunningBeforeBackground {
            pause()
        }

        #if DEBUG
            print("[APP] App backgrounded - timer was \(wasRunningBeforeBackground ? "running" : "stopped")")
        #endif
    }

    private func handleAppDidBecomeActive() {
        guard wasRunningBeforeBackground else {
            backgroundEntryTime = nil
            return
        }

        // Add the background time to accumulated elapsed seconds
        // (only if not using session start time, which handles this automatically)
        if sessionStartTime == nil, let backgroundTime = backgroundEntryTime {
            accumulatedElapsedSeconds += Int(Date().timeIntervalSince(backgroundTime))
        }

        backgroundEntryTime = nil
        wasRunningBeforeBackground = false

        // Resume if not expired - tick() will recalculate remaining time from wall-clock
        if !hasExpired {
            resume()
            // Immediately tick to update the display
            tick()

            // Check if timer expired while backgrounded
            if remainingSeconds == 0 {
                handleTimerExpired()
            }
        }

        #if DEBUG
            print("[APP] App foregrounded - \(formattedTime) remaining")
        #endif
    }
}

// MARK: - Timer Color State

enum TimerColorState {
    case normal
    case warning
    case critical
}
