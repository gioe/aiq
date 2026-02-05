import SwiftUI

/// Dashboard/Home view showing user stats and test availability
struct DashboardView: View {
    @StateObject private var viewModel: DashboardViewModel
    @ObservedObject private var authManager: AuthManager
    @EnvironmentObject var router: AppRouter

    /// Whether user skipped onboarding (determines if info card should show)
    @AppStorage("didSkipOnboarding") private var didSkipOnboarding: Bool = false

    /// Whether user has dismissed the onboarding info card
    @AppStorage("hasDismissedOnboardingInfoCard") private var hasDismissedOnboardingInfoCard: Bool = false

    /// Controls animation state for info card dismissal
    @State private var showOnboardingInfoCard: Bool = true

    /// Controls presentation of the onboarding flow
    @State private var showOnboarding: Bool = false

    /// Creates a DashboardView with the specified service container
    /// - Parameter serviceContainer: Container for resolving dependencies. Defaults to the shared container.
    ///   Parent views can inject this from `@Environment(\.serviceContainer)` for better testability.
    init(serviceContainer: ServiceContainer = .shared) {
        let vm = ViewModelFactory.makeDashboardViewModel(container: serviceContainer)
        _viewModel = StateObject(wrappedValue: vm)
        guard let resolved = serviceContainer.resolve(AuthManagerProtocol.self) as? AuthManager else {
            fatalError("AuthManagerProtocol not registered in ServiceContainer")
        }
        _authManager = ObservedObject(wrappedValue: resolved)
    }

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
        .task {
            await viewModel.fetchDashboardData()
        }
        .fullScreenCover(isPresented: $showOnboarding) {
            OnboardingContainerView()
        }
    }

    // MARK: - Dashboard Content

    private var dashboardContent: some View {
        ScrollView {
            VStack(spacing: DesignSystem.Spacing.xxl) {
                // Welcome Header
                welcomeHeader

                // Onboarding Skipped Info Card
                onboardingInfoCardSection

                // In-Progress Test Card
                if let activeSession = viewModel.activeTestSession {
                    InProgressTestCard(
                        session: activeSession,
                        questionsAnswered: viewModel.activeSessionQuestionsAnswered,
                        onResume: {
                            viewModel.trackTestResumed()
                            // Resume always uses fixed-form TestTakingView
                            router.push(.testTaking())
                        },
                        onAbandon: {
                            await viewModel.abandonActiveTest()
                        }
                    )
                    .inProgressCardTransition(sessionId: viewModel.activeTestSession?.id)
                }

                // Stats Grid
                statsGrid

                // Latest Test Result
                if let latest = viewModel.latestTestResult {
                    latestTestCard(latest)
                        .accessibilityIdentifier(AccessibilityIdentifiers.DashboardView.latestTestCard)
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
        withAnimation(DesignSystem.Animation.quick) {
            showOnboardingInfoCard = false
        }
    }

    // MARK: - Stats Grid

    private var statsGrid: some View {
        HStack(spacing: DesignSystem.Spacing.lg) {
            StatCard(
                label: "Tests Taken",
                value: "\(viewModel.testCount)",
                icon: "list.clipboard.fill",
                color: ColorPalette.statBlue,
                accessibilityId: AccessibilityIdentifiers.DashboardView.testsTakenStat
            )

            if let avgScore = viewModel.averageScore {
                StatCard(
                    label: "Average IQ",
                    value: "\(avgScore)",
                    icon: "chart.line.uptrend.xyaxis",
                    color: ColorPalette.statGreen,
                    accessibilityId: AccessibilityIdentifiers.DashboardView.averageIQStat
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

    // MARK: - Status Badge

    @ViewBuilder
    private var statusBadge: some View {
        if viewModel.hasActiveTest {
            HStack(spacing: DesignSystem.Spacing.xs) {
                Image(systemName: "exclamationmark.circle.fill")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundColor(ColorPalette.warning)

                VStack(alignment: .leading, spacing: 2) {
                    Text("Test in Progress")
                        .font(Typography.bodySmall.weight(.semibold))
                        .foregroundColor(ColorPalette.textPrimary)

                    if let questionsAnswered = viewModel.activeSessionQuestionsAnswered {
                        Text("\(questionsAnswered) questions answered")
                            .font(Typography.captionMedium)
                            .foregroundColor(ColorPalette.textSecondary)
                    }
                }

                Spacer()
            }
            .padding(.horizontal, DesignSystem.Spacing.md)
            .padding(.vertical, DesignSystem.Spacing.sm)
            .background(
                RoundedRectangle(cornerRadius: DesignSystem.CornerRadius.md)
                    .fill(ColorPalette.warning.opacity(0.1))
            )
            .overlay(
                RoundedRectangle(cornerRadius: DesignSystem.CornerRadius.md)
                    .strokeBorder(ColorPalette.warning.opacity(0.3), lineWidth: 1)
            )
            .accessibilityElement(children: .combine)
            .accessibilityLabel("Test in Progress. \(viewModel.activeSessionQuestionsAnswered ?? 0) questions answered")
        }
    }

    // MARK: - Routing Helpers

    /// Determines the correct test route based on active session and feature flags
    /// - Returns: Resume always routes to fixed-form test; new tests respect adaptive testing flag
    private func navigateToTest() {
        if viewModel.hasActiveTest {
            router.push(.testTaking())
        } else if Constants.Features.adaptiveTesting {
            router.push(.adaptiveTestTaking)
        } else {
            router.push(.testTaking())
        }
    }

    // MARK: - Action Button

    private var actionButton: some View {
        VStack(spacing: DesignSystem.Spacing.md) {
            // Status badge above button
            statusBadge

            // Action button
            Button {
                navigateToTest()
            } label: {
                HStack(spacing: DesignSystem.Spacing.sm) {
                    Image(systemName: viewModel.hasActiveTest ? "play.circle.fill" : "brain.head.profile")
                        .font(.system(size: DesignSystem.IconSize.md, weight: .semibold))

                    Text(viewModel.hasActiveTest ? "Resume Test in Progress" : "Take Another Test")
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
            .accessibilityLabel(viewModel.hasActiveTest ? "Resume Test in Progress" : "Take Another Test")
            .accessibilityHint(
                viewModel.hasActiveTest
                    ? "Continue your in-progress cognitive performance test"
                    : "Start a new cognitive performance test"
            )
            .accessibilityAddTraits(.isButton)
            .accessibilityIdentifier(AccessibilityIdentifiers.DashboardView.actionButton)
        }
    }

    // MARK: - Empty State

    private var emptyState: some View {
        ScrollView {
            VStack(spacing: DesignSystem.Spacing.xxl) {
                welcomeHeader

                // Onboarding Skipped Info Card
                onboardingInfoCardSection

                // In-Progress Test Card for empty state
                if let activeSession = viewModel.activeTestSession {
                    InProgressTestCard(
                        session: activeSession,
                        questionsAnswered: viewModel.activeSessionQuestionsAnswered,
                        onResume: {
                            // Resume always uses fixed-form TestTakingView
                            router.push(.testTaking())
                        },
                        onAbandon: {
                            await viewModel.abandonActiveTest()
                        }
                    )
                    .inProgressCardTransition(sessionId: viewModel.activeTestSession?.id)
                }

                EmptyStateView(
                    icon: viewModel.hasActiveTest ? "play.circle.fill" : "brain.head.profile",
                    title: viewModel.hasActiveTest ? "Test in Progress" : "Ready to Begin?",
                    message: viewModel.hasActiveTest ?
                        "You have a test in progress. Resume it to continue or complete it to see your results." :
                        """
                        Take your first cognitive performance assessment to establish your baseline score. \
                        Track your progress over time and discover insights about your performance.
                        """,
                    actionTitle: viewModel.hasActiveTest ? "Resume Test in Progress" : "Start Your First Test",
                    action: {
                        navigateToTest()
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
