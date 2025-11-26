import SwiftUI

/// Dashboard/Home view showing user stats and test availability
struct DashboardView: View {
    @StateObject private var viewModel = DashboardViewModel()
    @StateObject private var authManager = AuthManager.shared
    @State private var navigateToTest = false

    var body: some View {
        ZStack {
            // Modern gradient background
            LinearGradient(
                gradient: Gradient(colors: [
                    ColorPalette.background,
                    ColorPalette.backgroundSecondary.opacity(0.3)
                ]),
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .ignoresSafeArea()

            if viewModel.isLoading && !viewModel.hasTests {
                LoadingView(message: "Loading dashboard...")
            } else if viewModel.error != nil {
                ErrorView(
                    error: viewModel.error!,
                    retryAction: {
                        Task {
                            await viewModel.retry()
                        }
                    }
                )
            } else if viewModel.hasTests {
                dashboardContent
            } else {
                emptyState
            }
        }
        .navigationTitle("Dashboard")
        .navigationBarTitleDisplayMode(.large)
        .navigationDestination(isPresented: $navigateToTest) {
            TestTakingView()
        }
        .task {
            await viewModel.fetchDashboardData()
        }
    }

    // MARK: - Dashboard Content

    private var dashboardContent: some View {
        ScrollView {
            VStack(spacing: DesignSystem.Spacing.xxl) {
                // Welcome Header
                welcomeHeader

                // Stats Grid
                statsGrid

                // Latest Test Result
                if let latest = viewModel.latestTestResult {
                    latestTestCard(latest)
                }

                // Action Button
                actionButton

                Spacer()
            }
            .padding(DesignSystem.Spacing.lg)
        }
        .refreshable {
            await viewModel.refreshDashboard()
        }
    }

    // MARK: - Welcome Header

    private var welcomeHeader: some View {
        VStack(spacing: DesignSystem.Spacing.md) {
            // Greeting with time-based context
            HStack(spacing: DesignSystem.Spacing.xs) {
                Image(systemName: greetingIcon)
                    .font(.system(size: DesignSystem.IconSize.lg))
                    .foregroundStyle(
                        LinearGradient(
                            colors: [ColorPalette.primary, ColorPalette.primary.opacity(0.7)],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )

                if let userName = authManager.userFullName {
                    Text("\(greetingText), \(userName)!")
                        .font(Typography.h1)
                        .foregroundStyle(
                            LinearGradient(
                                colors: [ColorPalette.textPrimary, ColorPalette.textSecondary],
                                startPoint: .leading,
                                endPoint: .trailing
                            )
                        )
                } else {
                    Text("\(greetingText)!")
                        .font(Typography.h1)
                        .foregroundColor(ColorPalette.textPrimary)
                }
            }

            Text("Track your cognitive performance over time")
                .font(Typography.bodyMedium)
                .foregroundColor(ColorPalette.textSecondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, DesignSystem.Spacing.lg)
    }

    // Time-based greeting
    private var greetingText: String {
        let hour = Calendar.current.component(.hour, from: Date())
        switch hour {
        case 0 ..< 12: return "Good morning"
        case 12 ..< 17: return "Good afternoon"
        default: return "Good evening"
        }
    }

    private var greetingIcon: String {
        let hour = Calendar.current.component(.hour, from: Date())
        switch hour {
        case 0 ..< 12: return "sunrise.fill"
        case 12 ..< 17: return "sun.max.fill"
        default: return "moon.stars.fill"
        }
    }

    // MARK: - Stats Grid

    private var statsGrid: some View {
        HStack(spacing: DesignSystem.Spacing.lg) {
            StatCard(
                label: "Tests Taken",
                value: "\(viewModel.testCount)",
                icon: "list.clipboard.fill",
                color: ColorPalette.statBlue
            )

            if let avgScore = viewModel.averageScore {
                StatCard(
                    label: "Average IQ",
                    value: "\(avgScore)",
                    icon: "chart.line.uptrend.xyaxis",
                    color: ColorPalette.statGreen
                )
            }
        }
    }

    // MARK: - Latest Test Card

    private func latestTestCard(_ result: TestResult) -> some View {
        VStack(alignment: .leading, spacing: DesignSystem.Spacing.lg) {
            testCardHeader
            testCardScores(result)
            testCardProgress(result)
        }
        .padding(DesignSystem.Spacing.lg)
        .background(
            RoundedRectangle(cornerRadius: DesignSystem.CornerRadius.lg)
                .fill(ColorPalette.backgroundSecondary)
                .shadow(
                    color: Color.black.opacity(0.1),
                    radius: DesignSystem.Shadow.lg.radius,
                    x: 0,
                    y: DesignSystem.Shadow.lg.y
                )
        )
        .overlay(
            RoundedRectangle(cornerRadius: DesignSystem.CornerRadius.lg)
                .strokeBorder(Color.gray.opacity(0.1), lineWidth: 1)
        )
    }

    private var testCardHeader: some View {
        TestCardHeader(dateFormatted: viewModel.latestTestDateFormatted)
    }

    private func testCardScores(_ result: TestResult) -> some View {
        TestCardScores(result: result)
    }

    private func testCardProgress(_ result: TestResult) -> some View {
        TestCardProgress(result: result)
    }

    // MARK: - Action Button

    private var actionButton: some View {
        Button {
            navigateToTest = true
        } label: {
            HStack(spacing: DesignSystem.Spacing.sm) {
                Image(systemName: "brain.head.profile")
                    .font(.system(size: DesignSystem.IconSize.md, weight: .semibold))

                Text("Take Another Test")
                    .font(Typography.button)

                Spacer()

                Image(systemName: "arrow.right.circle.fill")
                    .font(.system(size: DesignSystem.IconSize.md))
            }
            .foregroundColor(.white)
            .frame(maxWidth: .infinity)
            .padding(DesignSystem.Spacing.lg)
            .background(
                LinearGradient(
                    colors: [ColorPalette.primary, ColorPalette.primary.opacity(0.8)],
                    startPoint: .leading,
                    endPoint: .trailing
                )
            )
            .cornerRadius(DesignSystem.CornerRadius.lg)
            .shadow(
                color: ColorPalette.primary.opacity(0.3),
                radius: 8,
                x: 0,
                y: 4
            )
        }
        .buttonStyle(.plain)
        .accessibilityLabel("Take Another Test")
        .accessibilityHint("Start a new cognitive performance test")
        .accessibilityAddTraits(.isButton)
    }

    // MARK: - Empty State

    private var emptyState: some View {
        ScrollView {
            VStack(spacing: DesignSystem.Spacing.xxl) {
                welcomeHeader

                EmptyStateView(
                    icon: "brain.head.profile",
                    title: "Ready to Begin?",
                    message: """
                    Take your first cognitive performance assessment to establish your baseline score. \
                    Track your progress over time and discover insights about your performance.
                    """,
                    actionTitle: "Start Your First Test",
                    action: {
                        navigateToTest = true
                    }
                )
                .padding(.vertical, DesignSystem.Spacing.xl)

                Spacer()
            }
            .padding(DesignSystem.Spacing.lg)
        }
        .refreshable {
            await viewModel.refreshDashboard()
        }
    }
}

// MARK: - Stat Card

private struct StatCard: View {
    let label: String
    let value: String
    let icon: String
    let color: Color

    var body: some View {
        VStack(spacing: DesignSystem.Spacing.md) {
            ZStack {
                Circle()
                    .fill(
                        LinearGradient(
                            colors: [color.opacity(0.2), color.opacity(0.1)],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                    .frame(width: 56, height: 56)

                Image(systemName: icon)
                    .font(.system(size: DesignSystem.IconSize.lg, weight: .semibold))
                    .foregroundStyle(
                        LinearGradient(
                            colors: [color, color.opacity(0.7)],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                    .accessibilityHidden(true)
            }

            Text(value)
                .font(Typography.statValue)
                .foregroundStyle(
                    LinearGradient(
                        colors: [ColorPalette.textPrimary, ColorPalette.textSecondary],
                        startPoint: .top,
                        endPoint: .bottom
                    )
                )
                .accessibilityHidden(true)

            Text(label)
                .font(Typography.captionMedium)
                .foregroundColor(ColorPalette.textSecondary)
                .accessibilityHidden(true)
        }
        .frame(maxWidth: .infinity)
        .padding(DesignSystem.Spacing.lg)
        .background(
            RoundedRectangle(cornerRadius: DesignSystem.CornerRadius.lg)
                .fill(ColorPalette.backgroundSecondary)
                .shadow(
                    color: Color.black.opacity(0.08),
                    radius: DesignSystem.Shadow.md.radius,
                    x: 0,
                    y: DesignSystem.Shadow.md.y
                )
        )
        .overlay(
            RoundedRectangle(cornerRadius: DesignSystem.CornerRadius.lg)
                .strokeBorder(
                    LinearGradient(
                        colors: [
                            Color.gray.opacity(0.1),
                            Color.gray.opacity(0.05)
                        ],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    ),
                    lineWidth: 1
                )
        )
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(label): \(value)")
    }
}

// MARK: - Test Card Components

private struct TestCardHeader: View {
    let dateFormatted: String?

    var body: some View {
        HStack(spacing: DesignSystem.Spacing.sm) {
            ZStack {
                Circle()
                    .fill(ColorPalette.primary.opacity(0.1))
                    .frame(width: 44, height: 44)

                Image(systemName: "chart.line.uptrend.xyaxis")
                    .font(.system(size: DesignSystem.IconSize.md))
                    .foregroundStyle(
                        LinearGradient(
                            colors: [ColorPalette.primary, ColorPalette.primary.opacity(0.7)],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
            }

            VStack(alignment: .leading, spacing: 2) {
                Text("Latest Result")
                    .font(Typography.h3)
                    .foregroundColor(ColorPalette.textPrimary)

                if let dateStr = dateFormatted {
                    Text(dateStr)
                        .font(Typography.captionMedium)
                        .foregroundColor(ColorPalette.textSecondary)
                }
            }

            Spacer()
        }
    }
}

private struct TestCardScores: View {
    let result: TestResult

    var body: some View {
        HStack(spacing: DesignSystem.Spacing.xl) {
            iqScore
            Spacer()
            accuracy
        }
    }

    private var iqScore: some View {
        VStack(alignment: .leading, spacing: DesignSystem.Spacing.xs) {
            Text("IQ Score")
                .font(Typography.bodySmall)
                .foregroundColor(ColorPalette.textSecondary)

            HStack(alignment: .firstTextBaseline, spacing: 4) {
                Text("\(result.iqScore)")
                    .font(Typography.displaySmall)
                    .foregroundStyle(
                        LinearGradient(
                            colors: [ColorPalette.primary, ColorPalette.primary.opacity(0.8)],
                            startPoint: .leading,
                            endPoint: .trailing
                        )
                    )

                if result.iqScore > 100 {
                    Image(systemName: "arrow.up.right")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundColor(ColorPalette.success)
                } else if result.iqScore < 100 {
                    Image(systemName: "arrow.down.right")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundColor(ColorPalette.error)
                }
            }
        }
    }

    private var accuracy: some View {
        VStack(alignment: .trailing, spacing: DesignSystem.Spacing.xs) {
            Text("Accuracy")
                .font(Typography.bodySmall)
                .foregroundColor(ColorPalette.textSecondary)

            Text("\(result.accuracyPercentage, specifier: "%.0f")%")
                .font(Typography.h2)
                .foregroundColor(ColorPalette.textPrimary)
        }
    }
}

private struct TestCardProgress: View {
    let result: TestResult

    var body: some View {
        HStack(spacing: DesignSystem.Spacing.sm) {
            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 4)
                        .fill(ColorPalette.backgroundTertiary)
                        .frame(height: 8)

                    let progressWidth = geometry.size.width
                        * (CGFloat(result.correctAnswers) / CGFloat(result.totalQuestions))

                    RoundedRectangle(cornerRadius: 4)
                        .fill(
                            LinearGradient(
                                colors: [ColorPalette.primary, ColorPalette.primary.opacity(0.7)],
                                startPoint: .leading,
                                endPoint: .trailing
                            )
                        )
                        .frame(width: progressWidth, height: 8)
                }
            }
            .frame(height: 8)

            Text("\(result.correctAnswers)/\(result.totalQuestions)")
                .font(Typography.captionMedium)
                .foregroundColor(ColorPalette.textSecondary)
                .fixedSize()
        }
    }
}

#Preview {
    NavigationStack {
        DashboardView()
    }
}
