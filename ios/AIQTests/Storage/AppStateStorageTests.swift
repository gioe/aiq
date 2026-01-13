@testable import AIQ
import XCTest

final class AppStateStorageTests: XCTestCase {
    var sut: AppStateStorage!
    var testUserDefaults: UserDefaults!
    let testSuiteName = "com.aiq.tests.appStateStorage"

    override func setUp() {
        super.setUp()

        // Create test-specific UserDefaults suite to avoid interfering with production data
        testUserDefaults = UserDefaults(suiteName: testSuiteName)!
        testUserDefaults.removePersistentDomain(forName: testSuiteName)
        sut = AppStateStorage(userDefaults: testUserDefaults)
    }

    override func tearDown() {
        // Clean up test data
        testUserDefaults.removePersistentDomain(forName: testSuiteName)
        sut = nil
        testUserDefaults = nil
        super.tearDown()
    }

    // MARK: - String Storage Tests

    func testSetValue_String_StoresSuccessfully() {
        // Given
        let key = "com.aiq.testString"
        let value = "Hello, World!"

        // When
        sut.setValue(value, forKey: key)

        // Then
        let retrieved = sut.getValue(forKey: key, as: String.self)
        XCTAssertEqual(retrieved, value)
    }

    func testGetValue_String_ReturnsNilWhenNotFound() {
        // Given
        let key = "com.aiq.nonexistentString"

        // When
        let retrieved = sut.getValue(forKey: key, as: String.self)

        // Then
        XCTAssertNil(retrieved)
    }

    func testSetValue_String_OverwritesExistingValue() {
        // Given
        let key = "com.aiq.testString"
        sut.setValue("First", forKey: key)

        // When
        sut.setValue("Second", forKey: key)

        // Then
        let retrieved = sut.getValue(forKey: key, as: String.self)
        XCTAssertEqual(retrieved, "Second")
    }

    func testSetValue_String_WithSpecialCharacters() {
        // Given
        let key = "com.aiq.specialString"
        let value = "Test!@#$%^&*(){}[]|\\:;\"'<>,.?/~` 世界 🌍"

        // When
        sut.setValue(value, forKey: key)

        // Then
        let retrieved = sut.getValue(forKey: key, as: String.self)
        XCTAssertEqual(retrieved, value)
    }

    func testSetValue_String_EmptyString() {
        // Given
        let key = "com.aiq.emptyString"
        let value = ""

        // When
        sut.setValue(value, forKey: key)

        // Then
        let retrieved = sut.getValue(forKey: key, as: String.self)
        XCTAssertEqual(retrieved, value)
    }

    // MARK: - Int Storage Tests

    func testSetValue_Int_StoresSuccessfully() {
        // Given
        let key = "com.aiq.testInt"
        let value = 42

        // When
        sut.setValue(value, forKey: key)

        // Then
        let retrieved = sut.getValue(forKey: key, as: Int.self)
        XCTAssertEqual(retrieved, value)
    }

    func testGetValue_Int_ReturnsNilWhenNotFound() {
        // Given
        let key = "com.aiq.nonexistentInt"

        // When
        let retrieved = sut.getValue(forKey: key, as: Int.self)

        // Then
        XCTAssertNil(retrieved)
    }

    func testSetValue_Int_Zero() {
        // Given
        let key = "com.aiq.zeroInt"
        let value = 0

        // When
        sut.setValue(value, forKey: key)

        // Then
        let retrieved = sut.getValue(forKey: key, as: Int.self)
        XCTAssertEqual(retrieved, value)
    }

    func testSetValue_Int_NegativeValue() {
        // Given
        let key = "com.aiq.negativeInt"
        let value = -100

        // When
        sut.setValue(value, forKey: key)

        // Then
        let retrieved = sut.getValue(forKey: key, as: Int.self)
        XCTAssertEqual(retrieved, value)
    }

    func testSetValue_Int_MaxValue() {
        // Given
        let key = "com.aiq.maxInt"
        let value = Int.max

        // When
        sut.setValue(value, forKey: key)

        // Then
        let retrieved = sut.getValue(forKey: key, as: Int.self)
        XCTAssertEqual(retrieved, value)
    }

    // MARK: - Bool Storage Tests

    func testSetValue_Bool_True() {
        // Given
        let key = "com.aiq.trueFlag"
        let value = true

        // When
        sut.setValue(value, forKey: key)

        // Then
        let retrieved = sut.getValue(forKey: key, as: Bool.self)
        XCTAssertEqual(retrieved, value)
    }

    func testSetValue_Bool_False() {
        // Given
        let key = "com.aiq.falseFlag"
        let value = false

        // When
        sut.setValue(value, forKey: key)

        // Then
        let retrieved = sut.getValue(forKey: key, as: Bool.self)
        XCTAssertEqual(retrieved, value)
    }

    func testGetValue_Bool_ReturnsNilWhenNotFound() {
        // Given
        let key = "com.aiq.nonexistentBool"

        // When
        let retrieved = sut.getValue(forKey: key, as: Bool.self)

        // Then
        XCTAssertNil(retrieved)
    }

    func testSetValue_Bool_ToggleValue() {
        // Given
        let key = "com.aiq.toggleFlag"
        sut.setValue(true, forKey: key)

        // When
        sut.setValue(false, forKey: key)

        // Then
        let retrieved = sut.getValue(forKey: key, as: Bool.self)
        XCTAssertEqual(retrieved, false)
    }

    // MARK: - Double Storage Tests

    func testSetValue_Double_StoresSuccessfully() {
        // Given
        let key = "com.aiq.testDouble"
        let value = 3.14159

        // When
        sut.setValue(value, forKey: key)

        // Then
        let retrieved = sut.getValue(forKey: key, as: Double.self)
        XCTAssertNotNil(retrieved)
        if let retrieved {
            XCTAssertEqual(retrieved, value, accuracy: 0.00001)
        }
    }

    func testGetValue_Double_ReturnsNilWhenNotFound() {
        // Given
        let key = "com.aiq.nonexistentDouble"

        // When
        let retrieved = sut.getValue(forKey: key, as: Double.self)

        // Then
        XCTAssertNil(retrieved)
    }

    func testSetValue_Double_Zero() {
        // Given
        let key = "com.aiq.zeroDouble"
        let value = 0.0

        // When
        sut.setValue(value, forKey: key)

        // Then
        let retrieved = sut.getValue(forKey: key, as: Double.self)
        XCTAssertEqual(retrieved, value)
    }

    func testSetValue_Double_NegativeValue() {
        // Given
        let key = "com.aiq.negativeDouble"
        let value = -99.99

        // When
        sut.setValue(value, forKey: key)

        // Then
        let retrieved = sut.getValue(forKey: key, as: Double.self)
        XCTAssertNotNil(retrieved)
        if let retrieved {
            XCTAssertEqual(retrieved, value, accuracy: 0.00001)
        }
    }

    // MARK: - Data Storage Tests

    func testSetValue_Data_StoresSuccessfully() {
        // Given
        let key = "com.aiq.testData"
        let value = "Test Data".data(using: .utf8)!

        // When
        sut.setValue(value, forKey: key)

        // Then
        let retrieved = sut.getValue(forKey: key, as: Data.self)
        XCTAssertEqual(retrieved, value)
    }

    func testGetValue_Data_ReturnsNilWhenNotFound() {
        // Given
        let key = "com.aiq.nonexistentData"

        // When
        let retrieved = sut.getValue(forKey: key, as: Data.self)

        // Then
        XCTAssertNil(retrieved)
    }

    func testSetValue_Data_EmptyData() {
        // Given
        let key = "com.aiq.emptyData"
        let value = Data()

        // When
        sut.setValue(value, forKey: key)

        // Then
        let retrieved = sut.getValue(forKey: key, as: Data.self)
        XCTAssertEqual(retrieved, value)
    }

    func testSetValue_Data_LargeData() {
        // Given
        let key = "com.aiq.largeData"
        let value = Data(repeating: 0xFF, count: 10000)

        // When
        sut.setValue(value, forKey: key)

        // Then
        let retrieved = sut.getValue(forKey: key, as: Data.self)
        XCTAssertEqual(retrieved, value)
    }

    // MARK: - Codable Type Storage Tests

    func testSetValue_CodableStruct_StoresSuccessfully() {
        // Given
        struct TestStruct: Codable, Equatable {
            let name: String
            let age: Int
            let isActive: Bool
        }

        let key = "com.aiq.testStruct"
        let value = TestStruct(name: "John", age: 30, isActive: true)

        // When
        sut.setValue(value, forKey: key)

        // Then
        let retrieved = sut.getValue(forKey: key, as: TestStruct.self)
        XCTAssertEqual(retrieved, value)
    }

    func testSetValue_CodableEnum_StoresSuccessfully() {
        // Given
        enum TestEnum: String, Codable {
            case option1 = "Option 1"
            case option2 = "Option 2"
        }

        let key = "com.aiq.testEnum"
        let value = TestEnum.option1

        // When
        sut.setValue(value, forKey: key)

        // Then
        let retrieved = sut.getValue(forKey: key, as: TestEnum.self)
        XCTAssertEqual(retrieved, value)
    }

    func testSetValue_CodableArray_StoresSuccessfully() {
        // Given
        let key = "com.aiq.testArray"
        let value = ["apple", "banana", "cherry"]

        // When
        sut.setValue(value, forKey: key)

        // Then
        let retrieved = sut.getValue(forKey: key, as: [String].self)
        XCTAssertEqual(retrieved, value)
    }

    func testSetValue_CodableDictionary_StoresSuccessfully() {
        // Given
        let key = "com.aiq.testDictionary"
        let value = ["key1": "value1", "key2": "value2"]

        // When
        sut.setValue(value, forKey: key)

        // Then
        let retrieved = sut.getValue(forKey: key, as: [String: String].self)
        XCTAssertEqual(retrieved, value)
    }

    func testSetValue_NestedCodableStruct_StoresSuccessfully() {
        // Given
        struct Address: Codable, Equatable {
            let street: String
            let city: String
        }

        struct Person: Codable, Equatable {
            let name: String
            let address: Address
        }

        let key = "com.aiq.nestedStruct"
        let value = Person(
            name: "Jane",
            address: Address(street: "123 Main St", city: "Springfield")
        )

        // When
        sut.setValue(value, forKey: key)

        // Then
        let retrieved = sut.getValue(forKey: key, as: Person.self)
        XCTAssertEqual(retrieved, value)
    }

    func testGetValue_CodableType_ReturnsNilWhenNotFound() {
        // Given
        struct TestStruct: Codable {
            let value: String
        }

        let key = "com.aiq.nonexistentCodable"

        // When
        let retrieved = sut.getValue(forKey: key, as: TestStruct.self)

        // Then
        XCTAssertNil(retrieved)
    }

    func testGetValue_CodableType_ReturnsNilForInvalidData() {
        // Given
        struct TestStruct: Codable {
            let name: String
            let age: Int
        }

        let key = "com.aiq.invalidCodable"
        let invalidData = "invalid json".data(using: .utf8)!
        testUserDefaults.set(invalidData, forKey: key)

        // When
        let retrieved = sut.getValue(forKey: key, as: TestStruct.self)

        // Then
        XCTAssertNil(retrieved)
    }

    // MARK: - RemoveValue Tests

    func testRemoveValue_RemovesStoredString() {
        // Given
        let key = "com.aiq.stringToRemove"
        sut.setValue("Test", forKey: key)
        XCTAssertNotNil(sut.getValue(forKey: key, as: String.self))

        // When
        sut.removeValue(forKey: key)

        // Then
        XCTAssertNil(sut.getValue(forKey: key, as: String.self))
    }

    func testRemoveValue_RemovesStoredInt() {
        // Given
        let key = "com.aiq.intToRemove"
        sut.setValue(42, forKey: key)
        XCTAssertNotNil(sut.getValue(forKey: key, as: Int.self))

        // When
        sut.removeValue(forKey: key)

        // Then
        XCTAssertNil(sut.getValue(forKey: key, as: Int.self))
    }

    func testRemoveValue_RemovesStoredBool() {
        // Given
        let key = "com.aiq.boolToRemove"
        sut.setValue(true, forKey: key)
        XCTAssertNotNil(sut.getValue(forKey: key, as: Bool.self))

        // When
        sut.removeValue(forKey: key)

        // Then
        XCTAssertNil(sut.getValue(forKey: key, as: Bool.self))
    }

    func testRemoveValue_RemovesStoredCodable() {
        // Given
        struct TestStruct: Codable {
            let value: String
        }

        let key = "com.aiq.codableToRemove"
        sut.setValue(TestStruct(value: "Test"), forKey: key)
        XCTAssertNotNil(sut.getValue(forKey: key, as: TestStruct.self))

        // When
        sut.removeValue(forKey: key)

        // Then
        XCTAssertNil(sut.getValue(forKey: key, as: TestStruct.self))
    }

    func testRemoveValue_WhenKeyDoesNotExist_DoesNotCrash() {
        // Given
        let key = "com.aiq.nonexistentKey"

        // When/Then - Should not crash
        sut.removeValue(forKey: key)
    }

    func testRemoveValue_CalledMultipleTimes_DoesNotCrash() {
        // Given
        let key = "com.aiq.keyToRemoveMultiple"
        sut.setValue("Test", forKey: key)

        // When/Then - Should not crash
        sut.removeValue(forKey: key)
        sut.removeValue(forKey: key)
        sut.removeValue(forKey: key)
    }

    // MARK: - HasValue Tests

    func testHasValue_ReturnsTrueWhenValueExists() {
        // Given
        let key = "com.aiq.existingValue"
        sut.setValue("Test", forKey: key)

        // When
        let hasValue = sut.hasValue(forKey: key)

        // Then
        XCTAssertTrue(hasValue)
    }

    func testHasValue_ReturnsFalseWhenValueDoesNotExist() {
        // Given
        let key = "com.aiq.nonexistentValue"

        // When
        let hasValue = sut.hasValue(forKey: key)

        // Then
        XCTAssertFalse(hasValue)
    }

    func testHasValue_ReturnsFalseAfterRemoval() {
        // Given
        let key = "com.aiq.removedValue"
        sut.setValue("Test", forKey: key)
        sut.removeValue(forKey: key)

        // When
        let hasValue = sut.hasValue(forKey: key)

        // Then
        XCTAssertFalse(hasValue)
    }

    func testHasValue_ReturnsTrueForInt() {
        // Given
        let key = "com.aiq.intValue"
        sut.setValue(42, forKey: key)

        // When
        let hasValue = sut.hasValue(forKey: key)

        // Then
        XCTAssertTrue(hasValue)
    }

    func testHasValue_ReturnsTrueForBool() {
        // Given
        let key = "com.aiq.boolValue"
        sut.setValue(true, forKey: key)

        // When
        let hasValue = sut.hasValue(forKey: key)

        // Then
        XCTAssertTrue(hasValue)
    }

    func testHasValue_ReturnsTrueForZeroInt() {
        // Given
        let key = "com.aiq.zeroValue"
        sut.setValue(0, forKey: key)

        // When
        let hasValue = sut.hasValue(forKey: key)

        // Then
        XCTAssertTrue(hasValue)
    }

    func testHasValue_ReturnsTrueForFalseBool() {
        // Given
        let key = "com.aiq.falseBool"
        sut.setValue(false, forKey: key)

        // When
        let hasValue = sut.hasValue(forKey: key)

        // Then
        XCTAssertTrue(hasValue)
    }

    // MARK: - Persistence Tests

    func testPersistence_SurvivesInstanceRecreation() {
        // Given
        let key = "com.aiq.persistentValue"
        sut.setValue("Persistent", forKey: key)

        // When - Create a new instance with same UserDefaults suite
        let newInstance = AppStateStorage(userDefaults: testUserDefaults)
        let retrieved = newInstance.getValue(forKey: key, as: String.self)

        // Then
        XCTAssertEqual(retrieved, "Persistent")
    }

    func testPersistence_IsolatedByUserDefaultsSuite() {
        // Given
        let suite1 = UserDefaults(suiteName: "com.aiq.tests.suite1")!
        let suite2 = UserDefaults(suiteName: "com.aiq.tests.suite2")!

        let storage1 = AppStateStorage(userDefaults: suite1)
        let storage2 = AppStateStorage(userDefaults: suite2)

        let key = "com.aiq.isolatedValue"

        // When
        storage1.setValue("Value1", forKey: key)
        storage2.setValue("Value2", forKey: key)

        // Then
        XCTAssertEqual(storage1.getValue(forKey: key, as: String.self), "Value1")
        XCTAssertEqual(storage2.getValue(forKey: key, as: String.self), "Value2")

        // Clean up
        suite1.removePersistentDomain(forName: "com.aiq.tests.suite1")
        suite2.removePersistentDomain(forName: "com.aiq.tests.suite2")
    }

    // MARK: - Protocol Conformance Tests

    func testConformsToAppStateStorageProtocol() {
        // When/Then - Verify protocol conformance
        let protocolInstance: AppStateStorageProtocol = sut

        // Test all protocol methods work
        let key = "com.aiq.protocolTest"

        protocolInstance.setValue("Test", forKey: key)
        XCTAssertEqual(protocolInstance.getValue(forKey: key, as: String.self), "Test")
        XCTAssertTrue(protocolInstance.hasValue(forKey: key))

        protocolInstance.removeValue(forKey: key)
        XCTAssertFalse(protocolInstance.hasValue(forKey: key))
    }

    // MARK: - Shared Instance Tests

    func testSharedInstance_IsAccessible() {
        // When/Then - Verify shared instance exists
        let sharedInstance = AppStateStorage.shared

        XCTAssertNotNil(sharedInstance)
    }

    func testSharedInstance_UsesDifferentUserDefaultsThanTestInstance() {
        // Given - Save via shared instance (uses standard UserDefaults)
        let key = "com.aiq.sharedTest"
        AppStateStorage.shared.setValue("Shared", forKey: key)

        // When - Check test instance (uses test suite)
        let retrieved = sut.getValue(forKey: key, as: String.self)

        // Then - Test instance should not see shared instance's data
        XCTAssertNil(retrieved) // Different UserDefaults suite

        // Clean up
        AppStateStorage.shared.removeValue(forKey: key)
    }

    // MARK: - Concurrent Access Tests

    // VERIFIED: Implementation uses DispatchQueue(label: "com.aiq.appStateStorage")
    // with .sync for all operations, so concurrent tests are valid

    func testConcurrentSetValue_ThreadSafety() {
        // Given
        let iterations = 100
        let expectation = expectation(description: "All sets complete")
        expectation.expectedFulfillmentCount = iterations

        // When - Set concurrently from multiple threads
        for i in 0 ..< iterations {
            DispatchQueue.global().async {
                let key = "com.aiq.concurrent.set.\(i)"
                self.sut.setValue("Value\(i)", forKey: key)
                expectation.fulfill()
            }
        }

        // Then
        wait(for: [expectation], timeout: 10.0)

        // Verify all values were set
        for i in 0 ..< iterations {
            let key = "com.aiq.concurrent.set.\(i)"
            let value = sut.getValue(forKey: key, as: String.self)
            XCTAssertEqual(value, "Value\(i)")
        }
    }

    func testConcurrentGetValue_ThreadSafety() {
        // Given
        let key = "com.aiq.concurrent.get"
        sut.setValue("TestValue", forKey: key)

        let iterations = 100
        let expectation = expectation(description: "All gets complete")
        expectation.expectedFulfillmentCount = iterations

        // When - Get concurrently from multiple threads
        for _ in 0 ..< iterations {
            DispatchQueue.global().async {
                let value = self.sut.getValue(forKey: key, as: String.self)
                XCTAssertEqual(value, "TestValue")
                expectation.fulfill()
            }
        }

        // Then
        wait(for: [expectation], timeout: 10.0)
    }

    func testConcurrentRemoveValue_ThreadSafety() {
        // Given
        let iterations = 100
        let expectation = expectation(description: "All removes complete")
        expectation.expectedFulfillmentCount = iterations

        // Set up values to remove
        for i in 0 ..< iterations {
            let key = "com.aiq.concurrent.remove.\(i)"
            sut.setValue("Value\(i)", forKey: key)
        }

        // When - Remove concurrently from multiple threads
        for i in 0 ..< iterations {
            DispatchQueue.global().async {
                let key = "com.aiq.concurrent.remove.\(i)"
                self.sut.removeValue(forKey: key)
                expectation.fulfill()
            }
        }

        // Then
        wait(for: [expectation], timeout: 10.0)

        // Verify all values were removed
        for i in 0 ..< iterations {
            let key = "com.aiq.concurrent.remove.\(i)"
            XCTAssertFalse(sut.hasValue(forKey: key))
        }
    }

    func testConcurrentMixedOperations_ThreadSafety() {
        // Given
        let iterations = 50
        let expectation = expectation(description: "All operations complete")
        expectation.expectedFulfillmentCount = iterations * 4

        // When - Perform mixed operations concurrently
        for i in 0 ..< iterations {
            let key = "com.aiq.concurrent.mixed.\(i)"

            // Set
            DispatchQueue.global().async {
                self.sut.setValue("Value\(i)", forKey: key)
                expectation.fulfill()
            }

            // Get
            DispatchQueue.global().async {
                _ = self.sut.getValue(forKey: key, as: String.self)
                expectation.fulfill()
            }

            // HasValue
            DispatchQueue.global().async {
                _ = self.sut.hasValue(forKey: key)
                expectation.fulfill()
            }

            // Remove
            DispatchQueue.global().async {
                self.sut.removeValue(forKey: key)
                expectation.fulfill()
            }
        }

        // Then
        wait(for: [expectation], timeout: 10.0)
    }

    // MARK: - Edge Cases

    func testEdgeCase_MultipleTypesForSameKey() {
        // Given
        let key = "com.aiq.multiType"

        // When - Store different types for the same key (overwriting)
        sut.setValue("String", forKey: key)
        let stringValue = sut.getValue(forKey: key, as: String.self)

        sut.setValue(42, forKey: key)
        let intValue = sut.getValue(forKey: key, as: Int.self)

        // Then
        XCTAssertEqual(stringValue, "String")
        XCTAssertEqual(intValue, 42)
        // Note: UserDefaults has type coercion - reading Int as String returns "42"
        // This is expected UserDefaults behavior, not an error
        XCTAssertEqual(sut.getValue(forKey: key, as: String.self), "42")
    }

    func testEdgeCase_VeryLongKey() {
        // Given
        let longKey = String(repeating: "a", count: 1000)
        let value = "Test"

        // When
        sut.setValue(value, forKey: longKey)

        // Then
        let retrieved = sut.getValue(forKey: longKey, as: String.self)
        XCTAssertEqual(retrieved, value)
    }

    func testEdgeCase_VeryLongStringValue() {
        // Given
        let key = "com.aiq.longString"
        let value = String(repeating: "x", count: 10000)

        // When
        sut.setValue(value, forKey: key)

        // Then
        let retrieved = sut.getValue(forKey: key, as: String.self)
        XCTAssertEqual(retrieved, value)
    }

    func testEdgeCase_KeysWithSpecialCharacters() {
        // Given
        let keys = [
            "com.aiq.test-key",
            "com.aiq.test_key",
            "com.aiq.test.key",
            "com.aiq.test@key",
            "com.aiq.test#key"
        ]

        // When/Then - All keys should work
        for (index, key) in keys.enumerated() {
            sut.setValue("Value\(index)", forKey: key)
            let retrieved = sut.getValue(forKey: key, as: String.self)
            XCTAssertEqual(retrieved, "Value\(index)", "Failed for key: \(key)")
        }
    }

    // MARK: - Real World Scenarios

    func testRealWorldScenario_TabSelection() {
        // Given - Simulating tab selection persistence
        enum TabDestination: String, Codable {
            case dashboard
            case history
            case settings
        }

        let key = "com.aiq.selectedTab"

        // When - User selects history tab
        sut.setValue(TabDestination.history, forKey: key)

        // Then - Tab selection is persisted
        let retrieved = sut.getValue(forKey: key, as: TabDestination.self)
        XCTAssertEqual(retrieved, .history)

        // When - App restarts (simulated with new instance)
        let newInstance = AppStateStorage(userDefaults: testUserDefaults)
        let restoredTab = newInstance.getValue(forKey: key, as: TabDestination.self)

        // Then - Tab selection is restored
        XCTAssertEqual(restoredTab, .history)
    }

    func testRealWorldScenario_FilterPreferences() {
        // Given - Simulating filter preferences
        struct FilterPreferences: Codable, Equatable {
            let sortOrder: String
            let dateFilter: String
            let showCompleted: Bool
        }

        let key = "com.aiq.filterPreferences"
        let preferences = FilterPreferences(
            sortOrder: "newestFirst",
            dateFilter: "lastMonth",
            showCompleted: true
        )

        // When - User changes filters
        sut.setValue(preferences, forKey: key)

        // Then - Preferences are persisted
        let retrieved = sut.getValue(forKey: key, as: FilterPreferences.self)
        XCTAssertEqual(retrieved, preferences)
    }

    func testRealWorldScenario_OnboardingCompletion() {
        // Given
        let key = "com.aiq.hasCompletedOnboarding"

        // When - User completes onboarding
        sut.setValue(true, forKey: key)

        // Then - State is persisted
        let hasCompleted = sut.getValue(forKey: key, as: Bool.self)
        XCTAssertEqual(hasCompleted, true)
    }

    func testRealWorldScenario_ClearingUserData() {
        // Given - User has various preferences stored
        let keys = [
            "com.aiq.selectedTab",
            "com.aiq.filterPreferences",
            "com.aiq.hasCompletedOnboarding",
            "com.aiq.userSettings"
        ]

        for key in keys {
            sut.setValue("Data", forKey: key)
        }

        // When - User logs out (clear all preferences)
        for key in keys {
            sut.removeValue(forKey: key)
        }

        // Then - All preferences are cleared
        for key in keys {
            XCTAssertFalse(sut.hasValue(forKey: key), "Key should be cleared: \(key)")
        }
    }
}
