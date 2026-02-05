import SwiftUI

/// Main onboarding container view with page navigation
/// Uses TabView for swipe-based page transitions
///
/// ## App Store Privacy Compliance
///
/// This view intentionally does **not** fire any analytics events. Per App Store privacy
/// requirements, users can view the full onboarding flow before registration/login.
/// Analytics tracking only begins after the user:
///
/// 1. Accepts the privacy policy (via `PrivacyConsentView`)
/// 2. Completes authentication (registration or login)
///
/// The onboarding pages display educational content without tracking user interactions,
/// ensuring compliance with Apple's privacy guidelines. All analytics events are defined
/// in `AnalyticsService` and only fire post-authentication.
///
/// - SeeAlso: `RootView` for the consent-first navigation flow
/// - SeeAlso: `AnalyticsService` for the privacy-preserving analytics implementation
struct OnboardingContainerView: View {
    @StateObject private var viewModel = OnboardingViewModel()
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        ZStack {
            // Background
            ColorPalette.background
                .ignoresSafeArea()

            VStack(spacing: 0) {
                // Skip Button (top-right, pages 0-2 only)
                HStack {
                    Spacer()

                    if viewModel.shouldShowSkip {
                        Button(String(localized: "onboarding.skip")) {
                            handleSkip()
                        }
                        .font(Typography.labelLarge)
                        .foregroundColor(ColorPalette.primary)
                        .frame(minWidth: 44, minHeight: 44)
                        .padding(.horizontal, DesignSystem.Spacing.xl)
                        .padding(.top, DesignSystem.Spacing.md)
                        .accessibilityIdentifier(AccessibilityIdentifiers.OnboardingView.skipButton)
                        .accessibilityHint(String(localized: "onboarding.skip.hint"))
                    }
                }

                // TabView with Pages
                TabView(selection: $viewModel.currentPage) {
                    OnboardingPage1View()
                        .tag(0)

                    OnboardingPage2View()
                        .tag(1)

                    OnboardingPage3View()
                        .tag(2)

                    OnboardingPage4View()
                        .tag(3)
                }
                .tabViewStyle(.page(indexDisplayMode: .never))
                .onChange(of: viewModel.currentPage) { _ in
                    // Haptic feedback on page change (respects Reduce Motion via HapticManager)
                    ServiceContainer.shared.resolve(HapticManagerProtocol.self)?.trigger(.light)
                }

                // Custom page indicator (scoped styling, no global UIPageControl modifications)
                PageIndicator(currentPage: $viewModel.currentPage, totalPages: 4)
                    .padding(.bottom, DesignSystem.Spacing.md)

                // Bottom Button Area
                VStack(spacing: DesignSystem.Spacing.md) {
                    if viewModel.isLastPage {
                        // Get Started Button (final page only)
                        PrimaryButton(
                            title: String(localized: "onboarding.get.started"),
                            action: handleGetStarted,
                            accessibilityId: AccessibilityIdentifiers.OnboardingView.getStartedButton
                        )
                        .padding(.horizontal, DesignSystem.Spacing.xxl)
                    } else {
                        // Continue Button (pages 0-2)
                        PrimaryButton(
                            title: String(localized: "onboarding.continue"),
                            action: handleContinue,
                            accessibilityId: AccessibilityIdentifiers.OnboardingView.continueButton
                        )
                        .padding(.horizontal, DesignSystem.Spacing.xxl)
                    }
                }
                .padding(.bottom, DesignSystem.Spacing.xl)
            }
        }
        .accessibilityIdentifier(AccessibilityIdentifiers.OnboardingView.containerView)
        .onAppear {
            // Prepare haptic generators for reduced latency on first use
            ServiceContainer.shared.resolve(HapticManagerProtocol.self)?.prepare()
        }
    }

    // MARK: - Actions

    /// Handle Continue button tap
    private func handleContinue() {
        // Haptic feedback (respects Reduce Motion via HapticManager)
        ServiceContainer.shared.resolve(HapticManagerProtocol.self)?.trigger(.medium)

        // Navigate to next page
        if reduceMotion {
            viewModel.nextPage()
        } else {
            withAnimation(DesignSystem.Animation.smooth) {
                viewModel.nextPage()
            }
        }
    }

    /// Handle Skip button tap
    private func handleSkip() {
        // Haptic feedback (respects Reduce Motion via HapticManager)
        ServiceContainer.shared.resolve(HapticManagerProtocol.self)?.trigger(.medium)

        // Skip onboarding
        if reduceMotion {
            viewModel.skipOnboarding()
        } else {
            withAnimation(DesignSystem.Animation.smooth) {
                viewModel.skipOnboarding()
            }
        }

        // Dismiss if presented as a sheet (e.g., from Settings)
        dismiss()
    }

    /// Handle Get Started button tap
    private func handleGetStarted() {
        // Haptic feedback (respects Reduce Motion via HapticManager)
        ServiceContainer.shared.resolve(HapticManagerProtocol.self)?.trigger(.success)

        // Complete onboarding
        if reduceMotion {
            viewModel.completeOnboarding()
        } else {
            withAnimation(DesignSystem.Animation.smooth) {
                viewModel.completeOnboarding()
            }
        }

        // Dismiss if presented as a sheet (e.g., from Settings)
        dismiss()
    }
}

// MARK: - Previews

#Preview("Light Mode") {
    OnboardingContainerView()
}

#Preview("Dark Mode") {
    OnboardingContainerView()
        .preferredColorScheme(.dark)
}

#Preview("Large Text") {
    OnboardingContainerView()
        .environment(\.sizeCategory, .accessibilityLarge)
}
