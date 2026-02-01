@testable import AIQ
import XCTest

final class PrivacyConsentStorageTests: XCTestCase {
    var sut: PrivacyConsentStorage!
    var mockUserDefaults: UserDefaults!

    override func setUp() {
        super.setUp()
        // Use a separate suite name for testing to avoid polluting production data
        mockUserDefaults = UserDefaults(suiteName: "com.aiq.tests.PrivacyConsentStorageTests")!
        mockUserDefaults.removePersistentDomain(forName: "com.aiq.tests.PrivacyConsentStorageTests")
        sut = PrivacyConsentStorage(userDefaults: mockUserDefaults)
    }

    override func tearDown() {
        mockUserDefaults.removePersistentDomain(forName: "com.aiq.tests.PrivacyConsentStorageTests")
        super.tearDown()
    }

    // MARK: - hasAcceptedConsent Tests

    func testHasAcceptedConsent_InitialState_ReturnsFalse() {
        // When
        let hasAccepted = sut.hasAcceptedConsent()

        // Then
        XCTAssertFalse(hasAccepted)
    }

    func testHasAcceptedConsent_AfterSaving_ReturnsTrue() {
        // Given
        sut.saveConsent()

        // When
        let hasAccepted = sut.hasAcceptedConsent()

        // Then
        XCTAssertTrue(hasAccepted)
    }

    func testHasAcceptedConsent_AfterClearing_ReturnsFalse() {
        // Given
        sut.saveConsent()
        XCTAssertTrue(sut.hasAcceptedConsent())

        // When
        sut.clearConsent()

        // Then
        XCTAssertFalse(sut.hasAcceptedConsent())
    }

    // MARK: - getConsentTimestamp Tests

    func testGetConsentTimestamp_InitialState_ReturnsNil() {
        // When
        let timestamp = sut.getConsentTimestamp()

        // Then
        XCTAssertNil(timestamp)
    }

    func testGetConsentTimestamp_AfterSaving_ReturnsValidDate() {
        // Given
        let beforeSave = Date()
        sut.saveConsent()
        let afterSave = Date()

        // When
        let timestamp = sut.getConsentTimestamp()

        // Then
        XCTAssertNotNil(timestamp)
        if let timestamp {
            XCTAssertGreaterThanOrEqual(timestamp, beforeSave)
            XCTAssertLessThanOrEqual(timestamp, afterSave)
        }
    }

    func testGetConsentTimestamp_AfterClearing_ReturnsNil() {
        // Given
        sut.saveConsent()
        XCTAssertNotNil(sut.getConsentTimestamp())

        // When
        sut.clearConsent()
        let timestamp = sut.getConsentTimestamp()

        // Then
        XCTAssertNil(timestamp)
    }

    // MARK: - saveConsent Tests

    func testSaveConsent_SetsConsentFlagToTrue() {
        // When
        sut.saveConsent()

        // Then
        let hasAccepted = sut.hasAcceptedConsent()
        XCTAssertTrue(hasAccepted)
    }

    func testSaveConsent_SetsTimestamp() {
        // When
        sut.saveConsent()

        // Then
        let timestamp = sut.getConsentTimestamp()
        XCTAssertNotNil(timestamp)
    }

    func testSaveConsent_CalledMultipleTimes_UpdatesTimestamp() {
        // Given
        sut.saveConsent()
        let firstTimestamp = sut.getConsentTimestamp()

        // Wait a tiny bit to ensure timestamps differ
        Thread.sleep(forTimeInterval: 0.01)

        // When
        sut.saveConsent()
        let secondTimestamp = sut.getConsentTimestamp()

        // Then
        XCTAssertNotNil(firstTimestamp)
        XCTAssertNotNil(secondTimestamp)
        if let first = firstTimestamp, let second = secondTimestamp {
            XCTAssertGreaterThan(second, first)
        }
    }

    func testSaveConsent_PersistsAcrossInstances() {
        // Given
        sut.saveConsent()

        // When - Create new instance with same UserDefaults
        let newStorage = PrivacyConsentStorage(userDefaults: mockUserDefaults)

        // Then
        XCTAssertTrue(newStorage.hasAcceptedConsent())
        XCTAssertNotNil(newStorage.getConsentTimestamp())
    }

    // MARK: - clearConsent Tests

    func testClearConsent_RemovesConsentFlag() {
        // Given
        sut.saveConsent()
        XCTAssertTrue(sut.hasAcceptedConsent())

        // When
        sut.clearConsent()

        // Then
        XCTAssertFalse(sut.hasAcceptedConsent())
    }

    func testClearConsent_RemovesTimestamp() {
        // Given
        sut.saveConsent()
        XCTAssertNotNil(sut.getConsentTimestamp())

        // When
        sut.clearConsent()

        // Then
        XCTAssertNil(sut.getConsentTimestamp())
    }

    func testClearConsent_CalledWhenNoConsent_DoesNotCrash() {
        // When/Then - Should not throw or crash
        sut.clearConsent()

        // Verify state is still clean
        XCTAssertFalse(sut.hasAcceptedConsent())
        XCTAssertNil(sut.getConsentTimestamp())
    }

    func testClearConsent_CalledMultipleTimes_DoesNotCrash() {
        // Given
        sut.saveConsent()

        // When/Then - Should not throw or crash
        sut.clearConsent()
        sut.clearConsent()
        sut.clearConsent()

        // Verify final state
        XCTAssertFalse(sut.hasAcceptedConsent())
        XCTAssertNil(sut.getConsentTimestamp())
    }

    // MARK: - UserDefaults Key Tests

    func testSaveConsent_UsesCorrectKey() {
        // When
        sut.saveConsent()

        // Then - Verify the value is stored under the correct key
        let storedValue = mockUserDefaults.bool(forKey: "com.aiq.privacyConsentAccepted")
        XCTAssertTrue(storedValue)
    }

    func testSaveConsent_TimestampUsesCorrectKey() {
        // When
        sut.saveConsent()

        // Then - Verify the timestamp is stored under the correct key
        let storedTimestamp = mockUserDefaults.object(forKey: "com.aiq.privacyConsentTimestamp") as? Date
        XCTAssertNotNil(storedTimestamp)
    }

    func testClearConsent_RemovesCorrectKeys() {
        // Given
        sut.saveConsent()

        // When
        sut.clearConsent()

        // Then - Verify both keys are removed
        let consentValue = mockUserDefaults.object(forKey: "com.aiq.privacyConsentAccepted")
        let timestampValue = mockUserDefaults.object(forKey: "com.aiq.privacyConsentTimestamp")

        XCTAssertNil(consentValue)
        XCTAssertNil(timestampValue)
    }

    // MARK: - Edge Cases

    func testSaveConsent_Timestamp_IsAccurate() {
        // Given
        let beforeSave = Date().timeIntervalSince1970

        // When
        sut.saveConsent()

        // Then
        let afterSave = Date().timeIntervalSince1970
        let timestamp = sut.getConsentTimestamp()

        XCTAssertNotNil(timestamp)
        if let timestamp {
            let timestampInterval = timestamp.timeIntervalSince1970
            XCTAssertGreaterThanOrEqual(timestampInterval, beforeSave)
            XCTAssertLessThanOrEqual(timestampInterval, afterSave)
        }
    }

    func testSaveConsent_OverwritesPreviousConsent() {
        // Given - Save first consent
        sut.saveConsent()
        let firstTimestamp = sut.getConsentTimestamp()

        // Ensure time passes
        Thread.sleep(forTimeInterval: 0.01)

        // When - Save again
        sut.saveConsent()
        let secondTimestamp = sut.getConsentTimestamp()

        // Then - Should have different timestamps
        XCTAssertNotNil(firstTimestamp)
        XCTAssertNotNil(secondTimestamp)
        XCTAssertNotEqual(firstTimestamp, secondTimestamp)
        XCTAssertTrue(sut.hasAcceptedConsent())
    }

    // MARK: - Protocol Conformance Tests

    func testConformsToPrivacyConsentStorageProtocol() {
        // When/Then - Verify protocol conformance
        let protocolInstance: PrivacyConsentStorageProtocol = sut

        // Test all protocol methods work
        XCTAssertFalse(protocolInstance.hasAcceptedConsent())

        protocolInstance.saveConsent()
        XCTAssertTrue(protocolInstance.hasAcceptedConsent())
        XCTAssertNotNil(protocolInstance.getConsentTimestamp())

        protocolInstance.clearConsent()
        XCTAssertFalse(protocolInstance.hasAcceptedConsent())
        XCTAssertNil(protocolInstance.getConsentTimestamp())
    }

    // MARK: - Shared Instance Tests

    func testSharedInstance_IsAccessible() {
        // When/Then - Verify shared instance exists
        let sharedInstance = PrivacyConsentStorage.shared

        XCTAssertNotNil(sharedInstance)
    }

    func testSharedInstance_UsesDifferentUserDefaultsThanTestInstance() {
        // Given - Save via shared instance (uses standard UserDefaults)
        PrivacyConsentStorage.shared.saveConsent()

        // When - Check test instance (uses test suite)
        let hasAccepted = sut.hasAcceptedConsent()

        // Then - Test instance should not see shared instance's data
        XCTAssertFalse(hasAccepted) // Different UserDefaults suite
    }

    // MARK: - Concurrent Access Tests

    func testSaveConsent_ConcurrentCalls_HandlesCorrectly() {
        // Given
        let expectation = expectation(description: "All saves complete")
        expectation.expectedFulfillmentCount = 10

        // When - Make multiple concurrent saves
        for _ in 0 ..< 10 {
            DispatchQueue.global().async {
                self.sut.saveConsent()
                expectation.fulfill()
            }
        }

        // Then
        wait(for: [expectation], timeout: 5.0)

        // Verify final state is valid
        XCTAssertTrue(sut.hasAcceptedConsent())
        XCTAssertNotNil(sut.getConsentTimestamp())
    }

    func testClearConsent_ConcurrentCalls_HandlesCorrectly() {
        // Given
        sut.saveConsent()
        let expectation = expectation(description: "All clears complete")
        expectation.expectedFulfillmentCount = 10

        // When - Make multiple concurrent clears
        for _ in 0 ..< 10 {
            DispatchQueue.global().async {
                self.sut.clearConsent()
                expectation.fulfill()
            }
        }

        // Then
        wait(for: [expectation], timeout: 5.0)

        // Verify final state is valid
        XCTAssertFalse(sut.hasAcceptedConsent())
        XCTAssertNil(sut.getConsentTimestamp())
    }

    // MARK: - State Consistency Tests

    func testStateConsistency_SaveClearSaveCycle() {
        // Given/When/Then - Cycle through states multiple times
        for i in 0 ..< 5 {
            // Save
            sut.saveConsent()
            XCTAssertTrue(sut.hasAcceptedConsent(), "Iteration \(i): Should be true after save")
            XCTAssertNotNil(sut.getConsentTimestamp(), "Iteration \(i): Should have timestamp after save")

            // Clear
            sut.clearConsent()
            XCTAssertFalse(sut.hasAcceptedConsent(), "Iteration \(i): Should be false after clear")
            XCTAssertNil(sut.getConsentTimestamp(), "Iteration \(i): Should not have timestamp after clear")
        }
    }

    func testStateConsistency_IndependentInstances() {
        // Given - Create two instances with same UserDefaults
        let storage1 = PrivacyConsentStorage(userDefaults: mockUserDefaults)
        let storage2 = PrivacyConsentStorage(userDefaults: mockUserDefaults)

        // When - Save with first instance
        storage1.saveConsent()

        // Then - Both should see the same state
        XCTAssertTrue(storage1.hasAcceptedConsent())
        XCTAssertTrue(storage2.hasAcceptedConsent())

        // When - Clear with second instance
        storage2.clearConsent()

        // Then - Both should see the cleared state
        XCTAssertFalse(storage1.hasAcceptedConsent())
        XCTAssertFalse(storage2.hasAcceptedConsent())
    }
}
