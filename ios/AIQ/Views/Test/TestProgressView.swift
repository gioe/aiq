import SwiftUI

/// Enhanced progress indicator showing test completion status with detailed stats
struct TestProgressView: View {
    let currentQuestion: Int
    let totalQuestions: Int
    let answeredCount: Int

    var progress: Double {
        Double(currentQuestion) / Double(totalQuestions)
    }

    var completionPercentage: Int {
        guard totalQuestions > 0 else { return 0 }
        return Int((Double(answeredCount) / Double(totalQuestions)) * 100)
    }

    var body: some View {
        VStack(spacing: 12) {
            // Progress bar with percentage
            VStack(spacing: 8) {
                HStack {
                    Text("test.progress.title".localized)
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .textCase(.uppercase)

                    Spacer()

                    Text("test.progress.complete.format".localized(with: completionPercentage))
                        .font(.caption)
                        .fontWeight(.semibold)
                        .foregroundColor(completionPercentage == 100 ? .green : .accentColor)
                        .animation(.easeInOut(duration: 0.3), value: completionPercentage)
                }

                progressBar
            }

            // Stats
            HStack(spacing: 20) {
                // Question position
                statItem(
                    icon: "doc.text.fill",
                    value: "\(currentQuestion)/\(totalQuestions)",
                    label: "test.progress.current".localized
                )

                Divider()
                    .frame(height: 20)

                // Answered count
                statItem(
                    icon: "checkmark.circle.fill",
                    value: "\(answeredCount)",
                    label: "test.progress.answered".localized,
                    iconColor: .green
                )

                Divider()
                    .frame(height: 20)

                // Remaining count
                statItem(
                    icon: "circle.dotted",
                    value: "\(totalQuestions - answeredCount)",
                    label: "test.progress.remaining".localized,
                    iconColor: .orange
                )
            }
        }
        .padding()
        .background(Color(.secondarySystemGroupedBackground))
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.05), radius: 8, x: 0, y: 2)
        .accessibilityIdentifier(AccessibilityIdentifiers.TestTakingView.progressBar)
        .accessibilityElement(children: .combine)
        .accessibilityLabel(
            "Test progress: Question \(currentQuestion) of \(totalQuestions), " +
                "\(answeredCount) answered, \(totalQuestions - answeredCount) remaining"
        )
        .accessibilityValue("\(completionPercentage) percent complete")
    }

    private var progressBar: some View {
        GeometryReader { geometry in
            ZStack(alignment: .leading) {
                // Background
                RoundedRectangle(cornerRadius: 6)
                    .fill(Color(.systemGray5))
                    .frame(height: 10)

                // Progress - segmented by answered questions
                RoundedRectangle(cornerRadius: 6)
                    .fill(
                        LinearGradient(
                            colors: [
                                completionPercentage == 100 ? Color.green : Color.accentColor,
                                (completionPercentage == 100 ? Color.green : Color.accentColor).opacity(0.7)
                            ],
                            startPoint: .leading,
                            endPoint: .trailing
                        )
                    )
                    .frame(
                        width: geometry.size.width * (Double(answeredCount) / Double(totalQuestions)),
                        height: 10
                    )
                    .animation(.spring(response: 0.5, dampingFraction: 0.8), value: answeredCount)
                    .animation(.easeInOut(duration: 0.4), value: completionPercentage)

                // Current position indicator
                Circle()
                    .fill(Color.white)
                    .frame(width: 14, height: 14)
                    .overlay(
                        Circle()
                            .strokeBorder(Color.accentColor, lineWidth: 2)
                    )
                    .offset(x: (geometry.size.width * progress) - 7)
                    .animation(.spring(response: 0.5, dampingFraction: 0.8), value: progress)
            }
        }
        .frame(height: 14)
    }

    private func statItem(
        icon: String,
        value: String,
        label: String,
        iconColor: Color? = nil
    ) -> some View {
        HStack(spacing: 6) {
            Image(systemName: icon)
                .foregroundColor(iconColor ?? .secondary)
                .font(.caption)

            VStack(alignment: .leading, spacing: 2) {
                Text(value)
                    .font(.subheadline)
                    .fontWeight(.bold)
                    .foregroundColor(.primary)

                Text(label)
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
        }
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
