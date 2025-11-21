import SwiftUI

/// Dashboard/Home view showing user stats and test availability
struct DashboardView: View {
    @StateObject private var viewModel = DashboardViewModel()
    @StateObject private var authManager = AuthManager.shared
    @State private var navigateToTest = false

    var body: some View {
        ZStack {
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
        VStack(spacing: DesignSystem.Spacing.sm) {
            if let userName = authManager.userFullName {
                Text("Welcome, \(userName)!")
                    .font(Typography.h1)
                    .foregroundColor(ColorPalette.textPrimary)
            } else {
                Text("Welcome!")
                    .font(Typography.h1)
                    .foregroundColor(ColorPalette.textPrimary)
            }

            Text("Track your cognitive performance over time")
                .font(Typography.bodyMedium)
                .foregroundColor(ColorPalette.textSecondary)
                .multilineTextAlignment(.center)
        }
        .padding(.top, DesignSystem.Spacing.xl)
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
        VStack(alignment: .leading, spacing: DesignSystem.Spacing.md) {
            HStack {
                Image(systemName: "clock.fill")
                    .foregroundColor(ColorPalette.primary)
                Text("Latest Test")
                    .font(Typography.h3)
                Spacer()
            }

            Divider()

            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: DesignSystem.Spacing.sm) {
                    Text("IQ Score")
                        .font(Typography.bodySmall)
                        .foregroundColor(ColorPalette.textSecondary)

                    Text("\(result.iqScore)")
                        .font(Typography.displaySmall)
                        .foregroundColor(ColorPalette.textPrimary)
                }

                Spacer()

                VStack(alignment: .trailing, spacing: DesignSystem.Spacing.xs) {
                    if let dateStr = viewModel.latestTestDateFormatted {
                        Text(dateStr)
                            .font(Typography.captionMedium)
                            .foregroundColor(ColorPalette.textSecondary)
                    }

                    Text("\(result.accuracyPercentage, specifier: "%.0f")% correct")
                        .font(Typography.captionMedium)
                        .foregroundColor(ColorPalette.textSecondary)
                }
            }
        }
        .padding(DesignSystem.Spacing.lg)
        .cardStyle(
            cornerRadius: DesignSystem.CornerRadius.md,
            shadow: DesignSystem.Shadow.md,
            backgroundColor: ColorPalette.backgroundSecondary
        )
    }

    // MARK: - Action Button

    private var actionButton: some View {
        Button {
            navigateToTest = true
        } label: {
            Label("Take Another Test", systemImage: "brain.head.profile")
                .font(Typography.button)
                .foregroundColor(.white)
                .frame(maxWidth: .infinity)
                .padding(DesignSystem.Spacing.lg)
                .background(ColorPalette.primary)
                .cornerRadius(DesignSystem.CornerRadius.md)
        }
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
            Image(systemName: icon)
                .font(.system(size: DesignSystem.IconSize.lg))
                .foregroundColor(color)
                .accessibilityHidden(true) // Decorative icon

            Text(value)
                .font(Typography.statValue)
                .foregroundColor(ColorPalette.textPrimary)
                .accessibilityHidden(true)

            Text(label)
                .font(Typography.captionMedium)
                .foregroundColor(ColorPalette.textSecondary)
                .accessibilityHidden(true)
        }
        .frame(maxWidth: .infinity)
        .padding(DesignSystem.Spacing.lg)
        .cardStyle(
            cornerRadius: DesignSystem.CornerRadius.md,
            shadow: DesignSystem.Shadow.sm,
            backgroundColor: ColorPalette.backgroundSecondary
        )
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(label): \(value)")
    }
}

#Preview {
    NavigationStack {
        DashboardView()
    }
}
