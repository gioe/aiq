import Foundation
import UIKit

/// Protocol abstracting UIApplication for testability
/// This allows injecting a mock application in tests to avoid
/// triggering real system calls like registerForRemoteNotifications
@MainActor
protocol ApplicationProtocol {
    /// Register for remote notifications
    func registerForRemoteNotifications()
}

/// Extend UIApplication to conform to our protocol
/// This allows using the real implementation in production
extension UIApplication: ApplicationProtocol {}
