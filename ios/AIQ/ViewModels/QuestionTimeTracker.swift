import Foundation
import UIKit

/// Tracks cumulative time spent on each question during a test session.
/// Handles app backgrounding by pausing and resuming timing automatically.
@MainActor
class QuestionTimeTracker {
    // MARK: - Private Properties

    private var questionTimeSpent: [Int: Int] = [:]
    private var currentQuestionId: Int?
    private var currentQuestionStartTime: Date?

    // MARK: - Initialization

    init() {
        setupBackgroundNotifications()
    }

    deinit {
        NotificationCenter.default.removeObserver(self)
    }

    // MARK: - Public API

    /// Starts timing for the given question.
    func startTracking(questionId: Int) {
        currentQuestionId = questionId
        currentQuestionStartTime = Date()
    }

    /// Records elapsed time for the current question and stops active tracking.
    func recordCurrent() {
        guard let startTime = currentQuestionStartTime,
              let questionId = currentQuestionId else { return }
        let elapsed = Int(Date().timeIntervalSince(startTime))
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
        guard let startTime = currentQuestionStartTime,
              let questionId = currentQuestionId else { return }
        let elapsed = Int(Date().timeIntervalSince(startTime))
        questionTimeSpent[questionId, default: 0] += elapsed
        currentQuestionStartTime = nil
        // Keep currentQuestionId so foreground handler knows to resume
        #if DEBUG
            print("[TIMING] Time tracking paused - app backgrounded")
        #endif
    }

    @objc private func handleAppDidBecomeActive() {
        guard currentQuestionId != nil else { return }
        currentQuestionStartTime = Date()
        #if DEBUG
            print("[TIMING] Time tracking resumed - app foregrounded")
        #endif
    }
}
