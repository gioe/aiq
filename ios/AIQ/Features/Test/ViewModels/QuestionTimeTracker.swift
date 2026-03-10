import Foundation
import UIKit

/// Tracks cumulative time spent on each question during a test session.
/// Handles app backgrounding by pausing and resuming timing automatically.
@MainActor
class QuestionTimeTracker {
    // MARK: - Private Properties

    private let clock: any TimeProvider
    private let notificationCenter: NotificationCenter
    private var questionTimeSpent: [Int: Int] = [:]
    private var currentQuestionId: Int?
    private var currentQuestionStartTime: Date?

    // MARK: - Initialization

    init(clock: any TimeProvider = SystemTimeProvider(), notificationCenter: NotificationCenter = .default) {
        self.clock = clock
        self.notificationCenter = notificationCenter
        setupBackgroundNotifications()
    }

    // MARK: - Public API

    /// Starts timing for the given question.
    func startTracking(questionId: Int) {
        #if DEBUG
            if currentQuestionStartTime != nil {
                assertionFailure("[TIMING] startTracking called while already tracking — missing recordCurrent() call")
            }
        #endif
        currentQuestionId = questionId
        currentQuestionStartTime = clock.now
    }

    /// Records elapsed time for the current question and stops active tracking.
    func recordCurrent() {
        guard let startTime = currentQuestionStartTime,
              let questionId = currentQuestionId else { return }
        let elapsed = Int(clock.now.timeIntervalSince(startTime))
        questionTimeSpent[questionId, default: 0] += elapsed
        currentQuestionStartTime = nil
        currentQuestionId = nil
        #if DEBUG
            print("[TIMING] Question \(questionId): +\(elapsed)s (total: \(questionTimeSpent[questionId] ?? 0)s)")
        #endif
    }

    /// Returns cumulative seconds spent on the given question.
    func elapsed(for questionId: Int) -> Int {
        questionTimeSpent[questionId] ?? 0
    }

    /// Clears all timing data.
    func reset() {
        questionTimeSpent.removeAll()
        currentQuestionId = nil
        currentQuestionStartTime = nil
    }

    // MARK: - Background Handling

    private func setupBackgroundNotifications() {
        notificationCenter.addObserver(
            forName: UIApplication.willResignActiveNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            Task { @MainActor in self?.pauseTracking() }
        }
        notificationCenter.addObserver(
            forName: UIApplication.didBecomeActiveNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            Task { @MainActor in self?.resumeTracking() }
        }
    }

    private func pauseTracking() {
        guard let startTime = currentQuestionStartTime,
              let questionId = currentQuestionId else { return }
        let elapsed = Int(clock.now.timeIntervalSince(startTime))
        questionTimeSpent[questionId, default: 0] += elapsed
        currentQuestionStartTime = nil
        // Keep currentQuestionId so resumeTracking knows to restart
        #if DEBUG
            print("[TIMING] Time tracking paused - app backgrounded")
        #endif
    }

    private func resumeTracking() {
        guard currentQuestionId != nil else { return }
        currentQuestionStartTime = clock.now
        #if DEBUG
            print("[TIMING] Time tracking resumed - app foregrounded")
        #endif
    }
}
