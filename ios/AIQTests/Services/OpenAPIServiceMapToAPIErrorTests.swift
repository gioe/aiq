@testable import AIQ
import AIQAPIClientCore
import OpenAPIRuntime
import XCTest

/// Tests for OpenAPIService.mapToAPIError(_:).
final class OpenAPIServiceMapToAPIErrorTests: XCTestCase {
    private var service: OpenAPIService!

    override func setUp() {
        super.setUp()
        service = OpenAPIService(
            factory: APIClientFactory(serverURL: URL(string: "https://example.com")!)
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
        let result = try service.mapToAPIError(APIError.api(.timeout))
        if case .api(.timeout) = result {
            // expected
        } else {
            XCTFail("Expected APIError.api(.timeout), got \(result)")
        }
    }

    // MARK: - URLError Mapping

    /// URLError.notConnectedToInternet maps to APIError.noInternetConnection.
    func testMapToAPIError_URLErrorNotConnected_MapsToNoInternetConnection() throws {
        let urlError = URLError(.notConnectedToInternet)
        let result = try service.mapToAPIError(urlError)
        if case .api(.noInternetConnection) = result {
            // expected
        } else {
            XCTFail("Expected APIError.api(.noInternetConnection), got \(result)")
        }
    }

    /// URLError.timedOut maps to APIError.api(.timeout).
    func testMapToAPIError_URLErrorTimedOut_MapsToTimeout() throws {
        let urlError = URLError(.timedOut)
        let result = try service.mapToAPIError(urlError)
        if case .api(.timeout) = result {
            // expected
        } else {
            XCTFail("Expected APIError.api(.timeout), got \(result)")
        }
    }

    /// URLError.networkConnectionLost also maps to APIError.api(.noInternetConnection) (same switch case).
    func testMapToAPIError_URLErrorNetworkConnectionLost_MapsToNoInternetConnection() throws {
        let urlError = URLError(.networkConnectionLost)
        let result = try service.mapToAPIError(urlError)
        if case .api(.noInternetConnection) = result {
            // expected
        } else {
            XCTFail("Expected APIError.api(.noInternetConnection), got \(result)")
        }
    }

    /// URLError default case (e.g. .cannotConnectToHost) maps to APIError.api(.networkError).
    func testMapToAPIError_URLErrorOther_MapsToNetworkError() throws {
        let urlError = URLError(.cannotConnectToHost)
        let result = try service.mapToAPIError(urlError)
        if case .api(.networkError) = result {
            // expected
        } else {
            XCTFail("Expected APIError.api(.networkError), got \(result)")
        }
    }

    // MARK: - DecodingError Mapping

    /// A DecodingError nested under NSUnderlyingErrorKey maps to APIError.api(.decodingError).
    func testMapToAPIError_WrappedDecodingError_MapsToDecodingError() throws {
        let decodingError = DecodingError.dataCorrupted(
            .init(codingPath: [], debugDescription: "corrupted")
        )
        let wrappedError = NSError(
            domain: "OpenAPIRuntime",
            code: 1,
            userInfo: [NSUnderlyingErrorKey: decodingError]
        )
        let result = try service.mapToAPIError(wrappedError)
        if case .api(.decodingError) = result {
            // expected
        } else {
            XCTFail("Expected APIError.api(.decodingError), got \(result)")
        }
    }

    // MARK: - ClientError Unwrapping

    private func makeClientError(wrapping underlying: any Error) -> ClientError {
        ClientError(
            operationID: "testOp",
            operationInput: "input" as any Sendable,
            causeDescription: "test",
            underlyingError: underlying
        )
    }

    /// A URLError.notConnectedToInternet wrapped inside a ClientError surfaces as APIError.api(.noInternetConnection).
    func testMapToAPIError_ClientErrorWrappingNotConnected_MapsToNoInternetConnection() throws {
        let result = try service.mapToAPIError(makeClientError(wrapping: URLError(.notConnectedToInternet)))
        if case .api(.noInternetConnection) = result {
            // expected
        } else {
            XCTFail("Expected APIError.api(.noInternetConnection), got \(result)")
        }
    }

    /// A URLError.timedOut wrapped inside a ClientError surfaces as APIError.api(.timeout).
    func testMapToAPIError_ClientErrorWrappingTimedOut_MapsToTimeout() throws {
        let result = try service.mapToAPIError(makeClientError(wrapping: URLError(.timedOut)))
        if case .api(.timeout) = result {
            // expected
        } else {
            XCTFail("Expected APIError.api(.timeout), got \(result)")
        }
    }

    /// A DecodingError wrapped inside a ClientError surfaces as APIError.api(.decodingError).
    func testMapToAPIError_ClientErrorWrappingDecodingError_MapsToDecodingError() throws {
        let decodingError = DecodingError.dataCorrupted(
            .init(codingPath: [], debugDescription: "corrupted")
        )
        let result = try service.mapToAPIError(makeClientError(wrapping: decodingError))
        if case .api(.decodingError) = result {
            // expected
        } else {
            XCTFail("Expected APIError.api(.decodingError), got \(result)")
        }
    }

    /// A CancellationError wrapped inside a ClientError is rethrown as CancellationError.
    func testMapToAPIError_ClientErrorWrappingCancellationError_Rethrows() {
        XCTAssertThrowsError(
            try service.mapToAPIError(makeClientError(wrapping: CancellationError()))
        ) { error in
            XCTAssertTrue(
                error is CancellationError,
                "CancellationError inside ClientError must propagate as CancellationError"
            )
        }
    }

    // MARK: - Unknown Error Fallback

    /// Unrecognised errors fall back to APIError.api(.unknown) without wrapping CancellationError.
    func testMapToAPIError_UnknownError_MapsToAPIErrorUnknown() throws {
        let error = NSError(domain: "test", code: 42, userInfo: [NSLocalizedDescriptionKey: "boom"])
        let result = try service.mapToAPIError(error)
        if case .api(.unknown) = result {
            // expected
        } else {
            XCTFail("Expected APIError.api(.unknown), got \(result)")
        }
    }
}
