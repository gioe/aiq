import SwiftUI

/// A compact timer display for the test-taking view
struct TestTimerView: View {
    @ObservedObject var timerManager: TestTimerManager

    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: timerIcon)
                .font(.system(size: 14, weight: .medium))
                .foregroundColor(timerForegroundColor)
                .accessibilityHidden(true)

            Text(timerManager.formattedTime)
                .font(.system(size: 16, weight: .semibold, design: .monospaced))
                .foregroundColor(timerForegroundColor)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 6)
        .background(timerBackgroundColor)
        .clipShape(Capsule())
        .animation(.easeInOut(duration: 0.3), value: timerManager.timerColor)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Time remaining: \(timerManager.formattedTime)")
        .accessibilityValue(timerManager.formattedTime)
        .accessibilityAddTraits(.updatesFrequently)
    }

    // MARK: - Computed Properties

    private var timerIcon: String {
        switch timerManager.timerColor {
        case .critical:
            "exclamationmark.circle.fill"
        case .warning:
            "clock.badge.exclamationmark.fill"
        case .normal:
            "clock.fill"
        }
    }

    private var timerForegroundColor: Color {
        switch timerManager.timerColor {
        case .critical:
            .white
        case .warning:
            .orange
        case .normal:
            .secondary
        }
    }

    private var timerBackgroundColor: Color {
        switch timerManager.timerColor {
        case .critical:
            .red
        case .warning:
            .orange.opacity(0.15)
        case .normal:
            Color(.systemGray6)
        }
    }
}

// MARK: - Preview

#Preview("Normal") {
    TestTimerView(timerManager: {
        let manager = TestTimerManager()
        return manager
    }())
}

#Preview("Warning") {
    TestTimerView(timerManager: {
        let manager = TestTimerManager()
        // Simulate 4 minutes remaining
        return manager
    }())
}
