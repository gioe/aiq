import Combine
import Foundation

/// Base protocol for all ViewModels in the app
protocol ViewModelProtocol: ObservableObject {
    /// Indicates whether the ViewModel is currently loading data
    var isLoading: Bool { get set }

    /// Stores any error that occurred during operations
    var error: Error? { get set }

    /// Called when the view appears
    func onAppear()

    /// Called when the view disappears
    func onDisappear()
}

// Default implementations
extension ViewModelProtocol {
    func onAppear() {}
    func onDisappear() {}
}
