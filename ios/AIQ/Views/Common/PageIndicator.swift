import SwiftUI

/// A custom page indicator component that displays dots for pagination
///
/// This component provides an alternative to the global `UIPageControl.appearance()` styling,
/// allowing scoped customization without affecting other TabViews in the app.
///
/// ## Usage
/// ```swift
/// PageIndicator(
///     currentPage: $currentPage,
///     totalPages: 4
/// )
/// ```
///
/// ## Design Notes
/// - Active dot uses `ColorPalette.primary`
/// - Inactive dots use `ColorPalette.textSecondary` (WCAG AA compliant with 4.5:1 contrast)
/// - Dots are 8pt diameter with 8pt spacing (matching UIPageControl)
/// - Includes smooth animation on page changes
struct PageIndicator: View {
    /// The current page index (0-based)
    @Binding var currentPage: Int

    /// Total number of pages
    let totalPages: Int

    /// Dot diameter
    private let dotSize: CGFloat = 8

    /// Spacing between dots
    private let dotSpacing: CGFloat = 8

    /// Validated total pages (minimum 1)
    private var validTotalPages: Int {
        max(1, totalPages)
    }

    /// Validated current page (clamped to valid range)
    private var validCurrentPage: Int {
        max(0, min(currentPage, validTotalPages - 1))
    }

    var body: some View {
        HStack(spacing: dotSpacing) {
            ForEach(0 ..< validTotalPages, id: \.self) { index in
                Circle()
                    .fill(index == validCurrentPage ? ColorPalette.primary : ColorPalette.textSecondary)
                    .frame(width: dotSize, height: dotSize)
                    .animation(.easeInOut(duration: 0.2), value: validCurrentPage)
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Page \(validCurrentPage + 1) of \(validTotalPages)")
        .accessibilityIdentifier(AccessibilityIdentifiers.PageIndicator.container)
    }
}

#Preview {
    VStack(spacing: 20) {
        PageIndicator(currentPage: .constant(0), totalPages: 4)
        PageIndicator(currentPage: .constant(1), totalPages: 4)
        PageIndicator(currentPage: .constant(2), totalPages: 4)
        PageIndicator(currentPage: .constant(3), totalPages: 4)
    }
    .padding()
}
