import SwiftUI

/// Compact progress header for adaptive (CAT) testing
///
/// Displays:
/// - Timer countdown
/// - Item count (X of ~Y)
/// - Progress bar
/// - Domain coverage indicators
struct AdaptiveProgressHeader: View {
    @ObservedObject var timerManager: TestTimerManager
    let itemsAdministered: Int
    let estimatedTotal: Int
    let progress: Double
    let administeredDomains: Set<QuestionType>

    @Environment(\.accessibilityReduceMotion) var reduceMotion

    var body: some View {
        VStack(spacing: 6) {
            // Top row: timer and item count
            HStack {
                TestTimerView(timerManager: timerManager)

                Spacer()

                Text("\(itemsAdministered) of ~\(estimatedTotal)")
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .accessibilityLabel("Question \(itemsAdministered) of approximately \(estimatedTotal)")
                    .accessibilityIdentifier(AccessibilityIdentifiers.AdaptiveTestView.itemCountLabel)
            }

            // Progress bar
            ProgressView(value: progress, total: 1.0)
                .tint(.accentColor)
                .accessibilityLabel("Test progress: \(Int(progress * 100)) percent complete")
                .accessibilityIdentifier(AccessibilityIdentifiers.AdaptiveTestView.progressBar)

            // Domain coverage indicators
            HStack(spacing: 8) {
                Text("Domains:")
                    .font(.caption2)
                    .foregroundColor(.secondary)
                    .accessibilityHidden(true)

                ForEach(allDomains, id: \.self) { domain in
                    let isAdministered = administeredDomains.contains(domain)
                    let color = isAdministered
                        ? domainColor(for: domain)
                        : Color.gray.opacity(0.3)
                    let statusText = isAdministered
                        ? "completed"
                        : "not yet administered"

                    domainIcon(for: domain)
                        .font(.system(size: 14))
                        .foregroundColor(color)
                        .frame(width: 20, height: 20)
                        .accessibilityLabel(
                            "\(domain.rawValue.capitalized) domain: \(statusText)"
                        )
                        .accessibilityIdentifier(
                            AccessibilityIdentifiers.AdaptiveTestView.domainIcon(
                                for: domain.rawValue
                            )
                        )
                }
            }
            .accessibilityElement(children: .combine)
            .accessibilityLabel(domainCoverageLabel)
            .accessibilityIdentifier(AccessibilityIdentifiers.AdaptiveTestView.domainIndicator)
        }
        .padding(.horizontal)
        .padding(.vertical, 8)
        .background(Color(.systemBackground))
        .shadow(color: Color.black.opacity(0.05), radius: 2, y: 1)
        .accessibilityIdentifier(AccessibilityIdentifiers.AdaptiveTestView.progressHeader)
    }

    // MARK: - Private Properties

    /// All cognitive domains in consistent order
    private var allDomains: [QuestionType] {
        [.pattern, .logic, .spatial, .math, .verbal, .memory]
    }

    /// SF Symbol icon for each domain
    private func domainIcon(for domain: QuestionType) -> Image {
        let iconName = switch domain {
        case .pattern:
            "square.grid.3x3.fill"
        case .logic:
            "lightbulb.fill"
        case .spatial:
            "rotate.3d"
        case .math:
            "function"
        case .verbal:
            "text.bubble.fill"
        case .memory:
            "brain.head.profile"
        }
        return Image(systemName: iconName)
    }

    /// Color coding for each domain
    private func domainColor(for domain: QuestionType) -> Color {
        switch domain {
        case .pattern:
            .blue
        case .logic:
            .orange
        case .spatial:
            .purple
        case .math:
            .green
        case .verbal:
            .pink
        case .memory:
            .indigo
        }
    }

    /// Accessibility label describing domain coverage
    private var domainCoverageLabel: String {
        let completed = administeredDomains.count
        let total = allDomains.count
        return "Domain coverage: \(completed) of \(total) domains have questions administered"
    }
}

// MARK: - Preview

#Preview("Early in Test") {
    AdaptiveProgressHeader(
        timerManager: TestTimerManager(),
        itemsAdministered: 3,
        estimatedTotal: 15,
        progress: 0.2,
        administeredDomains: [.pattern, .logic]
    )
}

#Preview("Mid Test") {
    AdaptiveProgressHeader(
        timerManager: TestTimerManager(),
        itemsAdministered: 8,
        estimatedTotal: 15,
        progress: 0.53,
        administeredDomains: [.pattern, .logic, .spatial, .math, .verbal]
    )
}

#Preview("Near End") {
    AdaptiveProgressHeader(
        timerManager: TestTimerManager(),
        itemsAdministered: 13,
        estimatedTotal: 15,
        progress: 0.87,
        administeredDomains: [.pattern, .logic, .spatial, .math, .verbal, .memory]
    )
}
