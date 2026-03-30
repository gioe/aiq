@testable import APIClient
import Foundation
import XCTest

// MARK: - FlexibleISO8601DateTranscoderTests

//
// FlexibleISO8601DateTranscoder is internal; @testable import is required.
//
// The transcoder uses NSLock for thread-safety on ISO8601DateFormatter (which is
// not Sendable). Tests are single-threaded since the locking is an implementation
// detail, not a contract tested here.

final class FlexibleISO8601DateTranscoderTests: XCTestCase {
    private let transcoder = FlexibleISO8601DateTranscoder()

    // MARK: - Decode tests

    func testDecodeWithFractionalSeconds() throws {
        // Given — Pydantic/FastAPI microsecond-precision format
        let dateString = "2025-11-26T02:01:47.860855Z"

        // When
        let date = try transcoder.decode(dateString)

        // Then — verify date components in UTC
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = try XCTUnwrap(TimeZone(identifier: "UTC"))
        let components = calendar.dateComponents([.year, .month, .day, .hour, .minute, .second], from: date)

        XCTAssertEqual(components.year, 2025)
        XCTAssertEqual(components.month, 11)
        XCTAssertEqual(components.day, 26)
        XCTAssertEqual(components.hour, 2)
        XCTAssertEqual(components.minute, 1)
        XCTAssertEqual(components.second, 47)
    }

    func testDecodeWithoutFractionalSeconds() throws {
        // Given — standard ISO 8601 without fractional seconds
        let dateString = "2025-11-26T02:01:47Z"

        // When
        let date = try transcoder.decode(dateString)

        // Then — the result must be a valid date
        XCTAssertNotNil(date)

        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = try XCTUnwrap(TimeZone(identifier: "UTC"))
        let components = calendar.dateComponents([.year, .month, .day], from: date)

        XCTAssertEqual(components.year, 2025)
        XCTAssertEqual(components.month, 11)
        XCTAssertEqual(components.day, 26)
    }

    func testDecodeInvalidInputThrows() {
        // Given
        let invalidString = "not-a-date"

        // Then — a DecodingError.dataCorrupted must be thrown
        XCTAssertThrowsError(try transcoder.decode(invalidString)) { error in
            if case let DecodingError.dataCorrupted(context) = error {
                XCTAssertTrue(
                    context.debugDescription.contains("not-a-date"),
                    "Error description should include the invalid input"
                )
            } else {
                XCTFail("Expected DecodingError.dataCorrupted, got \(error)")
            }
        }
    }

    // MARK: - Encode tests

    func testEncodeProducesFractionalFormat() throws {
        // Given — a known fixed date
        var components = DateComponents()
        components.year = 2025
        components.month = 6
        components.day = 15
        components.hour = 12
        components.minute = 0
        components.second = 0
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = try XCTUnwrap(TimeZone(identifier: "UTC"))
        let date = try XCTUnwrap(calendar.date(from: components))

        // When
        let encoded = try transcoder.encode(date)

        // Then — the encoder always uses the fractional-seconds formatter
        XCTAssertTrue(
            encoded.contains("T"),
            "Encoded string '\(encoded)' should contain 'T' (ISO 8601 datetime separator)"
        )
        XCTAssertTrue(
            encoded.contains("."),
            "Encoded string '\(encoded)' should contain '.' (fractional seconds)"
        )
    }

    // MARK: - Round-trip test

    func testRoundTripWithFractionalSeconds() throws {
        // Given — a string the backend might return
        let original = "2025-11-26T02:01:47.860855Z"

        // When — decode then re-encode
        let decoded = try transcoder.decode(original)
        let reEncoded = try transcoder.encode(decoded)

        // Then — re-encoding must produce a valid ISO 8601 string with fractional seconds
        XCTAssertTrue(reEncoded.contains("T"))
        XCTAssertTrue(reEncoded.contains("."))
        // The re-encoded date should decode back to the same second (microseconds
        // may differ due to precision limits of Double/TimeInterval).
        let reDecoded = try transcoder.decode(reEncoded)
        XCTAssertEqual(
            decoded.timeIntervalSinceReferenceDate,
            reDecoded.timeIntervalSinceReferenceDate,
            accuracy: 0.001
        )
    }
}
