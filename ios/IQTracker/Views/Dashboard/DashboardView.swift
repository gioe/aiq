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
            VStack(spacing: 24) {
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
            .padding()
        }
        .refreshable {
            await viewModel.refreshDashboard()
        }
    }

    // MARK: - Welcome Header

    private var welcomeHeader: some View {
        VStack(spacing: 8) {
            if let userName = authManager.userFullName {
                Text("Welcome, \(userName)!")
                    .font(.title)
                    .fontWeight(.bold)
            } else {
                Text("Welcome!")
                    .font(.title)
                    .fontWeight(.bold)
            }

            Text("Track your cognitive performance over time")
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
        }
        .padding(.top, 20)
    }

    // MARK: - Stats Grid

    private var statsGrid: some View {
        HStack(spacing: 16) {
            StatCard(
                label: "Tests Taken",
                value: "\(viewModel.testCount)",
                icon: "list.clipboard.fill",
                color: .blue
            )

            if let avgScore = viewModel.averageScore {
                StatCard(
                    label: "Average IQ",
                    value: "\(avgScore)",
                    icon: "chart.line.uptrend.xyaxis",
                    color: .green
                )
            }
        }
    }

    // MARK: - Latest Test Card

    private func latestTestCard(_ result: TestResult) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "clock.fill")
                    .foregroundColor(.accentColor)
                Text("Latest Test")
                    .font(.headline)
                Spacer()
            }

            Divider()

            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 8) {
                    Text("IQ Score")
                        .font(.subheadline)
                        .foregroundColor(.secondary)

                    Text("\(result.iqScore)")
                        .font(.system(size: 36, weight: .bold))
                        .foregroundColor(.primary)
                }

                Spacer()

                VStack(alignment: .trailing, spacing: 4) {
                    if let dateStr = viewModel.latestTestDateFormatted {
                        Text(dateStr)
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }

                    Text("\(result.accuracyPercentage, specifier: "%.0f")% correct")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
        }
        .padding()
        .background(Color(.secondarySystemBackground))
        .cornerRadius(12)
    }

    // MARK: - Action Button

    private var actionButton: some View {
        Button {
            navigateToTest = true
        } label: {
            Label("Take Another Test", systemImage: "brain.head.profile")
                .font(.headline)
                .foregroundColor(.white)
                .frame(maxWidth: .infinity)
                .padding()
                .background(Color.accentColor)
                .cornerRadius(12)
        }
        .accessibilityLabel("Take Another Test")
        .accessibilityHint("Start a new IQ test")
        .accessibilityAddTraits(.isButton)
    }

    // MARK: - Empty State

    private var emptyState: some View {
        ScrollView {
            VStack(spacing: 24) {
                welcomeHeader

                EmptyStateView(
                    icon: "brain.head.profile",
                    title: "Ready to Begin?",
                    message: """
                    Take your first IQ test to establish your baseline score. \
                    Track your progress and discover insights about your cognitive performance.
                    """,
                    actionTitle: "Start Your First Test",
                    action: {
                        navigateToTest = true
                    }
                )
                .padding(.vertical, 20)

                Spacer()
            }
            .padding()
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
        VStack(spacing: 12) {
            Image(systemName: icon)
                .font(.title)
                .foregroundColor(color)
                .accessibilityHidden(true) // Decorative icon

            Text(value)
                .font(.title.weight(.bold))
                .foregroundColor(.primary)
                .accessibilityHidden(true)

            Text(label)
                .font(.caption)
                .foregroundColor(.secondary)
                .accessibilityHidden(true)
        }
        .frame(maxWidth: .infinity)
        .padding()
        .background(Color(.secondarySystemBackground))
        .cornerRadius(12)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(label): \(value)")
    }
}

#Preview {
    NavigationStack {
        DashboardView()
    }
}
