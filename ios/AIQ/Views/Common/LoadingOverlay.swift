import SwiftUI

/// A full-screen loading overlay with spinner and optional message
struct LoadingOverlay: View {
    let message: String?
    @State private var isAnimating = false

    init(message: String? = nil) {
        self.message = message
    }

    var body: some View {
        ZStack {
            Color.black.opacity(0.4)
                .ignoresSafeArea()

            VStack(spacing: 16) {
                ProgressView()
                    .progressViewStyle(CircularProgressViewStyle(tint: .white))
                    .scaleEffect(isAnimating ? 1.5 : 1.2)

                if let message {
                    Text(message)
                        .font(.subheadline)
                        .foregroundColor(.white)
                        .opacity(isAnimating ? 1.0 : 0.0)
                }
            }
            .padding(32)
            .background(Color(.systemGray6))
            .cornerRadius(16)
            .shadow(radius: 10)
            .scaleEffect(isAnimating ? 1.0 : 0.8)
            .opacity(isAnimating ? 1.0 : 0.0)
        }
        .onAppear {
            withAnimation(.easeOut(duration: 0.3)) {
                isAnimating = true
            }
        }
    }
}

#Preview {
    ZStack {
        Color.blue
            .ignoresSafeArea()

        LoadingOverlay(message: "Logging in...")
    }
}
