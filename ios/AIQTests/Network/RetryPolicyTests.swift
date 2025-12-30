@testable import AIQ
import XCTest

/// Unit tests for RetryPolicy and RetryExecutor
///
/// Verifies:
/// - RetryPolicy struct configuration (default, none, custom)
/// - Status code and error retry logic
/// - Exponential backoff delay calculation
/// - RetryExecutor retry behavior (max attempts, retryable vs non-retryable)
/// - Edge cases (zero retries, negative attempts, overflow scenarios)
///
/// Note: Time delays are verified by checking calculated values, not actual sleep times,
/// to avoid slow tests. RetryExecutor tests use controlled mock operations.
final class RetryPolicyTests: XCTestCase {
    // MARK: - RetryPolicy Default Configuration Tests

    func testDefaultPolicy_MaxAttemptsIs3() {
        // Given/When
        let sut = RetryPolicy.default

        // Then
        XCTAssertEqual(sut.maxAttempts, 3, "Default policy should allow 3 attempts")
    }

    func testDefaultPolicy_RetryableStatusCodes() {
        // Given
        let sut = RetryPolicy.default

        // Then - Verify retryable codes
        XCTAssertTrue(sut.shouldRetry(statusCode: 408), "Should retry Request Timeout")
        XCTAssertTrue(sut.shouldRetry(statusCode: 429), "Should retry Too Many Requests")
        XCTAssertTrue(sut.shouldRetry(statusCode: 500), "Should retry Internal Server Error")
        XCTAssertTrue(sut.shouldRetry(statusCode: 502), "Should retry Bad Gateway")
        XCTAssertTrue(sut.shouldRetry(statusCode: 503), "Should retry Service Unavailable")
        XCTAssertTrue(sut.shouldRetry(statusCode: 504), "Should retry Gateway Timeout")
    }

    func testDefaultPolicy_NonRetryableStatusCodes() {
        // Given
        let sut = RetryPolicy.default

        // Then - Verify non-retryable codes
        XCTAssertFalse(sut.shouldRetry(statusCode: 200), "Should not retry OK")
        XCTAssertFalse(sut.shouldRetry(statusCode: 400), "Should not retry Bad Request")
        XCTAssertFalse(sut.shouldRetry(statusCode: 401), "Should not retry Unauthorized")
        XCTAssertFalse(sut.shouldRetry(statusCode: 403), "Should not retry Forbidden")
        XCTAssertFalse(sut.shouldRetry(statusCode: 404), "Should not retry Not Found")
        XCTAssertFalse(sut.shouldRetry(statusCode: 422), "Should not retry Unprocessable Entity")
    }

    func testDefaultPolicy_RetryableErrors() {
        // Given
        let sut = RetryPolicy.default

        // Then - Verify retryable URLError codes
        XCTAssertTrue(sut.shouldRetry(error: URLError(.timedOut)), "Should retry timeout")
        XCTAssertTrue(sut.shouldRetry(error: URLError(.networkConnectionLost)), "Should retry connection lost")
        XCTAssertTrue(sut.shouldRetry(error: URLError(.notConnectedToInternet)), "Should retry no internet")
        XCTAssertTrue(sut.shouldRetry(error: URLError(.cannotConnectToHost)), "Should retry cannot connect")
    }

    func testDefaultPolicy_NonRetryableErrors() {
        // Given
        let sut = RetryPolicy.default

        // Then - Verify non-retryable URLError codes
        XCTAssertFalse(sut.shouldRetry(error: URLError(.badURL)), "Should not retry bad URL")
        XCTAssertFalse(sut.shouldRetry(error: URLError(.cancelled)), "Should not retry cancelled")
        XCTAssertFalse(sut.shouldRetry(error: URLError(.badServerResponse)), "Should not retry bad server response")
    }

    func testDefaultPolicy_NonURLErrors() {
        // Given
        let sut = RetryPolicy.default
        struct CustomError: Error {}

        // When/Then
        XCTAssertFalse(sut.shouldRetry(error: CustomError()), "Should not retry non-URLError types")
    }

    func testDefaultPolicy_ExponentialBackoffDelay() {
        // Given
        let sut = RetryPolicy.default

        // Then - Verify exponential backoff: 1s, 2s, 4s
        XCTAssertEqual(sut.delay(for: 1), 1.0, accuracy: 0.001, "First retry delay should be 1 second")
        XCTAssertEqual(sut.delay(for: 2), 2.0, accuracy: 0.001, "Second retry delay should be 2 seconds")
        XCTAssertEqual(sut.delay(for: 3), 4.0, accuracy: 0.001, "Third retry delay should be 4 seconds")
    }

    // MARK: - RetryPolicy None Configuration Tests

    func testNonePolicy_MaxAttemptsIs1() {
        // Given/When
        let sut = RetryPolicy.none

        // Then
        XCTAssertEqual(sut.maxAttempts, 1, "None policy should allow only 1 attempt")
    }

    func testNonePolicy_NoRetryableStatusCodes() {
        // Given
        let sut = RetryPolicy.none

        // Then - Should not retry any status codes
        XCTAssertFalse(sut.shouldRetry(statusCode: 408))
        XCTAssertFalse(sut.shouldRetry(statusCode: 429))
        XCTAssertFalse(sut.shouldRetry(statusCode: 500))
        XCTAssertFalse(sut.shouldRetry(statusCode: 502))
        XCTAssertFalse(sut.shouldRetry(statusCode: 503))
        XCTAssertFalse(sut.shouldRetry(statusCode: 504))
    }

    func testNonePolicy_NoRetryableErrors() {
        // Given
        let sut = RetryPolicy.none

        // Then - Should not retry any errors
        XCTAssertFalse(sut.shouldRetry(error: URLError(.timedOut)))
        XCTAssertFalse(sut.shouldRetry(error: URLError(.networkConnectionLost)))
        XCTAssertFalse(sut.shouldRetry(error: URLError(.notConnectedToInternet)))
    }

    func testNonePolicy_ZeroDelay() {
        // Given
        let sut = RetryPolicy.none

        // Then
        XCTAssertEqual(sut.delay(for: 1), 0.0, "None policy should have zero delay")
        XCTAssertEqual(sut.delay(for: 2), 0.0, "None policy should have zero delay")
    }

    // MARK: - RetryPolicy Custom Configuration Tests

    func testCustomPolicy_CustomMaxAttempts() {
        // Given
        let sut = RetryPolicy(
            maxAttempts: 5,
            retryableStatusCodes: [],
            retryableErrors: [],
            delayCalculator: { _ in 0 }
        )

        // Then
        XCTAssertEqual(sut.maxAttempts, 5, "Should use custom max attempts")
    }

    func testCustomPolicy_CustomRetryableStatusCodes() {
        // Given
        let customCodes: Set<Int> = [418, 451] // I'm a teapot, Unavailable For Legal Reasons
        let sut = RetryPolicy(
            maxAttempts: 1,
            retryableStatusCodes: customCodes,
            retryableErrors: [],
            delayCalculator: { _ in 0 }
        )

        // Then
        XCTAssertTrue(sut.shouldRetry(statusCode: 418), "Should retry custom status code 418")
        XCTAssertTrue(sut.shouldRetry(statusCode: 451), "Should retry custom status code 451")
        XCTAssertFalse(sut.shouldRetry(statusCode: 500), "Should not retry non-custom status code 500")
    }

    func testCustomPolicy_CustomRetryableErrors() {
        // Given
        let customErrors: Set<URLError.Code> = [.dataNotAllowed, .internationalRoamingOff]
        let sut = RetryPolicy(
            maxAttempts: 1,
            retryableStatusCodes: [],
            retryableErrors: customErrors,
            delayCalculator: { _ in 0 }
        )

        // Then
        XCTAssertTrue(sut.shouldRetry(error: URLError(.dataNotAllowed)), "Should retry custom error")
        XCTAssertTrue(sut.shouldRetry(error: URLError(.internationalRoamingOff)), "Should retry custom error")
        XCTAssertFalse(sut.shouldRetry(error: URLError(.timedOut)), "Should not retry non-custom error")
    }

    func testCustomPolicy_CustomDelayCalculator() {
        // Given - Linear backoff instead of exponential
        let sut = RetryPolicy(
            maxAttempts: 3,
            retryableStatusCodes: [],
            retryableErrors: [],
            delayCalculator: { attempt in
                Double(attempt) * 0.5 // 0.5s, 1.0s, 1.5s
            }
        )

        // Then
        XCTAssertEqual(sut.delay(for: 1), 0.5, accuracy: 0.001, "Should use custom delay calculator")
        XCTAssertEqual(sut.delay(for: 2), 1.0, accuracy: 0.001, "Should use custom delay calculator")
        XCTAssertEqual(sut.delay(for: 3), 1.5, accuracy: 0.001, "Should use custom delay calculator")
    }

    // MARK: - RetryPolicy Edge Cases

    func testEdgeCase_DelayForAttemptZero() {
        // Given
        let sut = RetryPolicy.default

        // When
        let delay = sut.delay(for: 0)

        // Then - 2^(0-1) = 2^(-1) = 0.5
        XCTAssertEqual(delay, 0.5, accuracy: 0.001, "Attempt 0 should calculate delay correctly")
    }

    func testEdgeCase_DelayForNegativeAttempt() {
        // Given
        let sut = RetryPolicy.default

        // When
        let delay = sut.delay(for: -1)

        // Then - 2^(-1-1) = 2^(-2) = 0.25
        XCTAssertEqual(delay, 0.25, accuracy: 0.001, "Negative attempt should calculate delay correctly")
    }

    func testEdgeCase_DelayForVeryLargeAttempt() {
        // Given
        let sut = RetryPolicy.default

        // When - Test large attempt number (potential overflow)
        let delay = sut.delay(for: 20)

        // Then - 2^(20-1) = 2^19 = 524288 seconds (~6 days)
        XCTAssertEqual(delay, 524_288.0, accuracy: 1.0, "Large attempt should calculate delay without overflow")
        XCTAssertGreaterThan(delay, 0, "Delay should be positive")
        XCTAssertFalse(delay.isInfinite, "Delay should not be infinite")
        XCTAssertFalse(delay.isNaN, "Delay should not be NaN")
    }

    func testEdgeCase_DelayForExtremelyLargeAttempt() {
        // Given
        let sut = RetryPolicy.default

        // When - Test attempt that could cause overflow
        let delay = sut.delay(for: 100)

        // Then - 2^99 is very large but Double can represent it
        XCTAssertGreaterThan(delay, 0, "Delay should be positive even for extreme attempts")
        XCTAssertFalse(delay.isNaN, "Delay should not be NaN")
        // Note: This may be infinite due to Double limits, which is acceptable edge case
    }

    func testEdgeCase_EmptyRetryableSets() {
        // Given
        let sut = RetryPolicy(
            maxAttempts: 3,
            retryableStatusCodes: [],
            retryableErrors: [],
            delayCalculator: { _ in 1.0 }
        )

        // Then - Should not retry anything
        XCTAssertFalse(sut.shouldRetry(statusCode: 500))
        XCTAssertFalse(sut.shouldRetry(error: URLError(.timedOut)))
    }

    func testEdgeCase_ZeroMaxAttempts() {
        // Given - Policy that allows zero attempts (edge case configuration)
        let sut = RetryPolicy(
            maxAttempts: 0,
            retryableStatusCodes: [500],
            retryableErrors: [.timedOut],
            delayCalculator: { _ in 1.0 }
        )

        // Then - Configuration should be preserved
        XCTAssertEqual(sut.maxAttempts, 0, "Should allow zero max attempts configuration")
        // Note: RetryExecutor behavior with maxAttempts=0 will be tested separately
    }

    // MARK: - RetryExecutor Success Tests

    func testExecute_SuccessfulOperation_ReturnsImmediately() async throws {
        // Given
        let sut = RetryExecutor(policy: .default)
        let expectedResult = "success"
        var callCount = 0

        let operation = {
            callCount += 1
            let response = HTTPURLResponse(
                url: URL(string: "https://example.com")!,
                statusCode: 200,
                httpVersion: nil,
                headerFields: nil
            )!
            return (expectedResult, response)
        }

        // When
        let result = try await sut.execute(operation)

        // Then
        XCTAssertEqual(result, expectedResult, "Should return successful result")
        XCTAssertEqual(callCount, 1, "Should only call operation once on success")
    }

    func testExecute_SuccessfulOperationWithComplexType() async throws {
        // Given
        struct TestData: Equatable {
            let id: Int
            let name: String
        }

        let sut = RetryExecutor(policy: .default)
        let expectedResult = TestData(id: 1, name: "Test")

        let operation = {
            let response = HTTPURLResponse(
                url: URL(string: "https://example.com")!,
                statusCode: 200,
                httpVersion: nil,
                headerFields: nil
            )!
            return (expectedResult, response)
        }

        // When
        let result = try await sut.execute(operation)

        // Then
        XCTAssertEqual(result, expectedResult, "Should return complex type result")
    }

    // MARK: - RetryExecutor Retry on Status Code Tests

    func testExecute_RetryableStatusCode_RetriesUntilSuccess() async throws {
        // Given
        let sut = RetryExecutor(policy: .default)
        var callCount = 0
        let expectedResult = "success"

        let operation = {
            callCount += 1
            let statusCode = callCount < 3 ? 503 : 200 // Fail twice, succeed on third
            let response = HTTPURLResponse(
                url: URL(string: "https://example.com")!,
                statusCode: statusCode,
                httpVersion: nil,
                headerFields: nil
            )!
            return (expectedResult, response)
        }

        // When
        let result = try await sut.execute(operation)

        // Then
        XCTAssertEqual(result, expectedResult, "Should eventually succeed")
        XCTAssertEqual(callCount, 3, "Should retry twice (3 total attempts)")
    }

    func testExecute_RetryableStatusCode_ExhaustsMaxAttempts() async throws {
        // Given
        let sut = RetryExecutor(policy: .default)
        var callCount = 0
        let expectedResult = "result"

        let operation = {
            callCount += 1
            let response = HTTPURLResponse(
                url: URL(string: "https://example.com")!,
                statusCode: 503, // Always fail
                httpVersion: nil,
                headerFields: nil
            )!
            return (expectedResult, response)
        }

        // When
        let result = try await sut.execute(operation)

        // Then - Should return result even with retryable status code after max attempts
        XCTAssertEqual(result, expectedResult, "Should return result after exhausting retries")
        XCTAssertEqual(callCount, 3, "Should attempt maxAttempts times")
    }

    func testExecute_NonRetryableStatusCode_NoRetry() async throws {
        // Given
        let sut = RetryExecutor(policy: .default)
        var callCount = 0
        let expectedResult = "result"

        let operation = {
            callCount += 1
            let response = HTTPURLResponse(
                url: URL(string: "https://example.com")!,
                statusCode: 404, // Non-retryable
                httpVersion: nil,
                headerFields: nil
            )!
            return (expectedResult, response)
        }

        // When
        let result = try await sut.execute(operation)

        // Then
        XCTAssertEqual(result, expectedResult, "Should return result immediately")
        XCTAssertEqual(callCount, 1, "Should not retry non-retryable status code")
    }

    func testExecute_MixedStatusCodes_StopsRetryingOnSuccess() async throws {
        // Given
        let sut = RetryExecutor(policy: .default)
        var callCount = 0
        let expectedResult = "success"

        let operation = {
            callCount += 1
            // 503, 200 - should stop after second attempt
            let statusCode = callCount == 1 ? 503 : 200
            let response = HTTPURLResponse(
                url: URL(string: "https://example.com")!,
                statusCode: statusCode,
                httpVersion: nil,
                headerFields: nil
            )!
            return (expectedResult, response)
        }

        // When
        let result = try await sut.execute(operation)

        // Then
        XCTAssertEqual(result, expectedResult, "Should return successful result")
        XCTAssertEqual(callCount, 2, "Should stop retrying after success")
    }

    // MARK: - RetryExecutor Retry on Error Tests

    func testExecute_RetryableError_RetriesUntilSuccess() async throws {
        // Given
        let sut = RetryExecutor(policy: .default)
        var callCount = 0
        let expectedResult = "success"

        let operation = {
            callCount += 1
            if callCount < 3 {
                throw URLError(.timedOut) // Fail twice
            }
            let response = HTTPURLResponse(
                url: URL(string: "https://example.com")!,
                statusCode: 200,
                httpVersion: nil,
                headerFields: nil
            )!
            return (expectedResult, response)
        }

        // When
        let result = try await sut.execute(operation)

        // Then
        XCTAssertEqual(result, expectedResult, "Should eventually succeed after retries")
        XCTAssertEqual(callCount, 3, "Should retry twice (3 total attempts)")
    }

    func testExecute_RetryableError_ExhaustsMaxAttempts() async throws {
        // Given
        let sut = RetryExecutor(policy: .default)
        var callCount = 0

        let operation = { () -> (String, HTTPURLResponse) in
            callCount += 1
            throw URLError(.timedOut) // Always fail
        }

        // When/Then
        do {
            _ = try await sut.execute(operation)
            XCTFail("Should throw error after exhausting retries")
        } catch let error as URLError {
            XCTAssertEqual(error.code, .timedOut, "Should propagate the last error")
            XCTAssertEqual(callCount, 3, "Should attempt maxAttempts times")
        } catch {
            XCTFail("Should throw URLError, got \(error)")
        }
    }

    func testExecute_NonRetryableError_ThrowsImmediately() async throws {
        // Given
        let sut = RetryExecutor(policy: .default)
        var callCount = 0

        let operation = { () -> (String, HTTPURLResponse) in
            callCount += 1
            throw URLError(.badURL) // Non-retryable
        }

        // When/Then
        do {
            _ = try await sut.execute(operation)
            XCTFail("Should throw error immediately")
        } catch let error as URLError {
            XCTAssertEqual(error.code, .badURL, "Should propagate non-retryable error")
            XCTAssertEqual(callCount, 1, "Should not retry non-retryable error")
        } catch {
            XCTFail("Should throw URLError, got \(error)")
        }
    }

    func testExecute_NonURLError_ThrowsImmediately() async throws {
        // Given
        struct CustomError: Error, Equatable {}
        let sut = RetryExecutor(policy: .default)
        var callCount = 0

        let operation = { () -> (String, HTTPURLResponse) in
            callCount += 1
            throw CustomError()
        }

        // When/Then
        do {
            _ = try await sut.execute(operation)
            XCTFail("Should throw error immediately")
        } catch is CustomError {
            XCTAssertEqual(callCount, 1, "Should not retry non-URLError")
        } catch {
            XCTFail("Should throw CustomError, got \(error)")
        }
    }

    func testExecute_MixedErrors_StopsRetryingOnSuccess() async throws {
        // Given
        let sut = RetryExecutor(policy: .default)
        var callCount = 0
        let expectedResult = "success"

        let operation = {
            callCount += 1
            if callCount == 1 {
                throw URLError(.networkConnectionLost) // First attempt fails
            }
            let response = HTTPURLResponse(
                url: URL(string: "https://example.com")!,
                statusCode: 200,
                httpVersion: nil,
                headerFields: nil
            )!
            return (expectedResult, response)
        }

        // When
        let result = try await sut.execute(operation)

        // Then
        XCTAssertEqual(result, expectedResult, "Should succeed after retry")
        XCTAssertEqual(callCount, 2, "Should stop retrying after success")
    }

    // MARK: - RetryExecutor Edge Cases

    func testExecute_NonePolicy_NoRetryOnError() async throws {
        // Given
        let sut = RetryExecutor(policy: .none)
        var callCount = 0

        let operation = { () -> (String, HTTPURLResponse) in
            callCount += 1
            throw URLError(.timedOut)
        }

        // When/Then
        do {
            _ = try await sut.execute(operation)
            XCTFail("Should throw error immediately")
        } catch is URLError {
            XCTAssertEqual(callCount, 1, "None policy should not retry")
        } catch {
            XCTFail("Should throw URLError")
        }
    }

    func testExecute_NonePolicy_NoRetryOnStatusCode() async throws {
        // Given
        let sut = RetryExecutor(policy: .none)
        var callCount = 0

        let operation = {
            callCount += 1
            let response = HTTPURLResponse(
                url: URL(string: "https://example.com")!,
                statusCode: 503,
                httpVersion: nil,
                headerFields: nil
            )!
            return ("result", response)
        }

        // When
        let result = try await sut.execute(operation)

        // Then
        XCTAssertEqual(result, "result", "Should return result immediately")
        XCTAssertEqual(callCount, 1, "None policy should not retry")
    }

    func testExecute_CustomPolicy_RespectsCustomMaxAttempts() async throws {
        // Given - Custom policy with 5 max attempts
        let customPolicy = RetryPolicy(
            maxAttempts: 5,
            retryableStatusCodes: [503],
            retryableErrors: [],
            delayCalculator: { _ in 0 } // No delay for faster tests
        )
        let sut = RetryExecutor(policy: customPolicy)
        var callCount = 0

        let operation = {
            callCount += 1
            let response = HTTPURLResponse(
                url: URL(string: "https://example.com")!,
                statusCode: 503,
                httpVersion: nil,
                headerFields: nil
            )!
            return ("result", response)
        }

        // When
        _ = try await sut.execute(operation)

        // Then
        XCTAssertEqual(callCount, 5, "Should respect custom maxAttempts")
    }

    func testExecute_CustomPolicy_OnlyRetriesCustomErrors() async throws {
        // Given - Custom policy that only retries .dataNotAllowed
        let customPolicy = RetryPolicy(
            maxAttempts: 3,
            retryableStatusCodes: [],
            retryableErrors: [.dataNotAllowed],
            delayCalculator: { _ in 0 }
        )
        let sut = RetryExecutor(policy: customPolicy)
        var callCount = 0

        let operation = { () -> (String, HTTPURLResponse) in
            callCount += 1
            throw URLError(.timedOut) // Not in custom retryable set
        }

        // When/Then
        do {
            _ = try await sut.execute(operation)
            XCTFail("Should throw error immediately")
        } catch {
            XCTAssertEqual(callCount, 1, "Should not retry non-custom error")
        }
    }

    func testExecute_AlternatingErrorsAndStatusCodes() async throws {
        // Given
        let sut = RetryExecutor(policy: .default)
        var callCount = 0
        let expectedResult = "success"

        let operation = {
            callCount += 1
            switch callCount {
            case 1:
                throw URLError(.timedOut) // First: retryable error
            case 2:
                // Second: retryable status code
                let response = HTTPURLResponse(
                    url: URL(string: "https://example.com")!,
                    statusCode: 503,
                    httpVersion: nil,
                    headerFields: nil
                )!
                return (expectedResult, response)
            default:
                // Third: success
                let response = HTTPURLResponse(
                    url: URL(string: "https://example.com")!,
                    statusCode: 200,
                    httpVersion: nil,
                    headerFields: nil
                )!
                return (expectedResult, response)
            }
        }

        // When
        let result = try await sut.execute(operation)

        // Then
        XCTAssertEqual(result, expectedResult, "Should succeed after mixed retries")
        XCTAssertEqual(callCount, 3, "Should retry through different failure types")
    }

    func testExecute_MaxAttemptsEqualToOne_NoRetry() async throws {
        // Given
        let policy = RetryPolicy(
            maxAttempts: 1,
            retryableStatusCodes: [503],
            retryableErrors: [.timedOut],
            delayCalculator: { _ in 0 }
        )
        let sut = RetryExecutor(policy: policy)
        var callCount = 0

        let operation = { () -> (String, HTTPURLResponse) in
            callCount += 1
            throw URLError(.timedOut)
        }

        // When/Then
        do {
            _ = try await sut.execute(operation)
            XCTFail("Should throw error")
        } catch {
            XCTAssertEqual(callCount, 1, "Should only attempt once when maxAttempts is 1")
        }
    }

    // MARK: - RetryExecutor Delay Verification Tests

    // Note: We verify delays are calculated correctly, not that actual time passes

    func testExecute_CalculatesCorrectDelays() async throws {
        // Given - Custom policy with predictable delays for verification
        var calculatedDelays: [TimeInterval] = []
        let policy = RetryPolicy(
            maxAttempts: 3,
            retryableStatusCodes: [503],
            retryableErrors: [],
            delayCalculator: { attempt in
                let delay = Double(attempt) * 0.1
                calculatedDelays.append(delay)
                return delay
            }
        )
        let sut = RetryExecutor(policy: policy)

        let operation = {
            let response = HTTPURLResponse(
                url: URL(string: "https://example.com")!,
                statusCode: 503,
                httpVersion: nil,
                headerFields: nil
            )!
            return ("result", response)
        }

        // When
        _ = try await sut.execute(operation)

        // Then - Verify delays were calculated for attempts 1 and 2 (not 3, as it's the last)
        XCTAssertEqual(calculatedDelays.count, 2, "Should calculate delay for first 2 attempts")
        XCTAssertEqual(calculatedDelays[0], 0.1, accuracy: 0.001, "First retry delay")
        XCTAssertEqual(calculatedDelays[1], 0.2, accuracy: 0.001, "Second retry delay")
    }

    func testExecute_DoesNotDelayOnLastAttempt() async throws {
        // Given
        var delayCallCount = 0
        let policy = RetryPolicy(
            maxAttempts: 2,
            retryableStatusCodes: [503],
            retryableErrors: [],
            delayCalculator: { _ in
                delayCallCount += 1
                return 0.01
            }
        )
        let sut = RetryExecutor(policy: policy)

        let operation = {
            let response = HTTPURLResponse(
                url: URL(string: "https://example.com")!,
                statusCode: 503,
                httpVersion: nil,
                headerFields: nil
            )!
            return ("result", response)
        }

        // When
        _ = try await sut.execute(operation)

        // Then - Should only calculate delay once (between attempt 1 and 2, not after attempt 2)
        XCTAssertEqual(delayCallCount, 1, "Should only delay between attempts, not after last")
    }

    func testExecute_NoDelayOnFirstAttempt() async throws {
        // Given
        var delayCallCount = 0
        let policy = RetryPolicy(
            maxAttempts: 3,
            retryableStatusCodes: [],
            retryableErrors: [],
            delayCalculator: { _ in
                delayCallCount += 1
                return 0.01
            }
        )
        let sut = RetryExecutor(policy: policy)

        let operation = {
            let response = HTTPURLResponse(
                url: URL(string: "https://example.com")!,
                statusCode: 200,
                httpVersion: nil,
                headerFields: nil
            )!
            return ("success", response)
        }

        // When
        _ = try await sut.execute(operation)

        // Then
        XCTAssertEqual(delayCallCount, 0, "Should not calculate delay on immediate success")
    }
}
