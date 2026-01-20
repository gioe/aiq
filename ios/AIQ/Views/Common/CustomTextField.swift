import SwiftUI

/// A reusable styled text field with consistent appearance
struct CustomTextField: View {
    let title: String
    let placeholder: String
    @Binding var text: String
    var isSecure: Bool = false
    var keyboardType: UIKeyboardType = .default
    var autocapitalization: TextInputAutocapitalization = .sentences
    var accessibilityId: String?
    var submitLabel: SubmitLabel = .return
    var onSubmit: (() -> Void)?

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.subheadline)
                .fontWeight(.medium)
                .foregroundColor(.primary)
                .accessibilityHidden(true) // Hide label as it's redundant with field label

            Group {
                if isSecure {
                    SecureField(placeholder, text: $text)
                        .submitLabel(submitLabel)
                        .onSubmit { onSubmit?() }
                        .accessibilityLabel(title)
                        .accessibilityValue(text.isEmpty ? "Empty" : "Entered")
                        .accessibilityHint("Secure text field. Double tap to edit")
                        .optionalAccessibilityIdentifier(accessibilityId)
                } else {
                    TextField(placeholder, text: $text)
                        .keyboardType(keyboardType)
                        .textInputAutocapitalization(autocapitalization)
                        .submitLabel(submitLabel)
                        .onSubmit { onSubmit?() }
                        .accessibilityLabel(title)
                        .accessibilityValue(text.isEmpty ? "Empty" : text)
                        .accessibilityHint("Text field. Double tap to edit")
                        .optionalAccessibilityIdentifier(accessibilityId)
                }
            }
            .padding()
            .background(Color(.systemGray6))
            .cornerRadius(10)
            .overlay(
                RoundedRectangle(cornerRadius: 10)
                    .stroke(Color(.systemGray4), lineWidth: 1)
            )
        }
    }
}

// MARK: - View Extension for Optional Accessibility Identifier

extension View {
    /// Applies an accessibility identifier only if the value is non-nil
    /// This prevents creating elements with empty identifiers
    @ViewBuilder
    func optionalAccessibilityIdentifier(_ identifier: String?) -> some View {
        if let identifier {
            accessibilityIdentifier(identifier)
        } else {
            self
        }
    }
}

#Preview {
    VStack(spacing: 20) {
        CustomTextField(
            title: "Email",
            placeholder: "Enter your email",
            text: .constant(""),
            keyboardType: .emailAddress,
            autocapitalization: .never
        )

        CustomTextField(
            title: "Password",
            placeholder: "Enter your password",
            text: .constant(""),
            isSecure: true
        )
    }
    .padding()
}
