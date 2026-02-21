@testable import AIQ
import XCTest

/// Unit tests for DataCache actor
///
/// Verifies:
/// - In-memory cache storage and retrieval with type safety
/// - Expiration logic (default 5 minutes, custom durations)
/// - Thread safety via actor isolation
/// - Cache invalidation (single key, expired, all)
/// - Edge cases (special characters, large values, concurrent access)
///
/// Note: Tests use DataCache.shared since the actor is a singleton.
/// Each test calls clearAll() in setUp to ensure isolation.
final class DataCacheTests: XCTestCase {
    var sut: DataCache!

    override func setUp() async throws {
        try await super.setUp()
        sut = DataCache.shared
        await sut.clearAll()
    }

    override func tearDown() async throws {
        await sut.clearAll()
        try await super.tearDown()
    }

    // MARK: - Set Operation Tests

    func testSet_StoresValue() async {
        // Given
        let key = "testKey"
        let value = "testValue"

        // When
        await sut.set(value, forKey: key)

        // Then
        let retrieved: String? = await sut.get(forKey: key)
        XCTAssertEqual(retrieved, value, "Should retrieve stored value")
    }

    func testSet_StoresValueWithCustomExpiration() async {
        // Given
        let key = "testKey"
        let value = "testValue"
        let customExpiration: TimeInterval = 600 // 10 minutes

        // When
        await sut.set(value, forKey: key, expiration: customExpiration)

        // Then
        let retrieved: String? = await sut.get(forKey: key)
        XCTAssertNotNil(retrieved, "Should retrieve value with custom expiration")
        XCTAssertEqual(retrieved, value)
    }

    func testSet_OverwritesExistingValue() async {
        // Given
        let key = "testKey"
        let initialValue = "initialValue"
        let updatedValue = "updatedValue"

        // When
        await sut.set(initialValue, forKey: key)
        await sut.set(updatedValue, forKey: key)

        // Then
        let retrieved: String? = await sut.get(forKey: key)
        XCTAssertEqual(retrieved, updatedValue, "Should overwrite with new value")
    }

    func testSet_StoresDifferentTypesAtSameKey() async {
        // Given
        let key = "testKey"

        // When - Store string first
        await sut.set("stringValue", forKey: key)
        let stringValue: String? = await sut.get(forKey: key)

        // Then
        XCTAssertEqual(stringValue, "stringValue")

        // When - Overwrite with int
        await sut.set(42, forKey: key)
        let intValue: Int? = await sut.get(forKey: key)
        let oldStringValue: String? = await sut.get(forKey: key)

        // Then
        XCTAssertEqual(intValue, 42, "Should store new type")
        XCTAssertNil(oldStringValue, "Should not retrieve old type after overwrite")
    }

    func testSet_StoresComplexTypes() async {
        // Given
        struct TestStruct: Equatable {
            let id: Int
            let name: String
        }

        let key = "structKey"
        let value = TestStruct(id: 1, name: "Test")

        // When
        await sut.set(value, forKey: key)

        // Then
        let retrieved: TestStruct? = await sut.get(forKey: key)
        XCTAssertEqual(retrieved, value, "Should store and retrieve complex types")
    }

    // MARK: - Get Operation Tests

    func testGet_ReturnsNilForNonExistentKey() async {
        // Given
        let key = "nonExistentKey"

        // When
        let retrieved: String? = await sut.get(forKey: key)

        // Then
        XCTAssertNil(retrieved, "Should return nil for non-existent key")
    }

    func testGet_ReturnsNilForTypeMismatch() async {
        // Given
        let key = "testKey"
        await sut.set("stringValue", forKey: key)

        // When
        let retrieved: Int? = await sut.get(forKey: key)

        // Then
        XCTAssertNil(retrieved, "Should return nil for type mismatch")
    }

    func testGet_ReturnsValueBeforeExpiration() async {
        // Given
        let key = "testKey"
        let value = "testValue"
        let expiration: TimeInterval = 1.0 // 1 second

        // When
        await sut.set(value, forKey: key, expiration: expiration)

        // Wait a short time (well within expiration)
        try? await Task.sleep(nanoseconds: 100_000_000) // 0.1 seconds

        let retrieved: String? = await sut.get(forKey: key)

        // Then
        XCTAssertNotNil(retrieved, "Should return value before expiration")
        XCTAssertEqual(retrieved, value)
    }

    func testGet_ReturnsNilForExpiredValue() async {
        // Given
        let key = "testKey"
        let value = "testValue"
        let expiration: TimeInterval = 0.1 // 100ms

        // When
        await sut.set(value, forKey: key, expiration: expiration)

        // Wait for expiration + safe margin (200ms total)
        try? await Task.sleep(nanoseconds: 200_000_000)

        let retrieved: String? = await sut.get(forKey: key)

        // Then
        XCTAssertNil(retrieved, "Should return nil for expired value")
    }

    func testGet_AutomaticallyRemovesExpiredEntry() async {
        // Given
        let key = "testKey"
        let value = "testValue"
        let expiration: TimeInterval = 0.1 // 100ms

        await sut.set(value, forKey: key, expiration: expiration)

        // When - Wait for expiration
        try? await Task.sleep(nanoseconds: 200_000_000) // 200ms

        // First get returns nil and removes entry
        let firstGet: String? = await sut.get(forKey: key)

        // Second get should also return nil (entry was removed)
        let secondGet: String? = await sut.get(forKey: key)

        // Then
        XCTAssertNil(firstGet, "First get should return nil for expired entry")
        XCTAssertNil(secondGet, "Second get should return nil as entry was removed")
    }

    // MARK: - Remove Operation Tests

    func testRemove_RemovesExistingKey() async {
        // Given
        let key = "testKey"
        let value = "testValue"
        await sut.set(value, forKey: key)

        // When
        await sut.remove(forKey: key)

        // Then
        let retrieved: String? = await sut.get(forKey: key)
        XCTAssertNil(retrieved, "Should return nil after removal")
    }

    func testRemove_HandlesNonExistentKey() async {
        // Given
        let key = "nonExistentKey"

        // When/Then - Should not crash
        await sut.remove(forKey: key)

        // Verify no side effects
        let retrieved: String? = await sut.get(forKey: key)
        XCTAssertNil(retrieved)
    }

    func testRemove_OnlyRemovesSpecifiedKey() async {
        // Given
        let key1 = "key1"
        let key2 = "key2"
        await sut.set("value1", forKey: key1)
        await sut.set("value2", forKey: key2)

        // When
        await sut.remove(forKey: key1)

        // Then
        let retrieved1: String? = await sut.get(forKey: key1)
        let retrieved2: String? = await sut.get(forKey: key2)

        XCTAssertNil(retrieved1, "Removed key should return nil")
        XCTAssertNotNil(retrieved2, "Other key should remain")
        XCTAssertEqual(retrieved2, "value2")
    }

    // MARK: - ClearAll Operation Tests

    func testClearAll_RemovesAllEntries() async {
        // Given
        await sut.set("value1", forKey: "key1")
        await sut.set(42, forKey: "key2")
        await sut.set(true, forKey: "key3")

        // When
        await sut.clearAll()

        // Then
        let retrieved1: String? = await sut.get(forKey: "key1")
        let retrieved2: Int? = await sut.get(forKey: "key2")
        let retrieved3: Bool? = await sut.get(forKey: "key3")

        XCTAssertNil(retrieved1, "All entries should be cleared")
        XCTAssertNil(retrieved2, "All entries should be cleared")
        XCTAssertNil(retrieved3, "All entries should be cleared")
    }

    func testClearAll_HandlesEmptyCache() async {
        // Given - empty cache

        // When/Then - Should not crash
        await sut.clearAll()

        // Verify cache is still empty
        let retrieved: String? = await sut.get(forKey: "anyKey")
        XCTAssertNil(retrieved)
    }

    func testClearAll_AfterAlreadyCleared() async {
        // Given
        await sut.set("value", forKey: "key")
        await sut.clearAll()

        // When - Clear again
        await sut.clearAll()

        // Then
        let retrieved: String? = await sut.get(forKey: "key")
        XCTAssertNil(retrieved, "Should handle multiple clears gracefully")
    }

    // MARK: - ClearExpired Operation Tests

    func testClearExpired_RemovesOnlyExpiredEntries() async {
        // Given
        let expiredKey = "expiredKey"
        let validKey = "validKey"
        let shortExpiration: TimeInterval = 0.1 // 100ms
        let longExpiration: TimeInterval = 10.0 // 10 seconds

        await sut.set("expiredValue", forKey: expiredKey, expiration: shortExpiration)
        await sut.set("validValue", forKey: validKey, expiration: longExpiration)

        // When - Wait for short expiration + margin
        try? await Task.sleep(nanoseconds: 200_000_000) // 200ms

        await sut.clearExpired()

        // Then
        let expiredRetrieved: String? = await sut.get(forKey: expiredKey)
        let validRetrieved: String? = await sut.get(forKey: validKey)

        XCTAssertNil(expiredRetrieved, "Expired entry should be removed")
        XCTAssertNotNil(validRetrieved, "Valid entry should remain")
        XCTAssertEqual(validRetrieved, "validValue")
    }

    func testClearExpired_RemovesMultipleExpiredEntries() async {
        // Given
        let expiredKey1 = "expiredKey1"
        let expiredKey2 = "expiredKey2"
        let validKey = "validKey"
        let shortExpiration: TimeInterval = 0.1 // 100ms
        let longExpiration: TimeInterval = 10.0 // 10 seconds

        await sut.set("expired1", forKey: expiredKey1, expiration: shortExpiration)
        await sut.set("expired2", forKey: expiredKey2, expiration: shortExpiration)
        await sut.set("valid", forKey: validKey, expiration: longExpiration)

        // When - Wait for short expiration + margin
        try? await Task.sleep(nanoseconds: 200_000_000) // 200ms

        await sut.clearExpired()

        // Then
        let expired1Retrieved: String? = await sut.get(forKey: expiredKey1)
        let expired2Retrieved: String? = await sut.get(forKey: expiredKey2)
        let validRetrieved: String? = await sut.get(forKey: validKey)

        XCTAssertNil(expired1Retrieved, "First expired entry should be removed")
        XCTAssertNil(expired2Retrieved, "Second expired entry should be removed")
        XCTAssertNotNil(validRetrieved, "Valid entry should remain")
    }

    func testClearExpired_HandlesEmptyCache() async {
        // Given - empty cache

        // When/Then - Should not crash
        await sut.clearExpired()

        // Verify cache is still empty
        let retrieved: String? = await sut.get(forKey: "anyKey")
        XCTAssertNil(retrieved)
    }

    func testClearExpired_HandlesAllValidEntries() async {
        // Given - all entries are valid
        await sut.set("value1", forKey: "key1", expiration: 10.0)
        await sut.set("value2", forKey: "key2", expiration: 10.0)

        // When
        await sut.clearExpired()

        // Then - all entries should remain
        let retrieved1: String? = await sut.get(forKey: "key1")
        let retrieved2: String? = await sut.get(forKey: "key2")

        XCTAssertNotNil(retrieved1, "Valid entries should not be removed")
        XCTAssertNotNil(retrieved2, "Valid entries should not be removed")
    }

    func testClearExpired_UsesDefaultExpiration() async {
        // Given - entry with default expiration (5 minutes)
        let key = "testKey"
        await sut.set("value", forKey: key) // Uses default 300s expiration

        // When - Clear expired immediately (entry is still fresh)
        await sut.clearExpired()

        // Then
        let retrieved: String? = await sut.get(forKey: key)
        XCTAssertNotNil(retrieved, "Entry with default expiration should not be expired yet")
    }

    // MARK: - Expiration Logic Tests

    func testExpiration_DefaultIs5Minutes() async {
        // Given
        let key = "testKey"
        let value = "testValue"

        // When - Set without explicit expiration
        await sut.set(value, forKey: key)

        // Then - Value should be retrievable immediately
        let retrieved: String? = await sut.get(forKey: key)
        XCTAssertNotNil(retrieved, "Value with default expiration should be valid")
        XCTAssertEqual(retrieved, value)

        // Note: We can't wait 5 minutes in tests, so we verify it's set and retrievable
        // The default expiration duration is tested by checking it doesn't expire immediately
    }

    func testExpiration_CustomDuration() async {
        // Given
        let key = "testKey"
        let value = "testValue"
        let customExpiration: TimeInterval = 2.0 // 2 seconds

        // When
        await sut.set(value, forKey: key, expiration: customExpiration)

        // Wait well within expiration (0.5 seconds)
        try? await Task.sleep(nanoseconds: 500_000_000)

        let beforeExpiration: String? = await sut.get(forKey: key)

        // Then
        XCTAssertNotNil(beforeExpiration, "Should be valid before custom expiration")
    }

    func testExpiration_VeryShortDuration() async {
        // Given
        let key = "testKey"
        let value = "testValue"
        let veryShortExpiration: TimeInterval = 0.05 // 50ms

        // When
        await sut.set(value, forKey: key, expiration: veryShortExpiration)

        // Wait for expiration + safe margin (150ms total)
        try? await Task.sleep(nanoseconds: 150_000_000)

        let retrieved: String? = await sut.get(forKey: key)

        // Then
        XCTAssertNil(retrieved, "Should expire after very short duration")
    }

    func testExpiration_ZeroDurationExpiresImmediately() async {
        // Given
        let key = "testKey"
        let value = "testValue"
        let zeroDuration: TimeInterval = 0.0

        // When
        await sut.set(value, forKey: key, expiration: zeroDuration)

        // Even a tiny wait should expire it
        try? await Task.sleep(nanoseconds: 10_000_000) // 10ms

        let retrieved: String? = await sut.get(forKey: key)

        // Then
        XCTAssertNil(retrieved, "Should expire immediately with zero duration")
    }

    // MARK: - Type Safety Tests

    func testTypeSafety_StringType() async {
        // Given
        let key = "stringKey"
        let value = "Hello, World!"

        // When
        await sut.set(value, forKey: key)

        // Then
        let retrieved: String? = await sut.get(forKey: key)
        XCTAssertEqual(retrieved, value, "Should handle String type")
    }

    func testTypeSafety_IntType() async {
        // Given
        let key = "intKey"
        let value = 42

        // When
        await sut.set(value, forKey: key)

        // Then
        let retrieved: Int? = await sut.get(forKey: key)
        XCTAssertEqual(retrieved, value, "Should handle Int type")
    }

    func testTypeSafety_BoolType() async {
        // Given
        let key = "boolKey"
        let value = true

        // When
        await sut.set(value, forKey: key)

        // Then
        let retrieved: Bool? = await sut.get(forKey: key)
        XCTAssertEqual(retrieved, value, "Should handle Bool type")
    }

    func testTypeSafety_ArrayType() async {
        // Given
        let key = "arrayKey"
        let value = [1, 2, 3, 4, 5]

        // When
        await sut.set(value, forKey: key)

        // Then
        let retrieved: [Int]? = await sut.get(forKey: key)
        XCTAssertEqual(retrieved, value, "Should handle Array type")
    }

    func testTypeSafety_DictionaryType() async {
        // Given
        let key = "dictKey"
        let value = ["key1": "value1", "key2": "value2"]

        // When
        await sut.set(value, forKey: key)

        // Then
        let retrieved: [String: String]? = await sut.get(forKey: key)
        XCTAssertEqual(retrieved, value, "Should handle Dictionary type")
    }

    func testTypeSafety_OptionalType() async {
        // Given
        let key = "optionalKey"
        let value: String? = "optionalValue"

        // When
        await sut.set(value, forKey: key)

        // Then
        let retrieved: String?? = await sut.get(forKey: key)
        XCTAssertEqual(retrieved, value, "Should handle Optional type")
    }

    // MARK: - Concurrent Access Tests

    func testConcurrentSet_ThreadSafety() async {
        // Given
        let iterations = 100
        let keys = (0 ..< iterations).map { "key\($0)" }

        // When - Set concurrently from multiple tasks
        await withTaskGroup(of: Void.self) { group in
            for (index, key) in keys.enumerated() {
                group.addTask {
                    await self.sut.set("value\(index)", forKey: key)
                }
            }
        }

        // Then - All values should be stored without corruption
        for (index, key) in keys.enumerated() {
            let retrieved: String? = await sut.get(forKey: key)
            XCTAssertNotNil(retrieved, "Value should be stored for key: \(key)")
            XCTAssertEqual(retrieved, "value\(index)", "Value should match for key: \(key)")
        }
    }

    func testConcurrentGet_ThreadSafety() async {
        // Given
        let key = "sharedKey"
        let value = "sharedValue"
        await sut.set(value, forKey: key)

        let iterations = 100

        // When - Read concurrently from multiple tasks
        await withTaskGroup(of: String?.self) { group in
            for _ in 0 ..< iterations {
                group.addTask {
                    await self.sut.get(forKey: key)
                }
            }

            // Then - All reads should succeed with correct value
            for await retrieved in group {
                XCTAssertNotNil(retrieved, "Should read value concurrently")
                XCTAssertEqual(retrieved, value, "Should read correct value")
            }
        }
    }

    func testConcurrentRemove_ThreadSafety() async {
        // Given
        let iterations = 100
        let keys = (0 ..< iterations).map { "key\($0)" }

        // Pre-populate cache
        for (index, key) in keys.enumerated() {
            await sut.set("value\(index)", forKey: key)
        }

        // When - Remove concurrently from multiple tasks
        await withTaskGroup(of: Void.self) { group in
            for key in keys {
                group.addTask {
                    await self.sut.remove(forKey: key)
                }
            }
        }

        // Then - All keys should be removed
        for key in keys {
            let retrieved: String? = await sut.get(forKey: key)
            XCTAssertNil(retrieved, "All keys should be removed for key: \(key)")
        }
    }

    func testConcurrentMixedOperations_ThreadSafety() async {
        // Given
        let iterations = 50
        let keys = (0 ..< iterations).map { "key\($0)" }

        // When - Perform mixed operations concurrently
        await withTaskGroup(of: Void.self) { group in
            // Set operations
            for (index, key) in keys.enumerated() {
                group.addTask {
                    await self.sut.set("value\(index)", forKey: key)
                }
            }

            // Get operations
            for key in keys {
                group.addTask {
                    let _: String? = await self.sut.get(forKey: key)
                }
            }

            // Remove operations (on half the keys)
            for key in keys.prefix(iterations / 2) {
                group.addTask {
                    await self.sut.remove(forKey: key)
                }
            }

            // Clear expired
            group.addTask {
                await self.sut.clearExpired()
            }
        }

        // Then - Should complete without crashes or deadlocks
        // This test primarily verifies actor isolation prevents data races
    }

    func testConcurrentSetSameKey_ThreadSafety() async {
        // Given
        let key = "sameKey"
        let iterations = 100

        // When - Set the same key concurrently with different values
        await withTaskGroup(of: Void.self) { group in
            for i in 0 ..< iterations {
                group.addTask {
                    await self.sut.set("value\(i)", forKey: key)
                }
            }
        }

        // Then - Should have a value (last write wins)
        let retrieved: String? = await sut.get(forKey: key)
        XCTAssertNotNil(retrieved, "Should have a value after concurrent writes")
        if let retrieved {
            XCTAssertTrue(retrieved.starts(with: "value"), "Should have a valid value")
        }
    }

    func testConcurrentClearAll_ThreadSafety() async {
        // Given
        let iterations = 50

        // Pre-populate cache
        for i in 0 ..< iterations {
            await sut.set("value\(i)", forKey: "key\(i)")
        }

        // When - Clear all concurrently from multiple tasks
        await withTaskGroup(of: Void.self) { group in
            for _ in 0 ..< 10 {
                group.addTask {
                    await self.sut.clearAll()
                }
            }
        }

        // Then - Cache should be empty
        for i in 0 ..< iterations {
            let retrieved: String? = await sut.get(forKey: "key\(i)")
            XCTAssertNil(retrieved, "All entries should be cleared")
        }
    }

    // MARK: - Edge Cases

    func testEdgeCase_EmptyStringKey() async {
        // Given
        let key = ""
        let value = "value"

        // When
        await sut.set(value, forKey: key)

        // Then
        let retrieved: String? = await sut.get(forKey: key)
        XCTAssertEqual(retrieved, value, "Should handle empty string key")
    }

    func testEdgeCase_SpecialCharactersInKey() async {
        // Given
        let keys = [
            "key!@#$%^&*()",
            "key with spaces",
            "key\nwith\nnewlines",
            "key\twith\ttabs",
            "key.with.dots",
            "key/with/slashes",
            "key\\with\\backslashes",
            "unicode_世界_مرحبا_🌍"
        ]

        // When
        for (index, key) in keys.enumerated() {
            await sut.set("value\(index)", forKey: key)
        }

        // Then
        for (index, key) in keys.enumerated() {
            let retrieved: String? = await sut.get(forKey: key)
            XCTAssertEqual(retrieved, "value\(index)", "Should handle special characters in key: \(key)")
        }
    }

    func testEdgeCase_VeryLongKey() async {
        // Given
        let longKey = String(repeating: "A", count: 1000)
        let value = "value"

        // When
        await sut.set(value, forKey: longKey)

        // Then
        let retrieved: String? = await sut.get(forKey: longKey)
        XCTAssertEqual(retrieved, value, "Should handle very long key")
    }

    func testEdgeCase_VeryLargeValue() async {
        // Given
        let key = "largeKey"
        let largeValue = String(repeating: "X", count: 100_000) // 100KB string

        // When
        await sut.set(largeValue, forKey: key)

        // Then
        let retrieved: String? = await sut.get(forKey: key)
        XCTAssertEqual(retrieved, largeValue, "Should handle very large value")
    }

    func testEdgeCase_NilValueInOptional() async {
        // Given
        let key = "nilKey"
        let value: String? = nil

        // When
        await sut.set(value, forKey: key)

        // Then
        let retrieved: String?? = await sut.get(forKey: key)
        XCTAssertNotNil(retrieved, "Should store nil optional value")
        XCTAssertNil(retrieved, "Inner value should be nil")
    }

    func testEdgeCase_NegativeExpiration() async {
        // Given
        let key = "testKey"
        let value = "testValue"
        let negativeExpiration: TimeInterval = -100.0

        // When
        await sut.set(value, forKey: key, expiration: negativeExpiration)

        // Then - Should be expired immediately (negative is already in the past)
        let retrieved: String? = await sut.get(forKey: key)
        XCTAssertNil(retrieved, "Negative expiration should expire immediately")
    }

    func testEdgeCase_VeryLargeExpiration() async {
        // Given
        let key = "testKey"
        let value = "testValue"
        let hugeExpiration: TimeInterval = 999_999_999.0 // ~31 years

        // When
        await sut.set(value, forKey: key, expiration: hugeExpiration)

        // Then
        let retrieved: String? = await sut.get(forKey: key)
        XCTAssertNotNil(retrieved, "Should handle very large expiration")
        XCTAssertEqual(retrieved, value)
    }

    func testEdgeCase_MultipleTypesInCache() async {
        // Given
        let stringKey = "stringKey"
        let intKey = "intKey"
        let boolKey = "boolKey"
        let arrayKey = "arrayKey"

        // When
        await sut.set("stringValue", forKey: stringKey)
        await sut.set(42, forKey: intKey)
        await sut.set(true, forKey: boolKey)
        await sut.set([1, 2, 3], forKey: arrayKey)

        // Then
        let stringValue: String? = await sut.get(forKey: stringKey)
        let intValue: Int? = await sut.get(forKey: intKey)
        let boolValue: Bool? = await sut.get(forKey: boolKey)
        let arrayValue: [Int]? = await sut.get(forKey: arrayKey)

        XCTAssertEqual(stringValue, "stringValue", "Should store multiple types")
        XCTAssertEqual(intValue, 42, "Should store multiple types")
        XCTAssertEqual(boolValue, true, "Should store multiple types")
        XCTAssertEqual(arrayValue, [1, 2, 3], "Should store multiple types")
    }

    // MARK: - Cache Key Constants Tests

    func testCacheKeys_Constants() {
        // Verify key constants are stable for API compatibility
        XCTAssertEqual(DataCache.Key.testHistory, "test_history")
        XCTAssertEqual(DataCache.Key.userProfile, "user_profile")
        XCTAssertEqual(DataCache.Key.dashboardData, "dashboard_data")
        XCTAssertEqual(DataCache.Key.activeTestSession, "active_test_session")
    }

    func testCacheKeys_TestResultKey() {
        // Verify dynamic key generation
        XCTAssertEqual(DataCache.Key.testResult(id: 123), "test_result_123")
        XCTAssertEqual(DataCache.Key.testResult(id: 0), "test_result_0")
        XCTAssertEqual(DataCache.Key.testResult(id: -1), "test_result_-1")
    }

    // MARK: - Integration Tests

    func testRealWorldScenario_CachingAPIResponses() async {
        // Given - Simulating API response caching
        struct TestHistory: Codable, Equatable {
            let results: [Int]
            let count: Int
        }

        let cacheKey = "test_history"
        let apiResponse = TestHistory(results: [1, 2, 3, 4, 5], count: 5)
        let cacheDuration: TimeInterval = 300 // 5 minutes

        // When - Cache API response
        await sut.set(apiResponse, forKey: cacheKey, expiration: cacheDuration)

        // Then - Should retrieve cached response
        let cached: TestHistory? = await sut.get(forKey: cacheKey)
        XCTAssertNotNil(cached, "Should cache API response")
        XCTAssertEqual(cached, apiResponse, "Should retrieve exact cached data")

        // When - Force refresh (clear cache)
        await sut.remove(forKey: cacheKey)

        // Then - Cache should be empty
        let afterClear: TestHistory? = await sut.get(forKey: cacheKey)
        XCTAssertNil(afterClear, "Should clear cache on force refresh")
    }

    func testRealWorldScenario_CacheInvalidation() async {
        // Given - Multiple cached items
        await sut.set("dashboard_data", forKey: "dashboard")
        await sut.set("profile_data", forKey: "user_profile")
        await sut.set("history_data", forKey: "test_history")

        // When - User logs out (invalidate all caches)
        await sut.clearAll()

        // Then - All caches should be cleared
        let dashboard: String? = await sut.get(forKey: "dashboard")
        let profile: String? = await sut.get(forKey: "user_profile")
        let history: String? = await sut.get(forKey: "test_history")

        XCTAssertNil(dashboard, "Should clear all caches on logout")
        XCTAssertNil(profile, "Should clear all caches on logout")
        XCTAssertNil(history, "Should clear all caches on logout")
    }

    func testRealWorldScenario_PartialCacheExpiration() async {
        // Given - Mixed expiration times
        let shortLivedKey = "short_lived"
        let longLivedKey = "long_lived"

        await sut.set("shortData", forKey: shortLivedKey, expiration: 0.1) // 100ms
        await sut.set("longData", forKey: longLivedKey, expiration: 10.0) // 10 seconds

        // When - Wait for short-lived cache to expire
        try? await Task.sleep(nanoseconds: 200_000_000) // 200ms

        await sut.clearExpired()

        // Then
        let shortData: String? = await sut.get(forKey: shortLivedKey)
        let longData: String? = await sut.get(forKey: longLivedKey)

        XCTAssertNil(shortData, "Short-lived cache should be expired")
        XCTAssertNotNil(longData, "Long-lived cache should remain")
        XCTAssertEqual(longData, "longData")
    }

    func testRealWorldScenario_UpdateExistingCache() async {
        // Given - Initial cache
        let key = "user_profile"
        let initialData = "version_1"

        await sut.set(initialData, forKey: key, expiration: 300)

        // When - Update cache with new data
        let updatedData = "version_2"
        await sut.set(updatedData, forKey: key, expiration: 300)

        // Then
        let cached: String? = await sut.get(forKey: key)
        XCTAssertEqual(cached, updatedData, "Should update existing cache")
        XCTAssertNotEqual(cached, initialData, "Should overwrite old cache")
    }

    func testRealWorldScenario_ConditionalCaching() async {
        // Given - Conditional caching based on data freshness
        let key = "conditional_data"
        let freshData = "fresh"
        let staleData = "stale"

        // When - Cache fresh data with short expiration
        await sut.set(staleData, forKey: key, expiration: 0.1) // 100ms

        // Wait for it to become stale
        try? await Task.sleep(nanoseconds: 200_000_000) // 200ms

        // Check if cache is still valid
        let cachedStale: String? = await sut.get(forKey: key)

        // If stale (nil), cache fresh data
        if cachedStale == nil {
            await sut.set(freshData, forKey: key, expiration: 10.0)
        }

        // Then
        let cachedFresh: String? = await sut.get(forKey: key)
        XCTAssertNil(cachedStale, "Stale data should be expired")
        XCTAssertEqual(cachedFresh, freshData, "Should cache fresh data")
    }
}
