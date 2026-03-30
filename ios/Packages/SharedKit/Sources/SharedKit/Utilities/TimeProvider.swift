import Foundation

/// Abstraction over wall-clock time, enabling deterministic testing.
public protocol TimeProvider {
    var now: Date { get }
}

/// Production time provider backed by the system clock.
public struct SystemTimeProvider: TimeProvider {
    public init() {}

    public var now: Date {
        Date()
    }
}
