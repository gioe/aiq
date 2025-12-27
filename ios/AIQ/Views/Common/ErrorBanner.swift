import SwiftUI

/// A dismissible error banner that appears at the top of the screen
struct ErrorBanner: View {
    let message: String
    let onDismiss: () -> Void

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundColor(.white)

            Text(message)
                .font(.subheadline)
                .foregroundColor(.white)
                .multilineTextAlignment(.leading)

            Spacer()

            Button(
                action: onDismiss,
                label: {
                    Image(systemName: "xmark")
                        .foregroundColor(.white)
                        .fontWeight(.semibold)
                }
            )
            .accessibilityLabel("error.banner.dismiss".localized)
            .accessibilityIdentifier("errorBanner.dismissButton")
        }
        .padding()
        .background(Color.red)
        .cornerRadius(12)
        .shadow(color: Color.black.opacity(0.1), radius: 4, x: 0, y: 2)
        .accessibilityElement(children: .contain)
        .accessibilityLabel("Error: \(message)")
    }
}

#Preview {
    VStack {
        ErrorBanner(
            message: "Unable to connect to the server. Please check your internet connection.",
            onDismiss: {}
        )
        .padding()

        Spacer()
    }
}
