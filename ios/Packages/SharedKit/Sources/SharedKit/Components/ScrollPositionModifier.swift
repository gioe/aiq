import Combine
import SwiftUI

/// Protocol for scroll position storage operations
public protocol ScrollPositionStorageProtocol {
    /// Save scroll position for a view
    func savePosition(_ position: ScrollPositionData, forView viewId: String)

    /// Retrieve scroll position for a view
    func getPosition(forView viewId: String) -> ScrollPositionData?

    /// Clear scroll position for a view
    func clearPosition(forView viewId: String)
}

/// Data structure representing scroll position
public struct ScrollPositionData: Codable, Equatable {
    /// Item ID at the top of the viewport (for iOS 17+ ID-based scrolling)
    public let itemId: Int?

    /// CGPoint offset (for iOS 16 fallback)
    public let offsetY: Double?

    /// Timestamp when position was saved
    public let timestamp: Date

    public init(itemId: Int? = nil, offsetY: Double? = nil) {
        self.itemId = itemId
        self.offsetY = offsetY
        timestamp = Date()
    }
}

/// ViewModifier for persisting scroll positions across app launches
///
/// This modifier provides automatic scroll position persistence with support for:
/// - iOS 17+: ID-based scrolling using ScrollPosition API
/// - iOS 16: Graceful degradation (no persistence, acceptable per requirements)
///
/// Usage:
/// ```swift
/// ScrollView {
///     LazyVStack {
///         ForEach(items) { item in
///             ItemView(item: item)
///         }
///     }
/// }
/// .scrollPositionPersistence(
///     viewId: "historyView",
///     items: viewModel.items,
///     shouldClear: viewModel.filterActive,
///     storage: myStorage
/// )
/// ```
///
/// Thread Safety: Safe to use from main thread (ViewModifiers run on MainActor)
@available(iOS 17.0, *)
private struct ScrollPositionPersistenceModifier<Item: Identifiable>: ViewModifier where Item.ID == Int {
    let viewId: String
    let items: [Item]
    let shouldClear: Bool
    let storage: ScrollPositionStorageProtocol

    @State private var scrollPosition: Item.ID?

    func body(content: Content) -> some View {
        content
            .scrollPosition(id: $scrollPosition)
            .onAppear {
                restoreScrollPosition()
            }
            .onChange(of: scrollPosition) { oldValue, newValue in
                handleScrollPositionChange(oldValue: oldValue, newValue: newValue)
            }
            .onChange(of: shouldClear) { _, newValue in
                if newValue {
                    clearScrollPosition()
                }
            }
    }

    // MARK: - Private Methods

    private func restoreScrollPosition() {
        guard let savedPosition = storage.getPosition(forView: viewId) else {
            #if DEBUG
                print("No saved scroll position for \(viewId)")
            #endif
            return
        }

        guard let itemId = savedPosition.itemId else { return }
        guard items.contains(where: { $0.id == itemId }) else { return }

        scrollPosition = itemId
        #if DEBUG
            print("Restored scroll position for \(viewId): itemId=\(itemId)")
        #endif
    }

    private func handleScrollPositionChange(oldValue: Item.ID?, newValue: Item.ID?) {
        guard oldValue != newValue,
              let itemId = newValue,
              items.contains(where: { $0.id == itemId })
        else {
            return
        }

        let position = ScrollPositionData(itemId: itemId)
        storage.savePosition(position, forView: viewId)
    }

    private func clearScrollPosition() {
        scrollPosition = nil
        storage.clearPosition(forView: viewId)
        #if DEBUG
            print("Cleared scroll position for \(viewId)")
        #endif
    }
}

/// Extension to make scroll position persistence easy to apply
public extension View {
    /// Apply scroll position persistence to a ScrollView
    ///
    /// - Parameters:
    ///   - viewId: Unique identifier for this view (use same ID across app launches)
    ///   - items: Array of items being displayed (must have Int ID)
    ///   - shouldClear: When true, clears saved position (e.g., when filters change)
    ///   - storage: The storage backend for persisting scroll positions
    /// - Returns: Modified view with scroll position persistence
    ///
    /// Note: Only available on iOS 17+. On iOS 16, this is a no-op (acceptable per requirements)
    @ViewBuilder
    func scrollPositionPersistence<Item: Identifiable>(
        viewId: String,
        items: [Item],
        shouldClear: Bool = false,
        storage: ScrollPositionStorageProtocol
    ) -> some View where Item.ID == Int {
        if #available(iOS 17.0, *) {
            modifier(ScrollPositionPersistenceModifier(
                viewId: viewId,
                items: items,
                shouldClear: shouldClear,
                storage: storage
            ))
        } else {
            // iOS 16: No persistence (graceful degradation per requirements)
            self
        }
    }
}
