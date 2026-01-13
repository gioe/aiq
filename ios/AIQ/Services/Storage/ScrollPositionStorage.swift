import Combine
import Foundation

/// Protocol for scroll position storage operations
protocol ScrollPositionStorageProtocol {
    /// Save scroll position for a view
    /// - Parameters:
    ///   - position: The scroll position data to store
    ///   - viewId: Unique identifier for the view
    func savePosition(_ position: ScrollPositionData, forView viewId: String)

    /// Retrieve scroll position for a view
    /// - Parameter viewId: Unique identifier for the view
    /// - Returns: The stored scroll position, or nil if not found
    func getPosition(forView viewId: String) -> ScrollPositionData?

    /// Clear scroll position for a view
    /// - Parameter viewId: Unique identifier for the view
    func clearPosition(forView viewId: String)
}

/// Data structure representing scroll position
struct ScrollPositionData: Codable, Equatable {
    /// Test result ID at the top of the viewport (for iOS 17+ ID-based scrolling)
    let itemId: Int?

    /// CGPoint offset (for iOS 16 fallback)
    let offsetY: Double?

    /// Timestamp when position was saved
    let timestamp: Date

    init(itemId: Int? = nil, offsetY: Double? = nil) {
        self.itemId = itemId
        self.offsetY = offsetY
        timestamp = Date()
    }
}

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
/// Usage:
/// ```swift
/// let storage = ScrollPositionStorage.shared
///
/// // Save position (debounced automatically)
/// storage.savePosition(ScrollPositionData(itemId: 123), forView: "historyView")
///
/// // Retrieve position
/// if let position = storage.getPosition(forView: "historyView") {
///     // Restore scroll position
/// }
/// ```
///
/// Thread Safety: Uses a serial DispatchQueue for thread-safe access to internal state
class ScrollPositionStorage: ScrollPositionStorageProtocol {
    static let shared = ScrollPositionStorage()

    private let appStateStorage: AppStateStorageProtocol

    /// Debounce time interval (0.5 seconds)
    private let debounceInterval: TimeInterval = 0.5

    /// Per-view subjects for independent debouncing
    private var viewSubjects: [String: PassthroughSubject<ScrollPositionData, Never>] = [:]

    /// Per-view cancellables for debounced saves
    private var viewCancellables: [String: AnyCancellable] = [:]

    /// Serial queue for thread-safe access to subjects
    private let queue = DispatchQueue(label: "com.aiq.scrollPositionStorage")

    init(appStateStorage: AppStateStorageProtocol = AppStateStorage.shared) {
        self.appStateStorage = appStateStorage
    }

    // MARK: - Public Methods

    /// Save scroll position for a view (debounced)
    /// - Parameters:
    ///   - position: The scroll position data to store
    ///   - viewId: Unique identifier for the view
    func savePosition(_ position: ScrollPositionData, forView viewId: String) {
        queue.async { [weak self] in
            guard let self else { return }

            // Get or create subject for this view (avoiding closure to prevent retain cycle)
            let subject: PassthroughSubject<ScrollPositionData, Never>
            if let existingSubject = viewSubjects[viewId] {
                subject = existingSubject
            } else {
                let newSubject = PassthroughSubject<ScrollPositionData, Never>()
                viewSubjects[viewId] = newSubject
                setupDebouncing(for: viewId, subject: newSubject)
                subject = newSubject
            }

            subject.send(position)
        }
    }

    /// Retrieve scroll position for a view
    /// - Parameter viewId: Unique identifier for the view
    /// - Returns: The stored scroll position, or nil if not found
    func getPosition(forView viewId: String) -> ScrollPositionData? {
        let key = storageKey(for: viewId)
        return appStateStorage.getValue(forKey: key, as: ScrollPositionData.self)
    }

    /// Clear scroll position for a view
    /// - Parameter viewId: Unique identifier for the view
    func clearPosition(forView viewId: String) {
        let key = storageKey(for: viewId)
        appStateStorage.removeValue(forKey: key)
    }

    // MARK: - Private Methods

    /// Setup debounced save operations for a specific view
    /// Note: Must be called from within queue.async/sync to ensure thread safety
    private func setupDebouncing(for viewId: String, subject: PassthroughSubject<ScrollPositionData, Never>) {
        let cancellable = subject
            .debounce(for: .seconds(debounceInterval), scheduler: DispatchQueue.main)
            .sink { [weak self] position in
                self?.performSave(position, forView: viewId)
            }

        // Store cancellable immediately (we're already on the queue)
        viewCancellables[viewId] = cancellable
    }

    /// Perform the actual save operation (called after debounce)
    private func performSave(_ position: ScrollPositionData, forView viewId: String) {
        let key = storageKey(for: viewId)
        appStateStorage.setValue(position, forKey: key)

        #if DEBUG
            let itemStr = position.itemId?.description ?? "nil"
            let offsetStr = position.offsetY?.description ?? "nil"
            print("📜 Saved scroll position for \(viewId): itemId=\(itemStr), offsetY=\(offsetStr)")
        #endif
    }

    /// Generate storage key for a view
    private func storageKey(for viewId: String) -> String {
        "com.aiq.scrollPosition.\(viewId)"
    }
}
