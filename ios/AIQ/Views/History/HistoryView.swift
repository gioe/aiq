import SwiftUI

/// History view showing past test results
struct HistoryView: View {
    @StateObject private var viewModel: HistoryViewModel
    @Environment(\.appRouter) private var router

    /// Creates a HistoryView with the specified service container
    /// - Parameter serviceContainer: Container for resolving dependencies. Defaults to the shared container.
    ///   Parent views can inject this from `@Environment(\.serviceContainer)` for better testability.
    init(serviceContainer: ServiceContainer = .shared) {
        let vm = ViewModelFactory.makeHistoryViewModel(container: serviceContainer)
        _viewModel = StateObject(wrappedValue: vm)
    }

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
                            .frame(minWidth: 44, minHeight: 44)
                    }
                    .accessibilityLabel("Filter tests by date")
                    .accessibilityHint("Opens menu to filter test history by time period")

                    // Sort Order Menu
                    Menu {
                        Picker("Sort", selection: $viewModel.sortOrder) {
                            ForEach(TestHistorySortOrder.allCases) { order in
                                Text(order.rawValue).tag(order)
                            }
                        }
                    } label: {
                        Label("Sort", systemImage: "arrow.up.arrow.down.circle")
                            .frame(minWidth: 44, minHeight: 44)
                    }
                    .accessibilityLabel("Sort test results")
                    .accessibilityHint("Opens menu to change sort order")
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
                            .accessibilityIdentifier(AccessibilityIdentifiers.HistoryView.testsTakenStat)

                            HistoryStatCard(
                                label: "Average IQ",
                                value: "\(avgScore)",
                                icon: "chart.line.uptrend.xyaxis"
                            )
                            .accessibilityIdentifier(AccessibilityIdentifiers.HistoryView.averageIQStat)

                            HistoryStatCard(
                                label: "Best Score",
                                value: "\(bestScore)",
                                icon: "star.fill"
                            )
                            .accessibilityIdentifier(AccessibilityIdentifiers.HistoryView.bestScoreStat)
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
                    .accessibilityIdentifier(AccessibilityIdentifiers.HistoryView.chartView)

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
                                .font(.subheadline)
                                .foregroundColor(.accentColor)
                                .frame(minHeight: 44)
                        }
                    }
                    .padding(.horizontal)
                    .padding(.vertical, 8)
                    .background(Color(.secondarySystemBackground))
                    .cornerRadius(8)
                    .padding(.horizontal)
                }

                // Test History List
                ForEach(Array(viewModel.testHistory.enumerated()), id: \.element.id) { index, result in
                    Button {
                        router.push(.testDetail(
                            result: result,
                            userAverage: viewModel.averageIQScore
                        ))
                    } label: {
                        TestHistoryListItem(testResult: result)
                    }
                    .buttonStyle(.plain)
                    .padding(.horizontal)
                    .accessibilityIdentifier(AccessibilityIdentifiers.HistoryView.testRow(at: index))
                }

                // Load More Button
                if viewModel.hasMore {
                    LoadMoreButton(
                        isLoading: viewModel.isLoadingMore,
                        loadedCount: viewModel.testHistory.count,
                        totalCount: viewModel.totalCount
                    ) {
                        Task {
                            await viewModel.loadMore()
                        }
                    }
                    .padding(.horizontal)
                    .padding(.top, 8)
                }
            }
            .padding(.vertical)
            .adaptiveContentWidth()
        }
        .accessibilityIdentifier(AccessibilityIdentifiers.HistoryView.scrollView)
        .refreshable {
            await viewModel.refreshHistory()
        }
        .scrollPositionPersistence(
            viewId: "historyView",
            items: viewModel.testHistory,
            shouldClear: viewModel.dateFilter != .all || viewModel.sortOrder != .newestFirst
        )
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
        .accessibilityIdentifier(AccessibilityIdentifiers.HistoryView.emptyStateView)
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
                .accessibilityHidden(true)

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
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(label): \(value)")
    }
}

/// Button for loading more paginated results
private struct LoadMoreButton: View {
    let isLoading: Bool
    let loadedCount: Int
    let totalCount: Int
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 12) {
                if isLoading {
                    ProgressView()
                        .progressViewStyle(CircularProgressViewStyle())
                        .scaleEffect(0.8)
                } else {
                    Image(systemName: "arrow.down.circle")
                        .imageScale(.medium)
                }

                VStack(alignment: .leading, spacing: 2) {
                    Text(isLoading ? "Loading..." : "Load More")
                        .font(.subheadline.weight(.medium))

                    Text("Showing \(loadedCount) of \(totalCount) tests")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }

                Spacer()
            }
            .padding()
            .frame(maxWidth: .infinity)
            .background(Color(.secondarySystemBackground))
            .cornerRadius(12)
        }
        .buttonStyle(.plain)
        .disabled(isLoading)
        .accessibilityLabel(isLoading ? "Loading more results" : "Load more results")
        .accessibilityHint("Showing \(loadedCount) of \(totalCount) tests. Double tap to load more.")
    }
}

#Preview {
    NavigationStack {
        HistoryView()
    }
}

#Preview("Large Text") {
    NavigationStack {
        HistoryView()
    }
    .environment(\.sizeCategory, .accessibilityLarge)
}
