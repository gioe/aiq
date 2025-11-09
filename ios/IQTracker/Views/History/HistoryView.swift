import SwiftUI

/// History view showing past test results
struct HistoryView: View {
    @StateObject private var viewModel = HistoryViewModel()

    var body: some View {
        ZStack {
            if viewModel.isLoading && !viewModel.hasHistory {
                LoadingView(message: "Loading history...")
            } else if viewModel.error != nil {
                ErrorView(
                    error: viewModel.error!,
                    retryAction: {
                        Task {
                            await viewModel.retry()
                        }
                    }
                )
            } else if viewModel.hasHistory {
                historyList
            } else {
                emptyState
            }
        }
        .navigationTitle("History")
        .task {
            await viewModel.fetchHistory()
        }
    }

    private var historyList: some View {
        ScrollView {
            LazyVStack(spacing: 16) {
                // Summary Stats
                if let avgScore = viewModel.averageIQScore,
                   let bestScore = viewModel.bestIQScore {
                    VStack(spacing: 12) {
                        HStack(spacing: 20) {
                            StatCard(
                                label: "Tests Taken",
                                value: "\(viewModel.totalTestsTaken)",
                                icon: "list.clipboard.fill"
                            )

                            StatCard(
                                label: "Average IQ",
                                value: "\(avgScore)",
                                icon: "chart.line.uptrend.xyaxis"
                            )

                            StatCard(
                                label: "Best Score",
                                value: "\(bestScore)",
                                icon: "star.fill"
                            )
                        }
                        .padding(.horizontal)
                    }
                    .padding(.vertical)
                }

                Divider()
                    .padding(.horizontal)

                // Test History List
                ForEach(viewModel.testHistory) { result in
                    TestHistoryListItem(testResult: result)
                        .padding(.horizontal)
                }
            }
            .padding(.vertical)
        }
        .refreshable {
            await viewModel.refreshHistory()
        }
    }

    private var emptyState: some View {
        VStack(spacing: 24) {
            Image(systemName: "chart.xyaxis.line")
                .font(.system(size: 60))
                .foregroundColor(.accentColor)

            Text("No test history yet")
                .font(.headline)

            Text("Your test results will appear here once you complete your first IQ test.")
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 40)

            Spacer()
        }
        .padding()
        .padding(.top, 60)
    }
}

/// Stat card component for summary statistics
private struct StatCard: View {
    let label: String
    let value: String
    let icon: String

    var body: some View {
        VStack(spacing: 8) {
            Image(systemName: icon)
                .font(.title2)
                .foregroundColor(.accentColor)

            Text(value)
                .font(.title2.weight(.bold))
                .foregroundColor(.primary)

            Text(label)
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding()
        .background(Color(.secondarySystemBackground))
        .cornerRadius(12)
    }
}

#Preview {
    NavigationStack {
        HistoryView()
    }
}
