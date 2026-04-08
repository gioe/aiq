@testable import SharedKit
import UIKit
import XCTest

/// Unit tests for `ScreenshotContainerView.intrinsicContentSize` sizing behaviour.
///
/// Covers the bounds=0 → layout overflow regression fixed in TASK-286:
/// the view must cache the last real layout width and use it during animation
/// frames where bounds are temporarily zero, rather than falling back to
/// `UIView.noIntrinsicMetric` or an incorrect placeholder width of 1.
@MainActor
final class ScreenshotContainerViewTests: XCTestCase {
    // MARK: - intrinsicContentSize before any layout

    /// Criterion 907: When `bounds.width == 0` and no real width has ever been laid out,
    /// `intrinsicContentSize` must return `UIView.noIntrinsicMetric` on both axes so that
    /// external Auto Layout constraints can size the view without interference.
    func testIntrinsicContentSize_returnsNoIntrinsicMetric_whenBoundsAndCacheAreZero() {
        // Given: a fresh view with a provider but no frame (bounds.width == 0, _lastValidWidth == 0)
        let view = ScreenshotContainerView()
        var providerCallCount = 0
        view.preferredSizeProvider = { size in
            providerCallCount += 1
            return CGSize(width: size.width, height: 50)
        }

        // When
        let size = view.intrinsicContentSize

        // Then
        XCTAssertEqual(
            size.width,
            UIView.noIntrinsicMetric,
            "width should be noIntrinsicMetric before any real layout"
        )
        XCTAssertEqual(
            size.height,
            UIView.noIntrinsicMetric,
            "height should be noIntrinsicMetric before any real layout"
        )
        XCTAssertEqual(
            providerCallCount,
            0,
            "preferredSizeProvider must not be called when there is no valid width"
        )
    }

    // MARK: - layoutSubviews caches _lastValidWidth

    /// Criterion 908: After `layoutSubviews` runs with a real width, `_lastValidWidth`
    /// is set. A subsequent call to `intrinsicContentSize` while `bounds.width == 0`
    /// (e.g. during a collapse animation) must use the cached width, not return
    /// `noIntrinsicMetric`.
    func testIntrinsicContentSize_usesCachedWidth_whenBoundsTemporarilyCollapsedToZero() {
        // Given
        let realWidth: CGFloat = 320
        let view = ScreenshotContainerView()
        var providerCallCount = 0
        view.preferredSizeProvider = { size in
            providerCallCount += 1
            return CGSize(width: size.width, height: 50)
        }

        // Establish a real layout pass so _lastValidWidth is cached.
        view.frame = CGRect(x: 0, y: 0, width: realWidth, height: 100)
        view.layoutSubviews()

        // Simulate an animation frame where bounds collapse to zero.
        view.frame = .zero

        // When
        let size = view.intrinsicContentSize

        // Then: provider was called and returned a real height; width stays noIntrinsicMetric
        // because intrinsicContentSize defers horizontal sizing to SwiftUI.
        XCTAssertEqual(providerCallCount, 1, "preferredSizeProvider should be called when a cached width is available")
        XCTAssertEqual(
            size.width,
            UIView.noIntrinsicMetric,
            "width should be noIntrinsicMetric (SwiftUI controls horizontal sizing)"
        )
        XCTAssertNotEqual(
            size.height,
            UIView.noIntrinsicMetric,
            "height should not be noIntrinsicMetric when a cached width exists"
        )
    }

    // MARK: - preferredSizeProvider width correctness

    /// Criterion 909: When a cached width is available and `bounds.width == 0`,
    /// `preferredSizeProvider` must be called with the real cached width — never with
    /// the placeholder value of `1` that the pre-TASK-286 fallback used.
    func testPreferredSizeProvider_neverCalledWithWidth1_whenCachedWidthExists() {
        // Given
        let realWidth: CGFloat = 414
        let view = ScreenshotContainerView()
        var recordedWidths: [CGFloat] = []
        view.preferredSizeProvider = { size in
            recordedWidths.append(size.width)
            return CGSize(width: size.width, height: 60)
        }

        view.frame = CGRect(x: 0, y: 0, width: realWidth, height: 100)
        view.layoutSubviews()
        view.frame = .zero // collapse bounds

        // When
        _ = view.intrinsicContentSize

        // Then
        XCTAssertFalse(
            recordedWidths.contains(1),
            "preferredSizeProvider must never be called with width=1 when a cached real width exists"
        )
        XCTAssertEqual(
            recordedWidths.first,
            realWidth,
            "preferredSizeProvider should be called with the cached real width (\(realWidth))"
        )
    }

    /// Supplementary: when `bounds.width > 0` AND `layoutSubviews` has cached the width,
    /// `preferredSizeProvider` is called with the cached width and `intrinsicContentSize`
    /// reports only the height (width stays `noIntrinsicMetric` so SwiftUI controls horizontal sizing).
    func testIntrinsicContentSize_usesBoundsWidth_whenBoundsWidthIsPositive() {
        // Given
        let boundsWidth: CGFloat = 375
        let view = ScreenshotContainerView()
        var recordedWidths: [CGFloat] = []
        view.preferredSizeProvider = { size in
            recordedWidths.append(size.width)
            return CGSize(width: size.width, height: 44)
        }

        view.frame = CGRect(x: 0, y: 0, width: boundsWidth, height: 100)
        view.layoutSubviews() // Cache _lastValidWidth so intrinsicContentSize uses it

        // When
        let size = view.intrinsicContentSize

        // Then
        XCTAssertEqual(
            recordedWidths.first,
            boundsWidth,
            "preferredSizeProvider should receive the cached bounds.width"
        )
        // intrinsicContentSize returns noIntrinsicMetric for width (SwiftUI controls horizontal sizing)
        XCTAssertEqual(size.width, UIView.noIntrinsicMetric, "intrinsicContentSize.width should be noIntrinsicMetric")
        XCTAssertEqual(size.height, 44)
    }

    // MARK: - preferredSizeProvider == nil

    /// When no `preferredSizeProvider` is set, `intrinsicContentSize` must delegate to
    /// `super.intrinsicContentSize`, which returns `UIView.noIntrinsicMetric` on both axes
    /// for a plain `UIView` with no explicit size constraints.
    func testIntrinsicContentSize_delegatesToSuper_whenProviderIsNil() {
        // Given
        let view = ScreenshotContainerView()
        // No preferredSizeProvider assigned.

        // When
        let size = view.intrinsicContentSize

        // Then
        XCTAssertEqual(
            size.width,
            UIView.noIntrinsicMetric,
            "width should be noIntrinsicMetric when no provider is set"
        )
        XCTAssertEqual(
            size.height,
            UIView.noIntrinsicMetric,
            "height should be noIntrinsicMetric when no provider is set"
        )
    }

    // MARK: - sizeThatFits (UIView override)

    /// Criterion: When no `preferredSizeProvider` is set, `sizeThatFits` must delegate to
    /// `super.sizeThatFits(_:)`, which for an unframed `UIView` returns `bounds.size` (`.zero`).
    func testSizeThatFits_delegatesToSuper_whenProviderIsNil() {
        // Given: a fresh view with no frame and no provider
        let view = ScreenshotContainerView()
        // No preferredSizeProvider assigned.

        // When
        let size = view.sizeThatFits(CGSize(width: 200, height: 10000))

        // Then: super.sizeThatFits returns bounds.size, which is .zero for an unframed view
        XCTAssertEqual(
            size,
            .zero,
            "sizeThatFits should delegate to super (returning bounds.size == .zero) when no provider is set"
        )
    }

    /// Criterion: When a `preferredSizeProvider` is set, `sizeThatFits` must forward the exact
    /// target size to the provider and return the provider's result.
    func testSizeThatFits_forwardsToProvider_whenProviderIsSet() {
        // Given
        let view = ScreenshotContainerView()
        let targetSize = CGSize(width: 375, height: 10000)
        let expectedResult = CGSize(width: 375, height: 88)
        var capturedSize: CGSize?
        view.preferredSizeProvider = { size in
            capturedSize = size
            return expectedResult
        }

        // When
        let result = view.sizeThatFits(targetSize)

        // Then
        XCTAssertEqual(
            capturedSize,
            targetSize,
            "sizeThatFits should forward the exact target size to preferredSizeProvider"
        )
        XCTAssertEqual(result, expectedResult, "sizeThatFits should return the provider's result")
    }

    // MARK: - lastValidWidth

    /// Criterion: A freshly created `ScreenshotContainerView` with no layout pass has
    /// `lastValidWidth == 0` because `layoutSubviews` has never run with a positive width.
    func testLastValidWidth_isZero_beforeAnyLayout() {
        // Given
        let view = ScreenshotContainerView()

        // When / Then
        XCTAssertEqual(view.lastValidWidth, 0, "lastValidWidth should be zero before any layout pass")
    }

    /// Criterion: After a layout pass with a positive frame width, `lastValidWidth` must
    /// reflect that width.
    func testLastValidWidth_updatesAfterLayoutSubviews() {
        // Given
        let view = ScreenshotContainerView()
        let realWidth: CGFloat = 300

        // When
        view.frame = CGRect(x: 0, y: 0, width: realWidth, height: 100)
        view.layoutSubviews()

        // Then
        XCTAssertEqual(
            view.lastValidWidth,
            realWidth,
            "lastValidWidth should equal the frame width after layoutSubviews"
        )
    }

    /// Criterion: After a real layout pass, collapsing the frame to `.zero` and calling
    /// `layoutSubviews` again must NOT overwrite the cached width — `lastValidWidth` must
    /// retain the previously recorded real width.
    func testLastValidWidth_retainsValue_whenBoundsCollapseToZero() {
        // Given
        let realWidth: CGFloat = 414
        let view = ScreenshotContainerView()
        view.frame = CGRect(x: 0, y: 0, width: realWidth, height: 100)
        view.layoutSubviews()

        // When: bounds collapse to zero (e.g. during a dismiss animation)
        view.frame = .zero
        view.layoutSubviews()

        // Then: the cached width from the earlier real layout is preserved
        XCTAssertEqual(
            view.lastValidWidth,
            realWidth,
            "lastValidWidth should retain the last real width when bounds subsequently collapse to zero"
        )
    }
}
