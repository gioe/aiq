import SwiftUI

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
///     items: viewModel.testHistory,
///     shouldClear: viewModel.dateFilter != .all || viewModel.sortOrder != .newestFirst
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

    init(
        viewId: String,
        items: [Item],
        shouldClear: Bool,
        storage: ScrollPositionStorageProtocol = ScrollPositionStorage.shared
    ) {
        self.viewId = viewId
        self.items = items
        self.shouldClear = shouldClear
        self.storage = storage
    }

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

    /// Restore scroll position on view appear
    private func restoreScrollPosition() {
        guard let savedPosition = storage.getPosition(forView: viewId) else {
            #if DEBUG
                print("📜 No saved scroll position for \(viewId)")
            #endif
            return
        }

        // Use saved item ID if available and item still exists in list
        guard let itemId = savedPosition.itemId else { return }
        guard items.contains(where: { $0.id == itemId }) else { return }

        scrollPosition = itemId
        #if DEBUG
            print("📜 Restored scroll position for \(viewId): itemId=\(itemId)")
        #endif
    }

    /// Handle scroll position changes (save with debouncing)
    private func handleScrollPositionChange(oldValue: Item.ID?, newValue: Item.ID?) {
        // Only save if position actually changed and we have a valid item
        guard oldValue != newValue,
              let itemId = newValue,
              items.contains(where: { $0.id == itemId })
        else {
            return
        }

        let position = ScrollPositionData(itemId: itemId)
        storage.savePosition(position, forView: viewId)
    }

    /// Clear scroll position when filters/sort change
    private func clearScrollPosition() {
        scrollPosition = nil
        storage.clearPosition(forView: viewId)
        #if DEBUG
            print("📜 Cleared scroll position for \(viewId)")
        #endif
    }
}

/// Extension to make scroll position persistence easy to apply
extension View {
    /// Apply scroll position persistence to a ScrollView
    ///
    /// - Parameters:
    ///   - viewId: Unique identifier for this view (use same ID across app launches)
    ///   - items: Array of items being displayed (must have Int ID)
    ///   - shouldClear: When true, clears saved position (e.g., when filters change)
    /// - Returns: Modified view with scroll position persistence
    ///
    /// Note: Only available on iOS 17+. On iOS 16, this is a no-op (acceptable per requirements)
    @ViewBuilder
    func scrollPositionPersistence<Item: Identifiable>(
        viewId: String,
        items: [Item],
        shouldClear: Bool = false
    ) -> some View where Item.ID == Int {
        if #available(iOS 17.0, *) {
            modifier(ScrollPositionPersistenceModifier(
                viewId: viewId,
                items: items,
                shouldClear: shouldClear
            ))
        } else {
            // iOS 16: No persistence (graceful degradation per requirements)
            self
        }
    }
}
