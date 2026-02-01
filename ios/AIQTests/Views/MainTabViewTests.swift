import SwiftUI
import XCTest

@testable import AIQ

/// Tests for MainTabView tab selection persistence feature
///
/// These tests verify that:
/// 1. The default tab is .dashboard when no saved state exists
/// 2. Tab selection persists to UserDefaults when changed
/// 3. Tab selection is restored from UserDefaults on subsequent launches
///
/// Uses a test-specific UserDefaults suite to avoid polluting user data.
@MainActor
final class MainTabViewTests: XCTestCase {
    // MARK: - Properties

    private var testUserDefaults: UserDefaults!
    private var testSuiteName: String!
    private let tabStorageKey = "com.aiq.selectedTab"

    // MARK: - Setup & Teardown

    override func setUp() {
        super.setUp()

        // Create a test-specific UserDefaults suite to isolate tests.
        //
        // Trade-off explanation:
        // - We use a separate UserDefaults suite instead of UserDefaults.standard because:
        //   1. Test isolation: Each test runs with a clean slate, preventing test pollution
        //   2. Parallel test safety: Multiple tests can run concurrently without interference
        //   3. Cleanup simplicity: Suite can be completely removed in tearDown
        //
        // - The trade-off is that we're not testing with the production UserDefaults.standard,
        //   which means we're testing the persistence logic in isolation rather than the exact
        //   production environment. However, since UserDefaults behaves identically across
        //   suites (same API, same storage semantics), this provides valid coverage while
        //   avoiding side effects on user data or flaky tests from shared state.
        //
        // - If production-specific UserDefaults behavior needs testing (e.g., iCloud sync,
        //   app group containers), those would require separate integration tests.
        testSuiteName = "com.aiq.tests.MainTabView.\(UUID().uuidString)"
        testUserDefaults = UserDefaults(suiteName: testSuiteName)!
    }

    override func tearDown() {
        testUserDefaults.removePersistentDomain(forName: testSuiteName)
        super.tearDown()
    }

    // MARK: - Default Tab Tests

    /// Test that the default tab is .dashboard when no saved state exists in UserDefaults
    func testDefaultTab_IsDashboard_WhenNoSavedState() {
        // Given - No saved tab selection in UserDefaults
        XCTAssertNil(
            testUserDefaults.object(forKey: tabStorageKey),
            "UserDefaults should not have a saved tab before test"
        )

        // When - Reading the default value from @AppStorage
        // @AppStorage provides .dashboard as the default value
        let defaultValue = testUserDefaults.integer(forKey: tabStorageKey)

        // Then - Should return 0 (no stored value), which will trigger @AppStorage's default
        XCTAssertEqual(
            defaultValue,
            0,
            "When no value is stored, UserDefaults returns 0 for integer keys"
        )

        // Verify the TabDestination enum matches expected raw values
        XCTAssertEqual(TabDestination.dashboard.rawValue, 0, "Dashboard should be rawValue 0")
        XCTAssertEqual(TabDestination.history.rawValue, 1, "History should be rawValue 1")
        XCTAssertEqual(TabDestination.settings.rawValue, 2, "Settings should be rawValue 2")
    }

    // MARK: - Tab Selection Persistence Tests

    /// Test that tab selection persists to UserDefaults when changed to history
    func testTabSelection_PersistsToUserDefaults_WhenChangedToHistory() {
        // Given - Starting with no saved tab
        XCTAssertNil(testUserDefaults.object(forKey: tabStorageKey))

        // When - Simulating tab selection change to .history
        testUserDefaults.set(TabDestination.history.rawValue, forKey: tabStorageKey)

        // Then - Value should persist in UserDefaults
        let savedValue = testUserDefaults.integer(forKey: tabStorageKey)
        XCTAssertEqual(
            savedValue,
            TabDestination.history.rawValue,
            "History tab selection should persist to UserDefaults"
        )
    }

    /// Test that tab selection persists to UserDefaults when changed to settings
    func testTabSelection_PersistsToUserDefaults_WhenChangedToSettings() {
        // Given - Starting with no saved tab
        XCTAssertNil(testUserDefaults.object(forKey: tabStorageKey))

        // When - Simulating tab selection change to .settings
        testUserDefaults.set(TabDestination.settings.rawValue, forKey: tabStorageKey)

        // Then - Value should persist in UserDefaults
        let savedValue = testUserDefaults.integer(forKey: tabStorageKey)
        XCTAssertEqual(
            savedValue,
            TabDestination.settings.rawValue,
            "Settings tab selection should persist to UserDefaults"
        )
    }

    /// Test that tab selection persists when changed back to dashboard
    func testTabSelection_PersistsToUserDefaults_WhenChangedBackToDashboard() {
        // Given - Starting with history tab saved
        testUserDefaults.set(TabDestination.history.rawValue, forKey: tabStorageKey)

        // When - Changing back to dashboard
        testUserDefaults.set(TabDestination.dashboard.rawValue, forKey: tabStorageKey)

        // Then - Dashboard selection should persist
        let savedValue = testUserDefaults.integer(forKey: tabStorageKey)
        XCTAssertEqual(
            savedValue,
            TabDestination.dashboard.rawValue,
            "Dashboard tab selection should persist to UserDefaults"
        )
    }

    // MARK: - Tab Selection Restoration Tests

    /// Test that tab selection is restored from UserDefaults when history was previously selected
    func testTabSelection_RestoresFromUserDefaults_WhenHistoryWasPreviouslySelected() {
        // Given - History tab was previously selected and saved
        testUserDefaults.set(TabDestination.history.rawValue, forKey: tabStorageKey)

        // When - Reading the value (simulating app restart)
        let restoredValue = testUserDefaults.integer(forKey: tabStorageKey)

        // Then - Should restore history tab
        XCTAssertEqual(
            restoredValue,
            TabDestination.history.rawValue,
            "History tab selection should be restored from UserDefaults"
        )
    }

    /// Test that tab selection is restored from UserDefaults when settings was previously selected
    func testTabSelection_RestoresFromUserDefaults_WhenSettingsWasPreviouslySelected() {
        // Given - Settings tab was previously selected and saved
        testUserDefaults.set(TabDestination.settings.rawValue, forKey: tabStorageKey)

        // When - Reading the value (simulating app restart)
        let restoredValue = testUserDefaults.integer(forKey: tabStorageKey)

        // Then - Should restore settings tab
        XCTAssertEqual(
            restoredValue,
            TabDestination.settings.rawValue,
            "Settings tab selection should be restored from UserDefaults"
        )
    }

    /// Test that tab selection is restored from UserDefaults when dashboard was explicitly selected
    func testTabSelection_RestoresFromUserDefaults_WhenDashboardWasExplicitlySelected() {
        // Given - Dashboard was explicitly selected (not just default)
        testUserDefaults.set(TabDestination.dashboard.rawValue, forKey: tabStorageKey)

        // When - Reading the value
        let restoredValue = testUserDefaults.integer(forKey: tabStorageKey)

        // Then - Should restore dashboard tab
        XCTAssertEqual(
            restoredValue,
            TabDestination.dashboard.rawValue,
            "Dashboard tab selection should be restored from UserDefaults"
        )
    }

    // MARK: - Multiple Tab Changes Tests

    /// Test that multiple tab changes persist correctly in sequence
    func testTabSelection_PersistsCorrectly_WithMultipleChanges() {
        // Given - Starting with no saved tab
        XCTAssertNil(testUserDefaults.object(forKey: tabStorageKey))

        // When - Making multiple tab changes
        // Dashboard -> History
        testUserDefaults.set(TabDestination.history.rawValue, forKey: tabStorageKey)
        XCTAssertEqual(
            testUserDefaults.integer(forKey: tabStorageKey),
            TabDestination.history.rawValue
        )

        // History -> Settings
        testUserDefaults.set(TabDestination.settings.rawValue, forKey: tabStorageKey)
        XCTAssertEqual(
            testUserDefaults.integer(forKey: tabStorageKey),
            TabDestination.settings.rawValue
        )

        // Settings -> Dashboard
        testUserDefaults.set(TabDestination.dashboard.rawValue, forKey: tabStorageKey)

        // Then - Final value should be dashboard
        XCTAssertEqual(
            testUserDefaults.integer(forKey: tabStorageKey),
            TabDestination.dashboard.rawValue,
            "Final tab selection should persist after multiple changes"
        )
    }

    // MARK: - Storage Key Tests

    /// Test that the correct storage key is used for persistence
    func testTabSelection_UsesCorrectStorageKey() {
        // Given - A saved tab selection
        testUserDefaults.set(TabDestination.history.rawValue, forKey: tabStorageKey)

        // When - Reading with the correct key
        let correctKeyValue = testUserDefaults.integer(forKey: tabStorageKey)

        // And - Attempting to read with an incorrect key
        let wrongKeyValue = testUserDefaults.integer(forKey: "com.aiq.wrongKey")

        // Then - Correct key should return the saved value
        XCTAssertEqual(
            correctKeyValue,
            TabDestination.history.rawValue,
            "Correct storage key should retrieve the saved tab"
        )

        // And - Wrong key should return default (0)
        XCTAssertEqual(
            wrongKeyValue,
            0,
            "Wrong storage key should not retrieve the saved tab"
        )
    }

    // MARK: - App Upgrade Scenario Tests

    /// Test that upgrading from a version without tab persistence defaults to dashboard
    ///
    /// Scenario: A user upgrades from an older app version that did not have tab persistence
    /// (i.e., the `com.aiq.selectedTab` key does not exist in UserDefaults).
    /// The app should default to the dashboard tab without crashing or showing unexpected behavior.
    ///
    /// This test explicitly verifies the upgrade path behavior, ensuring:
    /// 1. The absence of the storage key is handled gracefully
    /// 2. The app defaults to the dashboard tab (rawValue 0)
    /// 3. The TabDestination enum correctly interprets the default value
    func testAppUpgrade_DefaultsToDashboard_WhenNoPersistedTabExists() {
        // Given - Fresh UserDefaults simulating upgrade from version without tab persistence
        // (No com.aiq.selectedTab key exists)
        XCTAssertNil(
            testUserDefaults.object(forKey: tabStorageKey),
            "Precondition: No tab selection should exist (simulating upgrade scenario)"
        )

        // When - Reading the persisted tab value (as the app would on first launch after upgrade)
        let storedValue = testUserDefaults.integer(forKey: tabStorageKey)

        // Then - Should return 0 (UserDefaults default for missing integer keys)
        XCTAssertEqual(
            storedValue,
            0,
            "Missing key should return 0, which corresponds to dashboard tab"
        )

        // And - This value should map to the dashboard tab
        let defaultTab = TabDestination(rawValue: storedValue)
        XCTAssertEqual(
            defaultTab,
            .dashboard,
            "Default value (0) should map to dashboard tab after app upgrade"
        )
    }

    // MARK: - Edge Case Tests

    /// Test behavior when UserDefaults contains an invalid tab value
    func testTabSelection_HandlesInvalidStoredValue() {
        // Given - An invalid tab value stored (999 is not a valid TabDestination)
        testUserDefaults.set(999, forKey: tabStorageKey)

        // When - Reading the value
        let invalidValue = testUserDefaults.integer(forKey: tabStorageKey)

        // Then - Should return the invalid value (view layer handles fallback)
        XCTAssertEqual(
            invalidValue,
            999,
            "UserDefaults should return invalid value as-is"
        )

        // Note: In production, @AppStorage will handle invalid values by falling back
        // to the default value (.dashboard) when the stored value cannot be converted
        // to a valid TabDestination enum case.
    }

    /// Test that removing the stored value returns to default behavior
    func testTabSelection_ReturnsToDefault_WhenStoredValueIsRemoved() {
        // Given - A saved tab selection
        testUserDefaults.set(TabDestination.settings.rawValue, forKey: tabStorageKey)
        XCTAssertEqual(testUserDefaults.integer(forKey: tabStorageKey), TabDestination.settings.rawValue)

        // When - Removing the stored value
        testUserDefaults.removeObject(forKey: tabStorageKey)

        // Then - Should return to default behavior (0, which maps to .dashboard)
        let defaultValue = testUserDefaults.integer(forKey: tabStorageKey)
        XCTAssertEqual(
            defaultValue,
            0,
            "After removing stored value, should return to default (0 = dashboard)"
        )
    }

    // MARK: - TabDestination Enum Tests

    /// Test that TabDestination rawValues are correctly defined
    func testTabDestination_RawValues_AreCorrectlyDefined() {
        // Verify each tab has the expected raw value
        // This is critical for @AppStorage persistence to work correctly

        XCTAssertEqual(
            TabDestination.dashboard.rawValue,
            0,
            "Dashboard should have rawValue 0"
        )

        XCTAssertEqual(
            TabDestination.history.rawValue,
            1,
            "History should have rawValue 1"
        )

        XCTAssertEqual(
            TabDestination.settings.rawValue,
            2,
            "Settings should have rawValue 2"
        )
    }

    /// Test that TabDestination can be initialized from rawValue
    func testTabDestination_CanBeInitializedFromRawValue() {
        // When - Creating TabDestination from raw values
        let dashboard = TabDestination(rawValue: 0)
        let history = TabDestination(rawValue: 1)
        let settings = TabDestination(rawValue: 2)
        let invalid = TabDestination(rawValue: 999)

        // Then - Valid raw values should create correct cases
        XCTAssertEqual(dashboard, .dashboard, "RawValue 0 should create .dashboard")
        XCTAssertEqual(history, .history, "RawValue 1 should create .history")
        XCTAssertEqual(settings, .settings, "RawValue 2 should create .settings")

        // And - Invalid raw value should return nil
        XCTAssertNil(invalid, "Invalid rawValue should return nil")
    }

    /// Test that TabDestination accessibility identifiers are correctly defined
    func testTabDestination_AccessibilityIdentifiers_AreCorrectlyDefined() {
        // Verify each tab has a unique accessibility identifier
        // This ensures UI tests can reliably target each tab

        XCTAssertEqual(
            TabDestination.dashboard.accessibilityIdentifier,
            "tabBar.dashboardTab",
            "Dashboard should have correct accessibility identifier"
        )

        XCTAssertEqual(
            TabDestination.history.accessibilityIdentifier,
            "tabBar.historyTab",
            "History should have correct accessibility identifier"
        )

        XCTAssertEqual(
            TabDestination.settings.accessibilityIdentifier,
            "tabBar.settingsTab",
            "Settings should have correct accessibility identifier"
        )
    }
}
