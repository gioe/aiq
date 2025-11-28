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
        .toolbar {
            ToolbarItemGroup(placement: .navigationBarTrailing) {
                if viewModel.hasHistory {
                    // Date Filter Menu
                    Menu {
                        Picker("Filter", selection: $viewModel.dateFilter) {
                            ForEach(TestHistoryDateFilter.allCases) { filter in
                                Text(filter.rawValue).tag(filter)
                            }
                        }
                    } label: {
                        Label("Filter", systemImage: "line.3.horizontal.decrease.circle")
                    }

                    // Sort Order Menu
                    Menu {
                        Picker("Sort", selection: $viewModel.sortOrder) {
                            ForEach(TestHistorySortOrder.allCases) { order in
                                Text(order.rawValue).tag(order)
                            }
                        }
                    } label: {
                        Label("Sort", systemImage: "arrow.up.arrow.down.circle")
                    }
                }
            }
        }
        .task {
            await viewModel.fetchHistory()
        }
        .onChange(of: viewModel.sortOrder) { _ in
            viewModel.applyFiltersAndSort()
        }
        .onChange(of: viewModel.dateFilter) { _ in
            viewModel.applyFiltersAndSort()
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
                            HistoryStatCard(
                                label: "Tests Taken",
                                value: "\(viewModel.totalTestsTaken)",
                                icon: "list.clipboard.fill"
                            )

                            HistoryStatCard(
                                label: "Average IQ",
                                value: "\(avgScore)",
                                icon: "chart.line.uptrend.xyaxis"
                            )

                            HistoryStatCard(
                                label: "Best Score",
                                value: "\(bestScore)",
                                icon: "star.fill"
                            )
                        }
                        .padding(.horizontal)
                    }
                    .padding(.vertical)
                }

                // Performance Insights
                if let insights = viewModel.performanceInsights {
                    InsightsCardView(insights: insights)
                        .padding(.horizontal)
                }

                // Trend Chart
                IQTrendChart(testHistory: viewModel.testHistory)
                    .padding(.horizontal)

                Divider()
                    .padding(.horizontal)

                // Filter Status (if filtered)
                if viewModel.dateFilter != .all || viewModel.sortOrder != .newestFirst {
                    HStack {
                        Image(systemName: "info.circle.fill")
                            .foregroundColor(.accentColor)
                            .imageScale(.small)

                        if viewModel.dateFilter != .all {
                            Text("Showing \(viewModel.filteredResultsCount) of \(viewModel.totalTestsTaken) tests")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }

                        Spacer()

                        Button {
                            viewModel.dateFilter = .all
                            viewModel.sortOrder = .newestFirst
                        } label: {
                            Text("Clear Filters")
                                .font(.caption)
                                .foregroundColor(.accentColor)
                        }
                    }
                    .padding(.horizontal)
                    .padding(.vertical, 8)
                    .background(Color(.secondarySystemBackground))
                    .cornerRadius(8)
                    .padding(.horizontal)
                }

                // Test History List
                ForEach(viewModel.testHistory) { result in
                    NavigationLink {
                        TestDetailView(
                            testResult: result,
                            userAverage: viewModel.averageIQScore
                        )
                    } label: {
                        TestHistoryListItem(testResult: result)
                    }
                    .buttonStyle(.plain)
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
        EmptyStateView(
            icon: "chart.xyaxis.line",
            title: "No Test History Yet",
            message: """
            Take your first IQ test to start tracking your cognitive performance over time. \
            Your scores and progress will appear here.
            """
        )
    }
}

/// Simple stat card component for history summary statistics
private struct HistoryStatCard: View {
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
