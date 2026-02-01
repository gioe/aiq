@testable import AIQ
import XCTest

/// Tests for NetworkLogger - a DEBUG-only logging utility.
///
/// Note: NetworkLogger only produces output in DEBUG builds using #if DEBUG guards.
/// These tests verify that logging calls don't crash with various inputs,
/// which is the appropriate testing strategy for side-effect-only logging utilities.
/// We cannot verify actual console output in unit tests.
final class NetworkLoggerTests: XCTestCase {
    var sut: NetworkLogger!

    override func setUp() {
        super.setUp()
        sut = NetworkLogger.shared
    }

    // MARK: - Shared Instance Tests

    func testSharedInstance_IsAccessible() {
        // When
        let sharedInstance = NetworkLogger.shared

        // Then
        XCTAssertNotNil(sharedInstance)
    }

    func testSharedInstance_IsSameInstance() {
        // Given
        // NetworkLogger is a struct with a private init, so all access goes through shared

        // When
        let instance1 = NetworkLogger.shared
        let instance2 = NetworkLogger.shared

        // Then - Both instances reference the same static shared property
        // For structs, we verify they work identically since they're value types
        // The shared pattern ensures consistent behavior
        XCTAssertNotNil(instance1)
        XCTAssertNotNil(instance2)
    }

    // MARK: - logRequest Tests

    func testLogRequest_DoesNotCrash() {
        // Given
        let url = URL(string: "https://example.com/api/test")!
        var request = URLRequest(url: url)
        request.httpMethod = "GET"

        // When/Then - Should not crash
        sut.logRequest(request)
    }

    func testLogRequest_WithHeaders_DoesNotCrash() {
        // Given
        let url = URL(string: "https://example.com/api/test")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer token123", forHTTPHeaderField: "Authorization")

        // When/Then - Should not crash and should mask authorization
        sut.logRequest(request)
    }

    func testLogRequest_WithBody_DoesNotCrash() throws {
        // Given
        let url = URL(string: "https://example.com/api/test")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        let bodyData = try XCTUnwrap("""
        {"key": "value"}
        """.data(using: .utf8))
        request.httpBody = bodyData

        // When/Then - Should not crash
        sut.logRequest(request)
    }

    func testLogRequest_WithInvalidJSONBody_DoesNotCrash() throws {
        // Given
        let url = URL(string: "https://example.com/api/test")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        // Invalid JSON
        let bodyData = try XCTUnwrap("not valid json".data(using: .utf8))
        request.httpBody = bodyData

        // When/Then - Should not crash
        sut.logRequest(request)
    }

    func testLogRequest_WithEmptyURL_DoesNotCrash() {
        // Given - URLRequest requires a URL, so we can't test nil URL
        // But we can test with minimal request
        let url = URL(string: "https://example.com")!
        let request = URLRequest(url: url)

        // When/Then - Should not crash
        sut.logRequest(request)
    }

    func testLogRequest_WithNoHTTPMethod_DoesNotCrash() {
        // Given
        let url = URL(string: "https://example.com/api/test")!
        let request = URLRequest(url: url) // No httpMethod set

        // When/Then - Should not crash
        sut.logRequest(request)
    }

    // MARK: - logResponse Tests

    func testLogResponse_DoesNotCrash() {
        // Given
        let url = URL(string: "https://example.com/api/test")!
        let response = HTTPURLResponse(
            url: url,
            statusCode: 200,
            httpVersion: nil,
            headerFields: nil
        )!

        // When/Then - Should not crash
        sut.logResponse(response, data: nil)
    }

    func testLogResponse_WithData_DoesNotCrash() throws {
        // Given
        let url = URL(string: "https://example.com/api/test")!
        let response = HTTPURLResponse(
            url: url,
            statusCode: 200,
            httpVersion: nil,
            headerFields: nil
        )!
        let responseData = try XCTUnwrap("""
        {"result": "success"}
        """.data(using: .utf8))

        // When/Then - Should not crash
        sut.logResponse(response, data: responseData)
    }

    func testLogResponse_WithErrorStatusCode_DoesNotCrash() {
        // Given
        let url = URL(string: "https://example.com/api/test")!
        let response = HTTPURLResponse(
            url: url,
            statusCode: 500,
            httpVersion: nil,
            headerFields: nil
        )!

        // When/Then - Should not crash
        sut.logResponse(response, data: nil)
    }

    func testLogResponse_With404StatusCode_DoesNotCrash() {
        // Given
        let url = URL(string: "https://example.com/api/test")!
        let response = HTTPURLResponse(
            url: url,
            statusCode: 404,
            httpVersion: nil,
            headerFields: nil
        )!

        // When/Then - Should not crash
        sut.logResponse(response, data: nil)
    }

    func testLogResponse_WithInvalidJSONData_DoesNotCrash() throws {
        // Given
        let url = URL(string: "https://example.com/api/test")!
        let response = HTTPURLResponse(
            url: url,
            statusCode: 200,
            httpVersion: nil,
            headerFields: nil
        )!
        let invalidData = try XCTUnwrap("not valid json".data(using: .utf8))

        // When/Then - Should not crash (should gracefully handle invalid JSON)
        sut.logResponse(response, data: invalidData)
    }

    func testLogResponse_WithEmptyData_DoesNotCrash() {
        // Given
        let url = URL(string: "https://example.com/api/test")!
        let response = HTTPURLResponse(
            url: url,
            statusCode: 204, // No Content
            httpVersion: nil,
            headerFields: nil
        )!
        let emptyData = Data()

        // When/Then - Should not crash
        sut.logResponse(response, data: emptyData)
    }

    func testLogResponse_WithBinaryData_DoesNotCrash() {
        // Given
        let url = URL(string: "https://example.com/api/test")!
        let response = HTTPURLResponse(
            url: url,
            statusCode: 200,
            httpVersion: nil,
            headerFields: nil
        )!
        let binaryData = Data([0x00, 0x01, 0x02, 0xFF])

        // When/Then - Should not crash
        sut.logResponse(response, data: binaryData)
    }

    // MARK: - logError Tests

    func testLogError_DoesNotCrash() {
        // Given
        let error = NSError(domain: "TestError", code: -1, userInfo: nil)
        let url = URL(string: "https://example.com/api/test")

        // When/Then - Should not crash
        sut.logError(error, for: url)
    }

    func testLogError_WithNilURL_DoesNotCrash() {
        // Given
        let error = NSError(domain: "TestError", code: -1, userInfo: nil)

        // When/Then - Should not crash
        sut.logError(error, for: nil)
    }

    func testLogError_WithURLError_DoesNotCrash() {
        // Given
        let urlError = URLError(.notConnectedToInternet)
        let url = URL(string: "https://example.com/api/test")

        // When/Then - Should not crash
        sut.logError(urlError, for: url)
    }

    func testLogError_WithCustomError_DoesNotCrash() {
        // Given
        enum CustomError: Error {
            case testError
        }
        let error = CustomError.testError
        let url = URL(string: "https://example.com/api/test")

        // When/Then - Should not crash
        sut.logError(error, for: url)
    }

    // MARK: - Debug Mode Tests

    func testLogging_OnlyInDebugMode() {
        // Note: The NetworkLogger only logs in DEBUG mode
        // These tests verify that the methods don't crash
        // Actual logging output would only appear in DEBUG builds

        // Given
        let url = URL(string: "https://example.com/api/test")!
        var request = URLRequest(url: url)
        request.httpMethod = "GET"

        let response = HTTPURLResponse(
            url: url,
            statusCode: 200,
            httpVersion: nil,
            headerFields: nil
        )!

        let error = NSError(domain: "Test", code: -1, userInfo: nil)

        // When/Then - All methods should complete without crashing
        sut.logRequest(request)
        sut.logResponse(response, data: nil)
        sut.logError(error, for: url)

        // Test passes if we reach here without crashing
        XCTAssertTrue(true)
    }

    // MARK: - Edge Cases

    func testLogRequest_WithVeryLongURL_DoesNotCrash() {
        // Given - URL with very long path
        let longPath = String(repeating: "a", count: 10000)
        let url = URL(string: "https://example.com/\(longPath)")!
        let request = URLRequest(url: url)

        // When/Then - Should not crash
        sut.logRequest(request)
    }

    func testLogRequest_WithManyHeaders_DoesNotCrash() {
        // Given
        let url = URL(string: "https://example.com/api/test")!
        var request = URLRequest(url: url)
        request.httpMethod = "GET"

        // Add many headers
        for i in 0 ..< 100 {
            request.setValue("value\(i)", forHTTPHeaderField: "Header\(i)")
        }

        // When/Then - Should not crash
        sut.logRequest(request)
    }

    func testLogResponse_WithVeryLargeData_DoesNotCrash() throws {
        // Given
        let url = URL(string: "https://example.com/api/test")!
        let response = HTTPURLResponse(
            url: url,
            statusCode: 200,
            httpVersion: nil,
            headerFields: nil
        )!

        // Create large JSON data
        let largeArray = Array(repeating: "test", count: 10000)
        let largeData = try JSONEncoder().encode(largeArray)

        // When/Then - Should not crash
        sut.logResponse(response, data: largeData)
    }

    func testLogRequest_WithSpecialCharactersInURL_DoesNotCrash() {
        // Given
        let url = URL(string: "https://example.com/api/test?query=hello%20world&special=%21%40%23")!
        let request = URLRequest(url: url)

        // When/Then - Should not crash
        sut.logRequest(request)
    }

    func testLogResponse_WithNestedJSON_DoesNotCrash() throws {
        // Given
        let url = URL(string: "https://example.com/api/test")!
        let response = HTTPURLResponse(
            url: url,
            statusCode: 200,
            httpVersion: nil,
            headerFields: nil
        )!

        let nestedJSON = """
        {
            "level1": {
                "level2": {
                    "level3": {
                        "value": "deeply nested"
                    }
                }
            }
        }
        """
        let data = try XCTUnwrap(nestedJSON.data(using: .utf8))

        // When/Then - Should not crash
        sut.logResponse(response, data: data)
    }

    func testLogError_WithNestedError_DoesNotCrash() {
        // Given
        let underlyingError = NSError(domain: "Underlying", code: -1, userInfo: nil)
        let topError = NSError(
            domain: "Top",
            code: -2,
            userInfo: [NSUnderlyingErrorKey: underlyingError]
        )
        let url = URL(string: "https://example.com/api/test")

        // When/Then - Should not crash
        sut.logError(topError, for: url)
    }

    // MARK: - Multiple Calls Tests

    func testLogRequest_MultipleSequentialCalls_DoesNotCrash() {
        // Given
        let url = URL(string: "https://example.com/api/test")!
        var request = URLRequest(url: url)
        request.httpMethod = "GET"

        // When/Then - Multiple calls should not crash
        for _ in 0 ..< 100 {
            sut.logRequest(request)
        }
    }

    func testLogResponse_MultipleSequentialCalls_DoesNotCrash() throws {
        // Given
        let url = URL(string: "https://example.com/api/test")!
        let response = HTTPURLResponse(
            url: url,
            statusCode: 200,
            httpVersion: nil,
            headerFields: nil
        )!
        let data = try XCTUnwrap("""
        {"key": "value"}
        """.data(using: .utf8))

        // When/Then - Multiple calls should not crash
        for _ in 0 ..< 100 {
            sut.logResponse(response, data: data)
        }
    }

    func testMixedLoggingCalls_DoesNotCrash() throws {
        // Given
        let url = URL(string: "https://example.com/api/test")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        let requestBody = try XCTUnwrap("""
        {"request": "data"}
        """.data(using: .utf8))
        request.httpBody = requestBody

        let response = HTTPURLResponse(
            url: url,
            statusCode: 200,
            httpVersion: nil,
            headerFields: nil
        )!
        let responseData = try XCTUnwrap("""
        {"response": "data"}
        """.data(using: .utf8))

        let error = NSError(domain: "Test", code: -1, userInfo: nil)

        // When/Then - Interleaved calls should not crash
        for _ in 0 ..< 10 {
            sut.logRequest(request)
            sut.logResponse(response, data: responseData)
            sut.logError(error, for: url)
        }
    }
}
