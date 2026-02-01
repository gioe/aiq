import Combine
import XCTest

@testable import AIQ

@MainActor
final class BaseViewModelTests: XCTestCase {
    var sut: BaseViewModel!

    override func setUp() {
        super.setUp()
        sut = BaseViewModel()
    }

    // MARK: - Initialization Tests

    func testInitialState() {
        // Then
        XCTAssertFalse(sut.isLoading, "isLoading should be false initially")
        XCTAssertNil(sut.error, "error should be nil initially")
        XCTAssertTrue(sut.cancellables.isEmpty, "cancellables should be empty initially")
    }

    // MARK: - Error Handling Tests

    func testHandleError() {
        // Given
        let testError = NSError(
            domain: "TestDomain",
            code: -1,
            userInfo: [NSLocalizedDescriptionKey: "Test error"]
        )
        sut.isLoading = true

        // When
        sut.handleError(testError, context: .unknown)

        // Then
        XCTAssertFalse(sut.isLoading, "isLoading should be set to false")
        XCTAssertNotNil(sut.error, "error should not be nil")
        XCTAssertEqual(
            (sut.error as NSError?)?.localizedDescription,
            testError.localizedDescription,
            "error should match the provided error"
        )
    }

    func testClearError() {
        // Given
        let testError = NSError(
            domain: "TestDomain",
            code: -1,
            userInfo: [NSLocalizedDescriptionKey: "Test error"]
        )
        sut.error = testError

        // When
        sut.clearError()

        // Then
        XCTAssertNil(sut.error, "error should be nil after clearing")
    }

    // MARK: - Loading State Tests

    func testSetLoadingTrue() {
        // When
        sut.setLoading(true)

        // Then
        XCTAssertTrue(sut.isLoading, "isLoading should be true")
    }

    func testSetLoadingFalse() {
        // Given
        sut.isLoading = true

        // When
        sut.setLoading(false)

        // Then
        XCTAssertFalse(sut.isLoading, "isLoading should be false")
    }

    // MARK: - Published Properties Tests

    func testIsLoadingPublishes() async {
        // Given
        var receivedValues: [Bool] = []
        let expectation = expectation(description: "isLoading publishes")
        expectation.expectedFulfillmentCount = 3 // Initial + 2 changes

        let cancellable = sut.$isLoading
            .sink { value in
                receivedValues.append(value)
                expectation.fulfill()
            }

        // When
        sut.setLoading(true)
        sut.setLoading(false)

        // Then
        await fulfillment(of: [expectation], timeout: 1.0)
        XCTAssertEqual(receivedValues, [false, true, false])
        cancellable.cancel()
    }

    func testErrorPublishes() async {
        // Given
        var receivedCount = 0
        let expectation = expectation(description: "error publishes")
        expectation.expectedFulfillmentCount = 3 // Initial + set + clear

        let cancellable = sut.$error
            .sink { _ in
                receivedCount += 1
                expectation.fulfill()
            }

        let testError = NSError(
            domain: "TestDomain",
            code: -1,
            userInfo: [NSLocalizedDescriptionKey: "Test error"]
        )

        // When
        sut.error = testError
        sut.clearError()

        // Then
        await fulfillment(of: [expectation], timeout: 1.0)
        XCTAssertEqual(receivedCount, 3)
        cancellable.cancel()
    }
}
