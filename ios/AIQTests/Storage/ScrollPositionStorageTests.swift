@testable import AIQ
import Combine
import XCTest

final class ScrollPositionStorageTests: XCTestCase {
    var sut: ScrollPositionStorage!
    var mockAppStateStorage: MockAppStateStorage!
    var cancellables: Set<AnyCancellable>!

    override func setUp() {
        super.setUp()
        mockAppStateStorage = MockAppStateStorage()
        sut = ScrollPositionStorage(appStateStorage: mockAppStateStorage)
        cancellables = []
    }

    // MARK: - Save Position Tests

    func testSavePosition_WithItemId_StoresSuccessfully() async {
        // Given
        let position = ScrollPositionData(itemId: 123)
        let viewId = "historyView"

        // When
        sut.savePosition(position, forView: viewId)

        // Wait for debounce (0.5s + buffer)
        try? await Task.sleep(nanoseconds: 600_000_000)

        // Then
        let savedPosition = mockAppStateStorage.getValue(
            forKey: "com.aiq.scrollPosition.\(viewId)",
            as: ScrollPositionData.self
        )
        XCTAssertNotNil(savedPosition)
        XCTAssertEqual(savedPosition?.itemId, 123)
        XCTAssertNil(savedPosition?.offsetY)
    }

    func testSavePosition_WithOffsetY_StoresSuccessfully() async {
        // Given
        let position = ScrollPositionData(offsetY: 500.5)
        let viewId = "helpView"

        // When
        sut.savePosition(position, forView: viewId)

        // Wait for debounce
        try? await Task.sleep(nanoseconds: 600_000_000)

        // Then
        let savedPosition = mockAppStateStorage.getValue(
            forKey: "com.aiq.scrollPosition.\(viewId)",
            as: ScrollPositionData.self
        )
        XCTAssertNotNil(savedPosition)
        XCTAssertNil(savedPosition?.itemId)
        XCTAssertEqual(savedPosition?.offsetY, 500.5)
    }

    func testSavePosition_WithBothValues_StoresSuccessfully() async {
        // Given
        let position = ScrollPositionData(itemId: 456, offsetY: 1000.0)
        let viewId = "testView"

        // When
        sut.savePosition(position, forView: viewId)

        // Wait for debounce
        try? await Task.sleep(nanoseconds: 600_000_000)

        // Then
        let savedPosition = mockAppStateStorage.getValue(
            forKey: "com.aiq.scrollPosition.\(viewId)",
            as: ScrollPositionData.self
        )
        XCTAssertNotNil(savedPosition)
        XCTAssertEqual(savedPosition?.itemId, 456)
        XCTAssertEqual(savedPosition?.offsetY, 1000.0)
    }

    func testSavePosition_DebouncesProperly() async {
        // Given
        let viewId = "historyView"
        let position1 = ScrollPositionData(itemId: 1)
        let position2 = ScrollPositionData(itemId: 2)
        let position3 = ScrollPositionData(itemId: 3)

        // When - Send 3 rapid updates
        sut.savePosition(position1, forView: viewId)
        try? await Task.sleep(nanoseconds: 100_000_000) // 0.1s
        sut.savePosition(position2, forView: viewId)
        try? await Task.sleep(nanoseconds: 100_000_000) // 0.1s
        sut.savePosition(position3, forView: viewId)

        // Wait for debounce to complete
        try? await Task.sleep(nanoseconds: 600_000_000) // 0.6s

        // Then - Only the last position should be saved (debounced)
        let savedPosition = mockAppStateStorage.getValue(
            forKey: "com.aiq.scrollPosition.\(viewId)",
            as: ScrollPositionData.self
        )
        XCTAssertNotNil(savedPosition)
        XCTAssertEqual(savedPosition?.itemId, 3, "Only last position should be saved")
    }

    func testSavePosition_MultipleViews_IndependentDebouncing() async {
        // Given
        let position1 = ScrollPositionData(itemId: 100)
        let position2 = ScrollPositionData(itemId: 200)

        // When - Save for different views
        sut.savePosition(position1, forView: "view1")
        sut.savePosition(position2, forView: "view2")

        // Wait for debounce
        try? await Task.sleep(nanoseconds: 600_000_000)

        // Then - Both positions should be saved
        let saved1 = mockAppStateStorage.getValue(
            forKey: "com.aiq.scrollPosition.view1",
            as: ScrollPositionData.self
        )
        let saved2 = mockAppStateStorage.getValue(
            forKey: "com.aiq.scrollPosition.view2",
            as: ScrollPositionData.self
        )

        XCTAssertEqual(saved1?.itemId, 100)
        XCTAssertEqual(saved2?.itemId, 200)
    }

    // MARK: - Get Position Tests

    func testGetPosition_WhenPositionExists_ReturnsPosition() {
        // Given
        let position = ScrollPositionData(itemId: 789)
        let viewId = "historyView"
        mockAppStateStorage.setValue(position, forKey: "com.aiq.scrollPosition.\(viewId)")

        // When
        let retrieved = sut.getPosition(forView: viewId)

        // Then
        XCTAssertNotNil(retrieved)
        XCTAssertEqual(retrieved?.itemId, 789)
    }

    func testGetPosition_WhenPositionDoesNotExist_ReturnsNil() {
        // Given
        let viewId = "nonexistentView"

        // When
        let retrieved = sut.getPosition(forView: viewId)

        // Then
        XCTAssertNil(retrieved)
    }

    func testGetPosition_AfterSaveWithDebounce_ReturnsPosition() async {
        // Given
        let position = ScrollPositionData(itemId: 999)
        let viewId = "testView"

        // When
        sut.savePosition(position, forView: viewId)
        try? await Task.sleep(nanoseconds: 600_000_000) // Wait for debounce

        // Then
        let retrieved = sut.getPosition(forView: viewId)
        XCTAssertNotNil(retrieved)
        XCTAssertEqual(retrieved?.itemId, 999)
    }

    // MARK: - Clear Position Tests

    func testClearPosition_RemovesStoredPosition() {
        // Given
        let position = ScrollPositionData(itemId: 123)
        let viewId = "historyView"
        mockAppStateStorage.setValue(position, forKey: "com.aiq.scrollPosition.\(viewId)")

        // When
        sut.clearPosition(forView: viewId)

        // Then
        let retrieved = sut.getPosition(forView: viewId)
        XCTAssertNil(retrieved)
    }

    func testClearPosition_WhenPositionDoesNotExist_DoesNotCrash() {
        // Given
        let viewId = "nonexistentView"

        // When/Then - Should not crash
        sut.clearPosition(forView: viewId)
    }

    func testClearPosition_OnFilterChange_ClearsPosition() async {
        // Given - Simulate filter change scenario
        let position = ScrollPositionData(itemId: 456)
        let viewId = "historyView"
        sut.savePosition(position, forView: viewId)
        try? await Task.sleep(nanoseconds: 600_000_000) // Wait for debounce

        // When - Filters change (should clear position)
        sut.clearPosition(forView: viewId)

        // Then
        let retrieved = sut.getPosition(forView: viewId)
        XCTAssertNil(retrieved, "Position should be cleared when filters change")
    }

    // MARK: - Protocol Conformance Tests

    func testConformsToScrollPositionStorageProtocol() async {
        // Given
        let protocolInstance: ScrollPositionStorageProtocol = sut
        let position = ScrollPositionData(itemId: 111)
        let viewId = "protocolTest"

        // When
        protocolInstance.savePosition(position, forView: viewId)
        try? await Task.sleep(nanoseconds: 600_000_000)

        // Then
        let retrieved = protocolInstance.getPosition(forView: viewId)
        XCTAssertNotNil(retrieved)
        XCTAssertEqual(retrieved?.itemId, 111)

        protocolInstance.clearPosition(forView: viewId)
        XCTAssertNil(protocolInstance.getPosition(forView: viewId))
    }

    // MARK: - Shared Instance Tests

    func testSharedInstance_IsAccessible() {
        // When/Then
        let sharedInstance = ScrollPositionStorage.shared
        XCTAssertNotNil(sharedInstance)
    }

    // MARK: - Edge Cases

    func testEdgeCase_NilValues_HandledGracefully() async {
        // Given
        let position = ScrollPositionData(itemId: nil, offsetY: nil)
        let viewId = "edgeCase"

        // When
        sut.savePosition(position, forView: viewId)
        try? await Task.sleep(nanoseconds: 600_000_000)

        // Then
        let retrieved = sut.getPosition(forView: viewId)
        XCTAssertNotNil(retrieved, "Position should be saved even with nil values")
        XCTAssertNil(retrieved?.itemId)
        XCTAssertNil(retrieved?.offsetY)
    }

    func testEdgeCase_VeryLargeItemId() async {
        // Given
        let position = ScrollPositionData(itemId: Int.max)
        let viewId = "largeId"

        // When
        sut.savePosition(position, forView: viewId)
        // Wait longer to account for queue.async + debounce
        try? await Task.sleep(nanoseconds: 700_000_000)

        // Then
        let retrieved = sut.getPosition(forView: viewId)
        XCTAssertEqual(retrieved?.itemId, Int.max)
    }

    func testEdgeCase_VeryLargeOffsetY() async {
        // Given
        let position = ScrollPositionData(offsetY: Double.greatestFiniteMagnitude / 2)
        let viewId = "largeOffset"

        // When
        sut.savePosition(position, forView: viewId)
        try? await Task.sleep(nanoseconds: 600_000_000)

        // Then
        let retrieved = sut.getPosition(forView: viewId)
        XCTAssertNotNil(retrieved?.offsetY)
    }

    func testEdgeCase_NegativeOffsetY() async {
        // Given
        let position = ScrollPositionData(offsetY: -100.0)
        let viewId = "negativeOffset"

        // When
        sut.savePosition(position, forView: viewId)
        try? await Task.sleep(nanoseconds: 600_000_000)

        // Then
        let retrieved = sut.getPosition(forView: viewId)
        XCTAssertEqual(retrieved?.offsetY, -100.0)
    }

    func testEdgeCase_SpecialCharactersInViewId() async {
        // Given
        let position = ScrollPositionData(itemId: 123)
        let viewIds = [
            "view-with-dashes",
            "view_with_underscores",
            "view.with.dots",
            "ViewWithCaps"
        ]

        // When/Then
        for viewId in viewIds {
            sut.savePosition(position, forView: viewId)
            try? await Task.sleep(nanoseconds: 600_000_000)

            let retrieved = sut.getPosition(forView: viewId)
            XCTAssertNotNil(retrieved, "Failed for viewId: \(viewId)")
            XCTAssertEqual(retrieved?.itemId, 123)

            sut.clearPosition(forView: viewId)
        }
    }

    // MARK: - Real World Scenarios

    func testRealWorldScenario_HistoryViewScrollPersistence() async {
        // Given - User scrolls to item 42 in history
        let position = ScrollPositionData(itemId: 42)
        let viewId = "historyView"

        // When - Save scroll position
        sut.savePosition(position, forView: viewId)
        try? await Task.sleep(nanoseconds: 600_000_000)

        // Then - Position is persisted
        let retrieved = sut.getPosition(forView: viewId)
        XCTAssertEqual(retrieved?.itemId, 42)

        // When - App restarts (simulated)
        let newStorage = ScrollPositionStorage(appStateStorage: mockAppStateStorage)
        let restored = newStorage.getPosition(forView: viewId)

        // Then - Position is restored
        XCTAssertEqual(restored?.itemId, 42)
    }

    func testRealWorldScenario_FilterChange_ClearsPosition() async {
        // Given - User has scrolled in history
        let position = ScrollPositionData(itemId: 100)
        let viewId = "historyView"
        sut.savePosition(position, forView: viewId)
        try? await Task.sleep(nanoseconds: 600_000_000)

        XCTAssertNotNil(sut.getPosition(forView: viewId))

        // When - User changes filter (should clear position)
        sut.clearPosition(forView: viewId)

        // Then - Position is cleared
        XCTAssertNil(sut.getPosition(forView: viewId))
    }

    func testRealWorldScenario_MultipleScrollPositions() async {
        // Given - User has scrolled in multiple views
        let historyPosition = ScrollPositionData(itemId: 50)
        let helpPosition = ScrollPositionData(offsetY: 300.0)

        // When
        sut.savePosition(historyPosition, forView: "historyView")
        sut.savePosition(helpPosition, forView: "helpView")
        try? await Task.sleep(nanoseconds: 600_000_000)

        // Then - Both positions are persisted independently
        let retrievedHistory = sut.getPosition(forView: "historyView")
        let retrievedHelp = sut.getPosition(forView: "helpView")

        XCTAssertEqual(retrievedHistory?.itemId, 50)
        XCTAssertEqual(retrievedHelp?.offsetY, 300.0)
    }

    func testRealWorldScenario_InvalidItemId_Restoration() {
        // Given - Position saved with item that no longer exists
        let position = ScrollPositionData(itemId: 999_999)
        let viewId = "historyView"
        mockAppStateStorage.setValue(position, forKey: "com.aiq.scrollPosition.\(viewId)")

        // When
        let retrieved = sut.getPosition(forView: viewId)

        // Then - Position is retrieved (validation happens in View layer)
        XCTAssertNotNil(retrieved)
        XCTAssertEqual(retrieved?.itemId, 999_999)
        // Note: The ScrollPositionModifier will validate if item exists in list
    }

    func testRealWorldScenario_RapidScrolling_OnlyLastPositionSaved() async {
        // Given - User rapidly scrolls through items
        let viewId = "historyView"

        // When - Rapid scroll events (like user quickly scrolling)
        for itemId in 1 ... 20 {
            sut.savePosition(ScrollPositionData(itemId: itemId), forView: viewId)
            try? await Task.sleep(nanoseconds: 10_000_000) // 0.01s between scrolls
        }

        // Wait for debounce to complete
        try? await Task.sleep(nanoseconds: 600_000_000)

        // Then - Only last position is saved (prevents excessive writes)
        let retrieved = sut.getPosition(forView: viewId)
        XCTAssertEqual(retrieved?.itemId, 20, "Should only save last position after debounce")
    }
}

// MARK: - Mock AppStateStorage

/// Mock implementation of AppStateStorageProtocol for testing
class MockAppStateStorage: AppStateStorageProtocol {
    private var storage: [String: Any] = [:]
    private let queue = DispatchQueue(label: "com.aiq.tests.mockAppStateStorage")

    func setValue(_ value: some Encodable, forKey key: String) {
        queue.sync {
            // For simple types
            if let stringValue = value as? String {
                storage[key] = stringValue
            } else if let intValue = value as? Int {
                storage[key] = intValue
            } else if let boolValue = value as? Bool {
                storage[key] = boolValue
            } else if let doubleValue = value as? Double {
                storage[key] = doubleValue
            } else if let dataValue = value as? Data {
                storage[key] = dataValue
            } else {
                // For complex types, encode to JSON
                if let encoded = try? JSONEncoder().encode(value) {
                    storage[key] = encoded
                }
            }
        }
    }

    func getValue<T: Decodable>(forKey key: String, as type: T.Type) -> T? {
        queue.sync {
            guard let value = storage[key] else { return nil }

            // For simple types
            if type == String.self {
                return value as? T
            } else if type == Int.self {
                return value as? T
            } else if type == Bool.self {
                return value as? T
            } else if type == Double.self {
                return value as? T
            } else if type == Data.self {
                return value as? T
            } else {
                // For complex types, decode from JSON
                guard let data = value as? Data else { return nil }
                return try? JSONDecoder().decode(type, from: data)
            }
        }
    }

    func removeValue(forKey key: String) {
        queue.sync {
            storage.removeValue(forKey: key)
        }
    }

    func hasValue(forKey key: String) -> Bool {
        queue.sync {
            storage[key] != nil
        }
    }
}
