@testable import AIQ
import AIQSharedKit
import Foundation

final class MockTimeProvider: TimeProvider {
    var now: Date

    init(startDate: Date = Date(timeIntervalSinceReferenceDate: 0)) {
        now = startDate
    }

    func advance(by seconds: TimeInterval) {
        now = now.addingTimeInterval(seconds)
    }
}
