import Foundation

/// Abstraction over wall-clock time, enabling deterministic testing.
protocol TimeProvider {
    var now: Date { get }
}

/// Production time provider backed by the system clock.
struct SystemTimeProvider: TimeProvider {
    var now: Date {
        Date()
    }
}
