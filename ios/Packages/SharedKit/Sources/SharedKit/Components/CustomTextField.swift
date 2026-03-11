import SwiftUI

/// A reusable styled text field with consistent appearance
public struct CustomTextField: View {
    public let title: String
    public let placeholder: String
    @Binding public var text: String
    public var isSecure: Bool = false
    public var keyboardType: UIKeyboardType = .default
    public var autocapitalization: TextInputAutocapitalization = .sentences
    public var accessibilityId: String?
    public var submitLabel: SubmitLabel = .return
    public var onSubmit: (() -> Void)?

    @Environment(\.appTheme) private var theme

    public init(
        title: String,
        placeholder: String,
        text: Binding<String>,
        isSecure: Bool = false,
        keyboardType: UIKeyboardType = .default,
        autocapitalization: TextInputAutocapitalization = .sentences,
        accessibilityId: String? = nil,
        submitLabel: SubmitLabel = .return,
        onSubmit: (() -> Void)? = nil
    ) {
        self.title = title
        self.placeholder = placeholder
        _text = text
        self.isSecure = isSecure
        self.keyboardType = keyboardType
        self.autocapitalization = autocapitalization
        self.accessibilityId = accessibilityId
        self.submitLabel = submitLabel
        self.onSubmit = onSubmit
    }

    public var body: some View {
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
            .cornerRadius(theme.cornerRadius.sm)
            .overlay(
                RoundedRectangle(cornerRadius: theme.cornerRadius.sm)
                    .stroke(Color(.systemGray4), lineWidth: 1)
            )
        }
    }
}

// MARK: - View Extension for Optional Accessibility Identifier

public extension View {
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
