import Foundation

#if DEBUG

    /// Mock local answer storage for UI tests
    ///
    /// This mock provides in-memory storage for test progress during UI tests,
    /// avoiding UserDefaults side effects.
    final class UITestMockLocalAnswerStorage: LocalAnswerStorageProtocol {
        private var savedProgress: SavedTestProgress?
        private let lock = NSLock()

        init() {}

        func saveProgress(_ progress: SavedTestProgress) throws {
            lock.lock()
            defer { lock.unlock() }
            savedProgress = progress
        }

        func loadProgress() -> SavedTestProgress? {
            lock.lock()
            defer { lock.unlock() }
            guard let progress = savedProgress, progress.isValid else {
                return nil
            }
            return progress
        }

        func clearProgress() {
            lock.lock()
            defer { lock.unlock() }
            savedProgress = nil
        }

        func hasProgress() -> Bool {
            loadProgress() != nil
        }

        /// Pre-seed storage for specific UI test scenarios
        func configureForScenario(_ scenario: MockScenario) {
            switch scenario {
            case .timerExpiredZeroAnswers:
                // Expired session with 0 answers — isTimeExpired = true, isValid = true, no answers
                savedProgress = SavedTestProgress(
                    sessionId: 98,
                    userId: 1,
                    questionIds: [1, 2, 3, 4, 5],
                    userAnswers: [:],
                    currentQuestionIndex: 0,
                    savedAt: Date(),
                    sessionStartedAt: Date().addingTimeInterval(-Double(TestTimerManager.totalTimeSeconds + 60)),
                    stimulusSeen: []
                )
            case .timerExpiredWithAnswers:
                // Near-expired session (2 sec remaining) with 1 pre-seeded answer.
                // sessionId = 97 matches nearExpiredSession in UITestMockData.
                // mergeSavedProgress in resumeActiveSession merges these answers before the
                // timer fires, so answeredCount > 0 when handleTimerExpiration is called.
                savedProgress = SavedTestProgress(
                    sessionId: 97,
                    userId: 1,
                    questionIds: [1, 2, 3, 4, 5],
                    userAnswers: [1: "Carrot"],
                    currentQuestionIndex: 1,
                    savedAt: Date(),
                    sessionStartedAt: Date().addingTimeInterval(-Double(TestTimerManager.totalTimeSeconds - 2)),
                    stimulusSeen: []
                )
            default:
                break
            }
        }
    }

#endif
