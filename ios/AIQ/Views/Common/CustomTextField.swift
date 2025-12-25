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
                        .accessibilityLabel(title)
                        .accessibilityValue(text.isEmpty ? "Empty" : "Entered")
                        .accessibilityHint("Secure text field. Double tap to edit")
                        .accessibilityIdentifier(accessibilityId ?? "")
                } else {
                    TextField(placeholder, text: $text)
                        .keyboardType(keyboardType)
                        .textInputAutocapitalization(autocapitalization)
                        .accessibilityLabel(title)
                        .accessibilityValue(text.isEmpty ? "Empty" : text)
                        .accessibilityHint("Text field. Double tap to edit")
                        .accessibilityIdentifier(accessibilityId ?? "")
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
