import SwiftUI

/// Progress indicator showing test completion status
struct TestProgressView: View {
    let currentQuestion: Int
    let totalQuestions: Int
    let answeredCount: Int

    var progress: Double {
        Double(currentQuestion) / Double(totalQuestions)
    }

    var body: some View {
        VStack(spacing: 12) {
            // Progress bar
            progressBar

            // Stats
            HStack {
                // Question progress
                Label {
                    Text("\(currentQuestion)/\(totalQuestions)")
                        .font(.subheadline)
                        .fontWeight(.semibold)
                } icon: {
                    Image(systemName: "list.bullet.clipboard")
                }

                Spacer()

                // Answered count
                Label {
                    Text("\(answeredCount) answered")
                        .font(.subheadline)
                        .fontWeight(.medium)
                } icon: {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.green)
                }
            }
            .foregroundColor(.secondary)
        }
    }

    private var progressBar: some View {
        GeometryReader { geometry in
            ZStack(alignment: .leading) {
                // Background
                RoundedRectangle(cornerRadius: 8)
                    .fill(Color(.systemGray5))
                    .frame(height: 8)

                // Progress
                RoundedRectangle(cornerRadius: 8)
                    .fill(
                        LinearGradient(
                            colors: [Color.accentColor, Color.accentColor.opacity(0.7)],
                            startPoint: .leading,
                            endPoint: .trailing
                        )
                    )
                    .frame(width: geometry.size.width * progress, height: 8)
                    .animation(.spring(response: 0.5, dampingFraction: 0.8), value: progress)
            }
        }
        .frame(height: 8)
    }
}

// MARK: - Preview

#Preview {
    VStack(spacing: 30) {
        TestProgressView(
            currentQuestion: 1,
            totalQuestions: 20,
            answeredCount: 0
        )

        TestProgressView(
            currentQuestion: 10,
            totalQuestions: 20,
            answeredCount: 8
        )

        TestProgressView(
            currentQuestion: 20,
            totalQuestions: 20,
            answeredCount: 20
        )
    }
    .padding()
}
