import SwiftUI

public extension View {
    /// Hide the keyboard (iOS only; no-op on other platforms)
    func hideKeyboard() {
        #if canImport(UIKit)
            UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil)
        #endif
    }

    /// Add a border with rounded corners
    func roundedBorder(
        color: Color = Color(.systemGray4),
        lineWidth: CGFloat = 1,
        cornerRadius: CGFloat = 10
    ) -> some View {
        overlay(
            RoundedRectangle(cornerRadius: cornerRadius)
                .stroke(color, lineWidth: lineWidth)
        )
    }

    /// Conditionally apply a modifier
    @ViewBuilder
    func `if`(_ condition: Bool, transform: (Self) -> some View) -> some View {
        if condition {
            transform(self)
        } else {
            self
        }
    }
}
