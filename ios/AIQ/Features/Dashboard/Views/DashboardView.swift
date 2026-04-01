import SwiftUI

/// Dashboard/Home view showing user stats and test availability
struct DashboardView: View {
    @StateObject private var viewModel: DashboardViewModel
    private let authManager: any AuthManagerProtocol
    @EnvironmentObject var router: AppRouter

    /// Whether user skipped onboarding (determines if info card should show)
    @AppStorage("didSkipOnboarding") private var didSkipOnboarding: Bool = false

    /// Whether user has dismissed the onboarding info card
    @AppStorage("hasDismissedOnboardingInfoCard") private var hasDismissedOnboardingInfoCard: Bool = false

    /// Controls animation state for info card dismissal
    @State private var showOnboardingInfoCard: Bool = true

    /// Controls presentation of the onboarding flow
    @State private var showOnboarding: Bool = false

    @Environment(\.appTheme) private var theme

    /// Creates a DashboardView with the specified service container
    /// - Parameter serviceContainer: Container for resolving dependencies. Defaults to the shared container.
    ///   Parent views can inject this from `@Environment(\.serviceContainer)` for better testability.
    init(serviceContainer: ServiceContainer = .shared) {
        let vm = ViewModelFactory.makeDashboardViewModel(container: serviceContainer)
        _viewModel = StateObject(wrappedValue: vm)
        guard let resolved = serviceContainer.resolve(AuthManagerProtocol.self) else {
            fatalError("AuthManagerProtocol not registered in ServiceContainer")
        }
        authManager = resolved
    }

    var body: some View {
        ZStack {
            // Modern gradient background
            LinearGradient(
                gradient: Gradient(colors: [
                    theme.colors.background,
                    theme.colors.backgroundSecondary.opacity(0.3)
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
            } else {
                // Single stable DashboardScrollBody instance for all four dashboard states.
                // Using a single instance with a @ViewBuilder computed property prevents SwiftUI
                // from treating each generic specialisation as a distinct view type, which would
                // destroy the scroll view context and cancel .refreshable tasks on state transitions.
                DashboardScrollBody(
                    userName: authManager.userFullName,
                    onRefresh: { await viewModel.refreshDashboard() },
                    onboardingInfoCard: { onboardingInfoCardSection },
                    bottomContent: { dashboardBottomContent }
                )
            }
        }
        .navigationTitle("Dashboard")
        .navigationBarTitleDisplayMode(.large)
        .task {
            await viewModel.fetchDashboardData()
        }
        .fullScreenCover(isPresented: $showOnboarding) {
            OnboardingContainerView()
        }
        .onReceive(NotificationCenter.default.publisher(for: .refreshCurrentView)) { _ in
            Task {
                await viewModel.refreshDashboard()
            }
        }
    }

    // MARK: - Dashboard Bottom Content

    /// Varying bottom content for the four dashboard states, provided to the single shared DashboardScrollBody.
    /// Extracting this into a @ViewBuilder computed property ensures DashboardScrollBody has a single stable
    /// concrete generic type across all state transitions, preventing .refreshable task cancellation.
    @ViewBuilder
    private var dashboardBottomContent: some View {
        if !viewModel.hasTests && !viewModel.hasActiveTest {
            // State 1: no completed tests, no active test — first-run empty state
            EmptyStateView(
                icon: "brain.head.profile",
                title: "Ready to Begin?",
                message: """
                Take your first cognitive performance assessment to establish your baseline score. \
                Track your progress over time and discover insights about your performance.
                """
            )
            .padding(.vertical, DesignSystem.Spacing.xl)

            DashboardActionButton(
                hasActiveTest: false,
                onTap: navigateToTest,
                label: "Start Your First Test"
            )
        } else if !viewModel.hasTests && viewModel.hasActiveTest {
            // State 2: active test in progress, no completed tests yet
            inProgressCardView

            Text("No completed tests yet")
                .font(theme.typography.captionMedium)
                .foregroundStyle(theme.colors.textSecondary)
                .frame(maxWidth: .infinity, alignment: .center)
                .padding(.top, DesignSystem.Spacing.sm)
                .accessibilityIdentifier(AccessibilityIdentifiers.DashboardView.noCompletedTestsNote)
        } else if viewModel.hasTests && !viewModel.hasActiveTest {
            // State 3: completed tests exist, no active test — new test CTA only
            DashboardActionButton(hasActiveTest: false, onTap: navigateToTest)
        } else {
            // State 4: completed tests exist + active test in progress — in-progress card only
            // No "Take Another Test" CTA here by design: only one test session can be active at a time.
            // InProgressTestCard's own Abandon action transitions back to State 3 where the CTA appears.
            inProgressCardView
        }
    }

    // MARK: - Onboarding Info Card

    /// Whether the onboarding info card should be displayed
    private var shouldShowOnboardingInfoCard: Bool {
        didSkipOnboarding && !hasDismissedOnboardingInfoCard && showOnboardingInfoCard
    }

    /// Info card section for users who skipped onboarding
    @ViewBuilder
    private var onboardingInfoCardSection: some View {
        if shouldShowOnboardingInfoCard {
            OnboardingSkippedInfoCard(
                onLearnMore: {
                    // Opening onboarding counts as addressing the skip, even if
                    // user dismisses partway through. Card won't reappear.
                    hasDismissedOnboardingInfoCard = true
                    didSkipOnboarding = false
                    showOnboarding = true
                },
                onDismiss: {
                    dismissOnboardingInfoCard()
                }
            )
            .transition(.asymmetric(
                insertion: .opacity,
                removal: .scale(scale: 0.95).combined(with: .opacity)
            ))
        }
    }

    /// Dismisses the onboarding info card with animation
    private func dismissOnboardingInfoCard() {
        // Persist dismissal immediately to avoid race conditions with app backgrounding
        hasDismissedOnboardingInfoCard = true
        withAnimation(theme.animations.quick) {
            showOnboardingInfoCard = false
        }
    }

    // MARK: - In-Progress Card

    /// Renders the in-progress test card with its transition modifier for the current active session.
    /// Both State 2 and State 4 use this helper to avoid duplication.
    @ViewBuilder
    private var inProgressCardView: some View {
        if let activeSession = viewModel.activeTestSession {
            InProgressTestCard(
                session: activeSession,
                questionsAnswered: viewModel.activeSessionQuestionsAnswered,
                onResume: {
                    viewModel.trackTestResumed()
                    router.push(.testTaking(sessionId: activeSession.id))
                },
                onAbandon: { await viewModel.abandonActiveTest() }
            )
            .inProgressCardTransition(sessionId: activeSession.id)
        }
    }

    // MARK: - Routing Helpers

    /// Determines the correct test route based on active session and feature flags
    /// - Returns: Resume always routes to fixed-form test; new tests respect adaptive testing flag
    private func navigateToTest() {
        if viewModel.hasActiveTest {
            router.push(.testTaking(sessionId: viewModel.activeTestSession?.id))
        } else if Constants.Features.adaptiveTesting {
            router.push(.adaptiveTestTaking)
        } else {
            router.push(.testTaking())
        }
    }
}

// MARK: - Shared Scroll Body

/// Shared scroll container used by all four dashboard states.
/// Renders the common preamble (header, onboarding card) followed by
/// caller-supplied content via a @ViewBuilder closure.
struct DashboardScrollBody<OnboardingCard: View, BottomContent: View>: View {
    let userName: String?
    let onRefresh: () async -> Void
    @ViewBuilder let onboardingInfoCard: OnboardingCard
    @ViewBuilder let bottomContent: BottomContent

    var body: some View {
        ScrollView {
            VStack(spacing: DesignSystem.Spacing.xxl) {
                DashboardWelcomeHeader(userName: userName)

                onboardingInfoCard

                bottomContent

                Spacer()
            }
            .padding(DesignSystem.Spacing.lg)
            .adaptiveContentWidth()
        }
        .refreshable {
            await onRefresh()
        }
    }
}

// MARK: - View Modifiers

/// View modifier for applying consistent transition and animation to InProgressTestCard
private struct InProgressCardTransition: ViewModifier {
    let sessionId: Int?
    @Environment(\.accessibilityReduceMotion) var reduceMotion

    func body(content: Content) -> some View {
        if reduceMotion {
            content
                .transition(.opacity)
                .animation(nil, value: sessionId)
        } else {
            content
                .transition(.asymmetric(
                    insertion: .scale(scale: 0.9).combined(with: .opacity),
                    removal: .scale(scale: 0.9).combined(with: .opacity)
                ))
                .animation(.spring(response: 0.4, dampingFraction: 0.8), value: sessionId)
        }
    }
}

private extension View {
    func inProgressCardTransition(sessionId: Int?) -> some View {
        modifier(InProgressCardTransition(sessionId: sessionId))
    }
}

#Preview {
    NavigationStack {
        DashboardView()
    }
}
