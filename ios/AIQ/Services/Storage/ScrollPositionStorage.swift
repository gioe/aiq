import AIQSharedKit
import Combine
import Foundation

// ScrollPositionStorageProtocol and ScrollPositionData are now defined in AIQSharedKit.
// This file re-exports the types and provides the AIQ-specific implementation.

/// Service for persisting scroll positions across app launches
///
/// This service provides thread-safe scroll position storage with debouncing
/// to prevent excessive writes to UserDefaults. It supports both iOS 17+
/// ID-based scrolling and iOS 16 offset-based fallback.
///
/// Lifecycle:
/// - Subjects and cancellables are created per-view and persist for the app lifetime
/// - No automatic cleanup is performed (acceptable for small number of scrollable views)
/// - Each view maintains independent debouncing state
///
/// Thread Safety: Uses a serial DispatchQueue for thread-safe access to internal state
class ScrollPositionStorage: AIQSharedKit.ScrollPositionStorageProtocol {
    static let shared = ScrollPositionStorage()

    private let appStateStorage: AppStateStorageProtocol

    /// Debounce time interval (0.5 seconds)
    private let debounceInterval: TimeInterval = 0.5

    /// Per-view subjects for independent debouncing
    private var viewSubjects: [String: PassthroughSubject<AIQSharedKit.ScrollPositionData, Never>] = [:]

    /// Per-view cancellables for debounced saves
    private var viewCancellables: [String: AnyCancellable] = [:]

    /// Serial queue for thread-safe access to subjects
    private let queue = DispatchQueue(label: "com.aiq.scrollPositionStorage")

    init(appStateStorage: AppStateStorageProtocol = AppStateStorage.shared) {
        self.appStateStorage = appStateStorage
    }

    // MARK: - Public Methods

    /// Save scroll position for a view (debounced)
    func savePosition(_ position: AIQSharedKit.ScrollPositionData, forView viewId: String) {
        queue.async { [weak self] in
            guard let self else { return }

            let subject: PassthroughSubject<AIQSharedKit.ScrollPositionData, Never>
            if let existingSubject = viewSubjects[viewId] {
                subject = existingSubject
            } else {
                let newSubject = PassthroughSubject<AIQSharedKit.ScrollPositionData, Never>()
                viewSubjects[viewId] = newSubject
                setupDebouncing(for: viewId, subject: newSubject)
                subject = newSubject
            }

            subject.send(position)
        }
    }

    /// Retrieve scroll position for a view
    func getPosition(forView viewId: String) -> AIQSharedKit.ScrollPositionData? {
        let key = storageKey(for: viewId)
        return appStateStorage.getValue(forKey: key, as: AIQSharedKit.ScrollPositionData.self)
    }

    /// Clear scroll position for a view
    func clearPosition(forView viewId: String) {
        let key = storageKey(for: viewId)
        appStateStorage.removeValue(forKey: key)
    }

    // MARK: - Private Methods

    private func setupDebouncing(
        for viewId: String,
        subject: PassthroughSubject<AIQSharedKit.ScrollPositionData, Never>
    ) {
        let cancellable = subject
            .debounce(for: .seconds(debounceInterval), scheduler: DispatchQueue.main)
            .sink { [weak self] position in
                self?.performSave(position, forView: viewId)
            }

        viewCancellables[viewId] = cancellable
    }

    private func performSave(_ position: AIQSharedKit.ScrollPositionData, forView viewId: String) {
        let key = storageKey(for: viewId)
        appStateStorage.setValue(position, forKey: key)

        #if DebugBuild
            let itemStr = position.itemId?.description ?? "nil"
            let offsetStr = position.offsetY?.description ?? "nil"
            print("Saved scroll position for \(viewId): itemId=\(itemStr), offsetY=\(offsetStr)")
        #endif
    }

    private func storageKey(for viewId: String) -> String {
        "com.aiq.scrollPosition.\(viewId)"
    }
}
