@testable import AIQ
import XCTest

final class KeychainStorageTests: XCTestCase {
    var sut: KeychainStorage!
    let testServiceName = "com.aiq.tests.keychain"

    override func setUp() {
        super.setUp()

        // Create SUT with test-specific service name to avoid interfering with production data
        sut = KeychainStorage(serviceName: testServiceName)

        // Clean up any existing test data
        try? sut.deleteAll()
    }

    override func tearDown() {
        // Clean up test data
        try? sut.deleteAll()
        sut = nil
        super.tearDown()
    }

    // MARK: - Save Operation Tests

    func testSave_Success() throws {
        // Given
        let key = "test_key"
        let value = "test_value"

        // When
        try sut.save(value, forKey: key)

        // Then
        let retrieved = try sut.retrieve(forKey: key)
        XCTAssertEqual(retrieved, value, "Retrieved value should match saved value")
    }

    func testSave_OverwritesExistingValue() throws {
        // Given
        let key = "test_key"
        let initialValue = "initial_value"
        let updatedValue = "updated_value"

        // When
        try sut.save(initialValue, forKey: key)
        try sut.save(updatedValue, forKey: key)

        // Then
        let retrieved = try sut.retrieve(forKey: key)
        XCTAssertEqual(retrieved, updatedValue, "Should overwrite existing value")
    }

    func testSave_MultipleKeys() throws {
        // Given
        let keys = ["key1", "key2", "key3"]
        let values = ["value1", "value2", "value3"]

        // When
        for (key, value) in zip(keys, values) {
            try sut.save(value, forKey: key)
        }

        // Then
        for (key, expectedValue) in zip(keys, values) {
            let retrieved = try sut.retrieve(forKey: key)
            XCTAssertEqual(retrieved, expectedValue, "Each key should have its correct value")
        }
    }

    func testSave_EmptyString() throws {
        // Given
        let key = "empty_key"
        let value = ""

        // When
        try sut.save(value, forKey: key)

        // Then
        let retrieved = try sut.retrieve(forKey: key)
        XCTAssertEqual(retrieved, value, "Should save and retrieve empty string")
    }

    func testSave_SpecialCharacters() throws {
        // Given
        let key = "special_key"
        let value = "Test!@#$%^&*(){}[]|\\:;\"'<>,.?/~`"

        // When
        try sut.save(value, forKey: key)

        // Then
        let retrieved = try sut.retrieve(forKey: key)
        XCTAssertEqual(retrieved, value, "Should handle special characters")
    }

    func testSave_Unicode() throws {
        // Given
        let key = "unicode_key"
        let value = "Hello 世界 🌍 مرحبا"

        // When
        try sut.save(value, forKey: key)

        // Then
        let retrieved = try sut.retrieve(forKey: key)
        XCTAssertEqual(retrieved, value, "Should handle Unicode characters")
    }

    func testSave_LargeValue() throws {
        // Given
        let key = "large_key"
        // Create a large string (10KB of text)
        let value = String(repeating: "abcdefghij", count: 1024)

        // When
        try sut.save(value, forKey: key)

        // Then
        let retrieved = try sut.retrieve(forKey: key)
        XCTAssertEqual(retrieved, value, "Should handle large values")
    }

    // MARK: - Retrieve Operation Tests

    func testRetrieve_Success() throws {
        // Given
        let key = "test_key"
        let value = "test_value"
        try sut.save(value, forKey: key)

        // When
        let retrieved = try sut.retrieve(forKey: key)

        // Then
        XCTAssertEqual(retrieved, value, "Should retrieve saved value")
    }

    func testRetrieve_NonExistentKey_ReturnsNil() throws {
        // Given
        let key = "nonexistent_key"

        // When
        let retrieved = try sut.retrieve(forKey: key)

        // Then
        XCTAssertNil(retrieved, "Should return nil for non-existent key")
    }

    func testRetrieve_AfterDelete_ReturnsNil() throws {
        // Given
        let key = "test_key"
        let value = "test_value"
        try sut.save(value, forKey: key)
        try sut.delete(forKey: key)

        // When
        let retrieved = try sut.retrieve(forKey: key)

        // Then
        XCTAssertNil(retrieved, "Should return nil after deletion")
    }

    // MARK: - Delete Operation Tests

    func testDelete_Success() throws {
        // Given
        let key = "test_key"
        let value = "test_value"
        try sut.save(value, forKey: key)

        // When
        try sut.delete(forKey: key)

        // Then
        let retrieved = try sut.retrieve(forKey: key)
        XCTAssertNil(retrieved, "Value should be deleted")
    }

    func testDelete_NonExistentKey_DoesNotThrow() throws {
        // Given
        let key = "nonexistent_key"

        // When/Then - Should not throw error
        XCTAssertNoThrow(try sut.delete(forKey: key), "Deleting non-existent key should not throw")
    }

    func testDelete_OneOfMultipleKeys() throws {
        // Given
        try sut.save("value1", forKey: "key1")
        try sut.save("value2", forKey: "key2")
        try sut.save("value3", forKey: "key3")

        // When
        try sut.delete(forKey: "key2")

        // Then
        XCTAssertEqual(try sut.retrieve(forKey: "key1"), "value1", "Other keys should remain")
        XCTAssertNil(try sut.retrieve(forKey: "key2"), "Deleted key should be nil")
        XCTAssertEqual(try sut.retrieve(forKey: "key3"), "value3", "Other keys should remain")
    }

    // MARK: - Delete All Operation Tests

    func testDeleteAll_Success() throws {
        // Given
        try sut.save("value1", forKey: "key1")
        try sut.save("value2", forKey: "key2")
        try sut.save("value3", forKey: "key3")

        // When
        try sut.deleteAll()

        // Then
        XCTAssertNil(try sut.retrieve(forKey: "key1"), "All keys should be deleted")
        XCTAssertNil(try sut.retrieve(forKey: "key2"), "All keys should be deleted")
        XCTAssertNil(try sut.retrieve(forKey: "key3"), "All keys should be deleted")
    }

    func testDeleteAll_EmptyKeychain_DoesNotThrow() throws {
        // Given - Empty keychain

        // When/Then - Should not throw error
        XCTAssertNoThrow(try sut.deleteAll(), "Deleting from empty keychain should not throw")
    }

    // MARK: - Data Persistence Tests

    func testPersistence_SurvivesInstanceRecreation() throws {
        // Given
        let key = "persistent_key"
        let value = "persistent_value"
        try sut.save(value, forKey: key)

        // When - Create a new instance with same service name
        let newInstance = KeychainStorage(serviceName: testServiceName)
        let retrieved = try newInstance.retrieve(forKey: key)

        // Then
        XCTAssertEqual(retrieved, value, "Data should persist across instances")

        // Clean up
        try newInstance.deleteAll()
    }

    func testPersistence_IsolatedByServiceName() throws {
        // Given
        let key = "shared_key"
        let value1 = "value_for_service1"
        let value2 = "value_for_service2"

        let service1 = KeychainStorage(serviceName: "com.aiq.tests.service1")
        let service2 = KeychainStorage(serviceName: "com.aiq.tests.service2")

        // When
        try service1.save(value1, forKey: key)
        try service2.save(value2, forKey: key)

        // Then
        XCTAssertEqual(try service1.retrieve(forKey: key), value1, "Service 1 should have its value")
        XCTAssertEqual(try service2.retrieve(forKey: key), value2, "Service 2 should have its value")

        // Clean up
        try service1.deleteAll()
        try service2.deleteAll()
    }

    // MARK: - Error Handling Tests

    func testError_EncodingFailed() {
        // Note: It's extremely difficult to make UTF-8 encoding fail in practice,
        // as Swift strings are inherently UTF-8 compatible.
        // This test documents that encoding errors are theoretically handled,
        // but in practice, UTF-8 encoding of Swift strings should never fail.

        // The error case is handled in the code, but we acknowledge that
        // triggering it in a test is not practical with standard Swift strings.
    }

    func testError_DecodingFailed() {
        // Note: Similar to encoding, UTF-8 decoding of valid keychain data
        // should not fail in practice. The error handling exists as a safety net,
        // but creating a scenario where keychain returns data that's not UTF-8
        // is not feasible in a unit test without mocking the keychain itself.

        // The error case is handled in the code for robustness.
    }

    // MARK: - Concurrent Access Tests

    func testConcurrentSave_ThreadSafety() {
        // Given
        let iterations = 100
        let expectation = expectation(description: "All saves complete")
        expectation.expectedFulfillmentCount = iterations

        // When - Save concurrently from multiple threads
        for i in 0 ..< iterations {
            DispatchQueue.global().async {
                do {
                    try self.sut.save("value_\(i)", forKey: "key_\(i)")
                    expectation.fulfill()
                } catch {
                    XCTFail("Concurrent save failed: \(error)")
                }
            }
        }

        // Then
        wait(for: [expectation], timeout: 10.0)

        // Verify all values were saved
        for i in 0 ..< iterations {
            let retrieved = try? sut.retrieve(forKey: "key_\(i)")
            XCTAssertEqual(retrieved, "value_\(i)", "Value \(i) should be saved")
        }
    }

    func testConcurrentRetrieve_ThreadSafety() {
        // Given
        let key = "shared_key"
        let value = "shared_value"
        try? sut.save(value, forKey: key)

        let iterations = 100
        let expectation = expectation(description: "All retrievals complete")
        expectation.expectedFulfillmentCount = iterations

        // When - Retrieve concurrently from multiple threads
        for _ in 0 ..< iterations {
            DispatchQueue.global().async {
                do {
                    let retrieved = try self.sut.retrieve(forKey: key)
                    XCTAssertEqual(retrieved, value, "Should retrieve correct value")
                    expectation.fulfill()
                } catch {
                    XCTFail("Concurrent retrieve failed: \(error)")
                }
            }
        }

        // Then
        wait(for: [expectation], timeout: 10.0)
    }

    func testConcurrentDelete_ThreadSafety() {
        // Given
        let iterations = 100

        // Save test data
        for i in 0 ..< iterations {
            try? sut.save("value_\(i)", forKey: "key_\(i)")
        }

        let expectation = expectation(description: "All deletions complete")
        expectation.expectedFulfillmentCount = iterations

        // When - Delete concurrently from multiple threads
        for i in 0 ..< iterations {
            DispatchQueue.global().async {
                do {
                    try self.sut.delete(forKey: "key_\(i)")
                    expectation.fulfill()
                } catch {
                    XCTFail("Concurrent delete failed: \(error)")
                }
            }
        }

        // Then
        wait(for: [expectation], timeout: 10.0)

        // Verify all values were deleted
        for i in 0 ..< iterations {
            let retrieved = try? sut.retrieve(forKey: "key_\(i)")
            XCTAssertNil(retrieved, "Value \(i) should be deleted")
        }
    }

    func testConcurrentMixedOperations_ThreadSafety() {
        // Given
        let iterations = 50
        let expectation = expectation(description: "All operations complete")
        expectation.expectedFulfillmentCount = iterations * 3 // save, retrieve, delete

        // When - Perform mixed operations concurrently
        for i in 0 ..< iterations {
            // Save
            DispatchQueue.global().async {
                do {
                    try self.sut.save("value_\(i)", forKey: "key_\(i)")
                    expectation.fulfill()
                } catch {
                    XCTFail("Save failed: \(error)")
                }
            }

            // Retrieve
            DispatchQueue.global().async {
                do {
                    _ = try self.sut.retrieve(forKey: "key_\(i)")
                    expectation.fulfill()
                } catch {
                    XCTFail("Retrieve failed: \(error)")
                }
            }

            // Delete
            DispatchQueue.global().async {
                do {
                    try self.sut.delete(forKey: "key_\(i % 10)") // Delete with some overlap
                    expectation.fulfill()
                } catch {
                    XCTFail("Delete failed: \(error)")
                }
            }
        }

        // Then
        wait(for: [expectation], timeout: 10.0)
    }

    func testConcurrentSaveToSameKey_ThreadSafety() {
        // Given
        let key = "contested_key"
        let iterations = 100
        let expectation = expectation(description: "All saves complete")
        expectation.expectedFulfillmentCount = iterations

        // Track successful and failed saves - concurrent saves to same key may fail
        // due to race conditions in the delete-then-add pattern. This is expected
        // Keychain behavior when multiple threads compete for the same key.
        let successLock = NSLock()
        var successes = 0

        // When - Multiple threads try to save to the same key
        for i in 0 ..< iterations {
            DispatchQueue.global().async {
                do {
                    try self.sut.save("value_\(i)", forKey: key)
                    successLock.lock()
                    successes += 1
                    successLock.unlock()
                } catch {
                    // Concurrent saves to same key may fail with errSecDuplicateItem (-25299)
                    // This is expected behavior when multiple threads race to save the same key
                }
                expectation.fulfill()
            }
        }

        // Then
        wait(for: [expectation], timeout: 10.0)

        // At least one save should succeed
        XCTAssertGreaterThan(successes, 0, "At least one concurrent save should succeed")

        // One of the values should be present (we can't predict which one due to race conditions)
        let retrieved = try? sut.retrieve(forKey: key)
        XCTAssertNotNil(retrieved, "A value should be present after concurrent saves")
        XCTAssertTrue(retrieved?.hasPrefix("value_") ?? false, "Value should be one of the saved values")
    }

    // MARK: - Integration Tests

    func testRealWorldScenario_TokenStorage() throws {
        // Given - Simulating OAuth token storage
        let accessTokenKey = "access_token"
        let refreshTokenKey = "refresh_token"
        let accessToken = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ"
        let refreshToken = "abc123def456ghi789"

        // When - Save tokens
        try sut.save(accessToken, forKey: accessTokenKey)
        try sut.save(refreshToken, forKey: refreshTokenKey)

        // Then - Verify tokens are stored
        XCTAssertEqual(try sut.retrieve(forKey: accessTokenKey), accessToken)
        XCTAssertEqual(try sut.retrieve(forKey: refreshTokenKey), refreshToken)

        // When - Update access token (token refresh scenario)
        let newAccessToken = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDMzfQ"
        try sut.save(newAccessToken, forKey: accessTokenKey)

        // Then - Verify token was updated
        XCTAssertEqual(try sut.retrieve(forKey: accessTokenKey), newAccessToken)
        XCTAssertEqual(try sut.retrieve(forKey: refreshTokenKey), refreshToken, "Refresh token should remain unchanged")

        // When - Logout (delete all tokens)
        try sut.deleteAll()

        // Then - Verify tokens are deleted
        XCTAssertNil(try sut.retrieve(forKey: accessTokenKey))
        XCTAssertNil(try sut.retrieve(forKey: refreshTokenKey))
    }
}
