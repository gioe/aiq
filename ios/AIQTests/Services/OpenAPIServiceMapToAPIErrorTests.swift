@testable import AIQ
import AIQAPIClient
import XCTest

/// Tests for OpenAPIService.mapToAPIError(_:) — specifically the CancellationError pass-through.
final class OpenAPIServiceMapToAPIErrorTests: XCTestCase {
    private var service: OpenAPIService!

    override func setUp() {
        super.setUp()
        service = OpenAPIService(
            factory: AIQAPIClientFactory(serverURL: URL(string: "https://example.com")!)
        )
    }

    override func tearDown() {
        service = nil
        super.tearDown()
    }

    // MARK: - CancellationError Pass-through

    /// CancellationError must be rethrown as-is, never wrapped in APIError.unknown.
    func testMapToAPIError_CancellationError_RethrowsAsCancellationError() {
        XCTAssertThrowsError(try service.mapToAPIError(CancellationError())) { error in
            XCTAssertTrue(
                error is CancellationError,
                "CancellationError must propagate as CancellationError, not be wrapped as APIError"
            )
        }
    }

    // MARK: - APIError Pass-through

    /// An existing APIError must be returned unchanged, not double-wrapped.
    func testMapToAPIError_APIError_ReturnsUnchanged() throws {
        let result = try service.mapToAPIError(APIError.timeout)
        if case .timeout = result {
            // expected
        } else {
            XCTFail("Expected APIError.timeout, got \(result)")
        }
    }

    // MARK: - URLError Mapping

    /// URLError.notConnectedToInternet maps to APIError.noInternetConnection.
    func testMapToAPIError_URLErrorNotConnected_MapsToNoInternetConnection() throws {
        let urlError = URLError(.notConnectedToInternet)
        let result = try service.mapToAPIError(urlError)
        if case .noInternetConnection = result {
            // expected
        } else {
            XCTFail("Expected APIError.noInternetConnection, got \(result)")
        }
    }

    /// URLError.timedOut maps to APIError.timeout.
    func testMapToAPIError_URLErrorTimedOut_MapsToTimeout() throws {
        let urlError = URLError(.timedOut)
        let result = try service.mapToAPIError(urlError)
        if case .timeout = result {
            // expected
        } else {
            XCTFail("Expected APIError.timeout, got \(result)")
        }
    }

    // MARK: - Unknown Error Fallback

    /// Unrecognised errors fall back to APIError.unknown without wrapping CancellationError.
    func testMapToAPIError_UnknownError_MapsToAPIErrorUnknown() throws {
        let error = NSError(domain: "test", code: 42, userInfo: [NSLocalizedDescriptionKey: "boom"])
        let result = try service.mapToAPIError(error)
        if case .unknown = result {
            // expected
        } else {
            XCTFail("Expected APIError.unknown, got \(result)")
        }
    }
}
