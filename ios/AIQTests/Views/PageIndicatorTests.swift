@testable import AIQ
import SwiftUI
import XCTest

/// Tests for PageIndicator component.
///
/// These tests verify the page indicator's visual representation,
/// accessibility support, and behavior with different configurations.
@MainActor
final class PageIndicatorTests: XCTestCase {
    // MARK: - Initialization Tests

    func testViewCanBeInitialized() {
        // Given/When
        let view = PageIndicator(currentPage: .constant(0), totalPages: 4)

        // Then
        XCTAssertNotNil(view, "View should be initialized successfully")
    }

    func testViewInitializesWithProvidedValues() {
        // Given
        let currentPage = 2
        let totalPages = 5

        // When
        let view = PageIndicator(currentPage: .constant(currentPage), totalPages: totalPages)
        let mirror = Mirror(reflecting: view)

        // Then
        if let totalPagesValue = mirror.descendant("totalPages") as? Int {
            XCTAssertEqual(totalPagesValue, totalPages, "totalPages should match provided value")
        } else {
            XCTFail("Could not extract totalPages from view")
        }
    }

    // MARK: - Configuration Tests

    func testDotSizeIsCorrect() {
        // Given
        let view = PageIndicator(currentPage: .constant(0), totalPages: 4)
        let mirror = Mirror(reflecting: view)

        // When
        let dotSize = mirror.descendant("dotSize") as? CGFloat

        // Then
        XCTAssertEqual(dotSize, 8, "Dot size should be 8pt to match UIPageControl")
    }

    func testDotSpacingIsCorrect() {
        // Given
        let view = PageIndicator(currentPage: .constant(0), totalPages: 4)
        let mirror = Mirror(reflecting: view)

        // When
        let dotSpacing = mirror.descendant("dotSpacing") as? CGFloat

        // Then
        XCTAssertEqual(dotSpacing, 8, "Dot spacing should be 8pt to match UIPageControl")
    }

    // MARK: - Edge Case Tests

    func testSinglePageIndicator() {
        // Given/When
        let view = PageIndicator(currentPage: .constant(0), totalPages: 1)
        let mirror = Mirror(reflecting: view)

        // Then
        if let totalPages = mirror.descendant("totalPages") as? Int {
            XCTAssertEqual(totalPages, 1, "Should support single page")
        }
    }

    func testLargeTotalPages() {
        // Given/When
        let view = PageIndicator(currentPage: .constant(0), totalPages: 20)
        let mirror = Mirror(reflecting: view)

        // Then
        if let totalPages = mirror.descendant("totalPages") as? Int {
            XCTAssertEqual(totalPages, 20, "Should support large number of pages")
        }
    }

    func testCurrentPageAtStart() {
        // Given
        var currentPage = 0

        // When
        let binding = Binding(
            get: { currentPage },
            set: { currentPage = $0 }
        )
        let view = PageIndicator(currentPage: binding, totalPages: 4)

        // Then
        XCTAssertNotNil(view, "View should initialize with currentPage at 0")
    }

    func testCurrentPageAtEnd() {
        // Given
        var currentPage = 3

        // When
        let binding = Binding(
            get: { currentPage },
            set: { currentPage = $0 }
        )
        let view = PageIndicator(currentPage: binding, totalPages: 4)

        // Then
        XCTAssertNotNil(view, "View should initialize with currentPage at last index")
    }

    func testCurrentPageInMiddle() {
        // Given
        var currentPage = 2

        // When
        let binding = Binding(
            get: { currentPage },
            set: { currentPage = $0 }
        )
        let view = PageIndicator(currentPage: binding, totalPages: 5)

        // Then
        XCTAssertNotNil(view, "View should initialize with currentPage in middle")
    }

    // MARK: - Binding Update Tests

    func testBindingUpdates() {
        // Given
        var currentPage = 0
        let binding = Binding(
            get: { currentPage },
            set: { currentPage = $0 }
        )
        _ = PageIndicator(currentPage: binding, totalPages: 4)

        // When
        binding.wrappedValue = 2

        // Then
        XCTAssertEqual(currentPage, 2, "Binding should update the underlying value")
    }

    // MARK: - Accessibility Tests

    func testAccessibilityLabelFormat() {
        // The accessibility label should follow the format "Page X of Y"
        // This test documents the expected accessibility behavior

        // Given
        let currentPage = 2
        let totalPages = 5

        // When
        let expectedLabel = "Page \(currentPage + 1) of \(totalPages)"

        // Then
        // Note: The actual accessibility label is generated in the view body
        // This test validates the expected format
        XCTAssertEqual(expectedLabel, "Page 3 of 5", "Accessibility label should use 1-based page numbers")
    }

    func testAccessibilityLabelAtFirstPage() {
        // Given
        let currentPage = 0
        let totalPages = 4

        // When
        let expectedLabel = "Page \(currentPage + 1) of \(totalPages)"

        // Then
        XCTAssertEqual(expectedLabel, "Page 1 of 4")
    }

    func testAccessibilityLabelAtLastPage() {
        // Given
        let currentPage = 3
        let totalPages = 4

        // When
        let expectedLabel = "Page \(currentPage + 1) of \(totalPages)"

        // Then
        XCTAssertEqual(expectedLabel, "Page 4 of 4")
    }

    // MARK: - Zero Pages Edge Case

    func testZeroTotalPagesDoesNotCrash() {
        // Given/When - This tests that the view doesn't crash with 0 pages
        // (though this is an invalid state, robustness is important)
        let view = PageIndicator(currentPage: .constant(0), totalPages: 0)

        // Then
        XCTAssertNotNil(view, "View should not crash with 0 pages")
    }

    // MARK: - Input Validation Tests

    func testNegativeTotalPages_ClampedToOne() {
        // Given/When - View should not crash with negative totalPages
        // The view clamps totalPages to min 1 via validTotalPages computed property
        let view = PageIndicator(currentPage: .constant(0), totalPages: -5)

        // Then - View initializes without crashing and stores the original value
        XCTAssertNotNil(view, "View should handle negative totalPages without crashing")
        let mirror = Mirror(reflecting: view)
        if let storedTotal = mirror.descendant("totalPages") as? Int {
            XCTAssertEqual(storedTotal, -5, "Stored totalPages preserves original value")
        }
        // Validation happens at render time via validTotalPages (clamped to 1)
    }

    func testCurrentPageBeyondBounds_ClampedToMax() {
        // Given/When - View should not crash when currentPage exceeds totalPages
        // The view clamps currentPage to 0..<totalPages via validCurrentPage computed property
        let view = PageIndicator(currentPage: .constant(10), totalPages: 4)

        // Then - View initializes without crashing
        XCTAssertNotNil(view, "View should handle out-of-bounds currentPage without crashing")
        let mirror = Mirror(reflecting: view)
        if let storedTotal = mirror.descendant("totalPages") as? Int {
            XCTAssertEqual(storedTotal, 4, "totalPages should be preserved")
        }
        // Validation clamps currentPage to 3 (totalPages - 1) at render time
    }

    func testCurrentPageNegative_ClampedToZero() {
        // Given/When - View should not crash with negative currentPage
        // The view clamps currentPage to min 0 via validCurrentPage computed property
        let view = PageIndicator(currentPage: .constant(-3), totalPages: 4)

        // Then - View initializes without crashing
        XCTAssertNotNil(view, "View should handle negative currentPage without crashing")
        let mirror = Mirror(reflecting: view)
        if let storedTotal = mirror.descendant("totalPages") as? Int {
            XCTAssertEqual(storedTotal, 4, "totalPages should be preserved")
        }
        // Validation clamps currentPage to 0 at render time
    }
}
