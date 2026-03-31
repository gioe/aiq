import SwiftUI

/// Card component displaying in-progress test session details with resume and abandon options
struct InProgressTestCard: View {
    let session: TestSession
    let questionsAnswered: Int?
    let onResume: () -> Void
    let onAbandon: () async -> Void

    @State private var showAbandonConfirmation = false
    @State private var isAbandoning = false
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    @Environment(\.appTheme) private var theme

    var body: some View {
        VStack(alignment: .leading, spacing: DesignSystem.Spacing.lg) {
            // Header
            header

            // Session Details
            sessionDetails

            // Divider
            Divider()
                .background(theme.colors.textSecondary.opacity(0.2))

            // Action Buttons
            actionButtons
        }
        .padding(DesignSystem.Spacing.lg)
        .onAppear {
            ServiceContainer.shared.resolve(HapticManagerProtocol.self)?.prepare()
        }
        .background(
            RoundedRectangle(cornerRadius: DesignSystem.CornerRadius.lg)
                .fill(theme.colors.backgroundSecondary)
                .shadow(
                    color: Color.black.opacity(0.1),
                    radius: DesignSystem.Shadow.lg.radius,
                    x: 0,
                    y: DesignSystem.Shadow.lg.y
                )
        )
        .overlay(
            RoundedRectangle(cornerRadius: DesignSystem.CornerRadius.lg)
                .strokeBorder(theme.colors.warning.opacity(0.3), lineWidth: 2)
        )
        .alert("Abandon Test?", isPresented: $showAbandonConfirmation) {
            Button("Cancel", role: .cancel) {}
            Button("Abandon Test", role: .destructive) {
                isAbandoning = true
                Task {
                    await onAbandon()
                    isAbandoning = false
                }
            }
        } message: {
            Text("This test will not count toward your history. Are you sure you want to abandon it?")
        }
        .overlay {
            if isAbandoning {
                ZStack {
                    Color.black.opacity(0.3)
                        .ignoresSafeArea()

                    VStack(spacing: DesignSystem.Spacing.md) {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle(tint: .white))
                            .scaleEffect(1.2)

                        Text("Abandoning test...")
                            .font(theme.typography.bodyMedium)
                            .foregroundColor(.white)
                    }
                    .padding(DesignSystem.Spacing.xl)
                    .background(
                        RoundedRectangle(cornerRadius: DesignSystem.CornerRadius.lg)
                            .fill(theme.colors.textPrimary.opacity(0.9))
                    )
                }
                .transition(reduceMotion ? .identity : .opacity)
            }
        }
        .disabled(isAbandoning)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier(AccessibilityIdentifiers.DashboardView.inProgressTestCard)
    }

    // MARK: - Header

    private var header: some View {
        HStack(spacing: DesignSystem.Spacing.sm) {
            ZStack {
                Circle()
                    .fill(theme.colors.warning.opacity(0.15))
                    .frame(width: 48, height: 48)

                Image(systemName: "clock.fill")
                    .font(.system(size: theme.iconSizes.md))
                    .foregroundStyle(
                        LinearGradient(
                            colors: [theme.colors.warning, theme.colors.warning.opacity(0.7)],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
            }

            VStack(alignment: .leading, spacing: 2) {
                Text("Test in Progress")
                    .font(theme.typography.h3)
                    .foregroundColor(theme.colors.textPrimary)

                Text(timeElapsedText)
                    .font(theme.typography.captionMedium)
                    .foregroundColor(theme.colors.textSecondary)
            }

            Spacer()
        }
    }

    // MARK: - Session Details

    private var sessionDetails: some View {
        VStack(spacing: DesignSystem.Spacing.md) {
            // Progress indicator
            if let answered = questionsAnswered {
                HStack(spacing: DesignSystem.Spacing.sm) {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.system(size: 16))
                        .foregroundColor(theme.colors.success)

                    Text("\(answered) questions answered")
                        .font(theme.typography.bodyMedium)
                        .foregroundColor(theme.colors.textPrimary)

                    Spacer()
                }
            }

            // Session ID (for debugging/reference)
            #if DEBUG
                HStack(spacing: DesignSystem.Spacing.sm) {
                    Image(systemName: "number.circle.fill")
                        .font(.system(size: 16))
                        .foregroundColor(theme.colors.textSecondary)

                    Text("Session ID: \(session.id)")
                        .font(theme.typography.captionMedium)
                        .foregroundColor(theme.colors.textSecondary)

                    Spacer()
                }
            #endif
        }
    }

    // MARK: - Action Buttons

    private var actionButtons: some View {
        VStack(spacing: DesignSystem.Spacing.sm) {
            // Resume Button (Primary)
            Button {
                // Haptic feedback for button tap
                ServiceContainer.shared.resolve(HapticManagerProtocol.self)?.trigger(.medium)
                onResume()
            } label: {
                HStack(spacing: DesignSystem.Spacing.sm) {
                    Image(systemName: "play.circle.fill")
                        .font(.system(size: theme.iconSizes.md, weight: .semibold))

                    Text("Resume Test")
                        .font(theme.typography.button)

                    Spacer()

                    Image(systemName: "arrow.right.circle.fill")
                        .font(.system(size: theme.iconSizes.md))
                }
                .foregroundColor(.white)
                .frame(maxWidth: .infinity)
                .padding(DesignSystem.Spacing.md)
                .background(
                    LinearGradient(
                        colors: [theme.colors.primary, theme.colors.primary.opacity(0.8)],
                        startPoint: .leading,
                        endPoint: .trailing
                    )
                )
                .cornerRadius(DesignSystem.CornerRadius.md)
            }
            .buttonStyle(.plain)
            .accessibilityLabel("Resume Test")
            .accessibilityHint("Continue your in-progress cognitive performance test")
            .accessibilityAddTraits(.isButton)
            .accessibilityIdentifier(AccessibilityIdentifiers.DashboardView.resumeButton)

            // Abandon Button (Secondary, Destructive)
            Button {
                // Haptic feedback for destructive action
                ServiceContainer.shared.resolve(HapticManagerProtocol.self)?.trigger(.warning)
                showAbandonConfirmation = true
            } label: {
                HStack(spacing: DesignSystem.Spacing.sm) {
                    Image(systemName: "xmark.circle.fill")
                        .font(.system(size: 16))

                    Text("Abandon Test")
                        .font(theme.typography.bodySmall.weight(.medium))
                }
                .foregroundColor(theme.colors.errorText)
                .frame(maxWidth: .infinity)
                .padding(DesignSystem.Spacing.md)
                .background(
                    RoundedRectangle(cornerRadius: DesignSystem.CornerRadius.md)
                        .fill(theme.colors.error.opacity(0.1))
                )
                .overlay(
                    RoundedRectangle(cornerRadius: DesignSystem.CornerRadius.md)
                        .strokeBorder(theme.colors.error.opacity(0.3), lineWidth: 1)
                )
            }
            .buttonStyle(.plain)
            .accessibilityLabel("Abandon Test")
            .accessibilityHint("Discard this test. It will not count toward your history.")
            .accessibilityAddTraits(.isButton)
            .accessibilityIdentifier(AccessibilityIdentifiers.DashboardView.abandonTestButton)
        }
    }

    // MARK: - Helper Properties

    private var timeElapsedText: String {
        let elapsed = Date().timeIntervalSince(session.startedAt)

        if elapsed < 60 {
            return "Started just now"
        } else if elapsed < 3600 {
            let minutes = Int(elapsed / 60)
            return "Started \(minutes) \(minutes == 1 ? "minute" : "minutes") ago"
        } else if elapsed < 86400 {
            let hours = Int(elapsed / 3600)
            return "Started \(hours) \(hours == 1 ? "hour" : "hours") ago"
        } else {
            let days = Int(elapsed / 86400)
            return "Started \(days) \(days == 1 ? "day" : "days") ago"
        }
    }
}

#if DEBUG

    // MARK: - Preview

    #Preview("With Progress") {
        ScrollView {
            InProgressTestCard(
                session: MockDataFactory.makeInProgressSession(
                    id: 123,
                    userId: 1,
                    startedAt: Date().addingTimeInterval(-3600 * 2) // 2 hours ago
                ),
                questionsAnswered: 12,
                onResume: {
                    print("Resume tapped")
                },
                onAbandon: {
                    print("Abandon tapped")
                }
            )
            .padding()
        }
        .background(ColorPalette.background)
    }

    #Preview("Just Started") {
        ScrollView {
            InProgressTestCard(
                session: MockDataFactory.makeInProgressSession(
                    id: 456,
                    userId: 1,
                    startedAt: Date().addingTimeInterval(-30) // 30 seconds ago
                ),
                questionsAnswered: 0,
                onResume: {
                    print("Resume tapped")
                },
                onAbandon: {
                    print("Abandon tapped")
                }
            )
            .padding()
        }
        .background(ColorPalette.background)
    }

    #Preview("Days Ago") {
        ScrollView {
            InProgressTestCard(
                session: MockDataFactory.makeInProgressSession(
                    id: 789,
                    userId: 1,
                    startedAt: Date().addingTimeInterval(-86400 * 3) // 3 days ago
                ),
                questionsAnswered: 5,
                onResume: {
                    print("Resume tapped")
                },
                onAbandon: {
                    print("Abandon tapped")
                }
            )
            .padding()
        }
        .background(ColorPalette.background)
    }
#endif
