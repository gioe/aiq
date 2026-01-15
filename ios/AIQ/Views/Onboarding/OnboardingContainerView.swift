import SwiftUI
import UIKit

/// Main onboarding container view with page navigation
/// Uses TabView for swipe-based page transitions
struct OnboardingContainerView: View {
    @StateObject private var viewModel = OnboardingViewModel()
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    @Environment(\.dismiss) private var dismiss

    // Reusable haptic generators (created once, reused throughout lifecycle)
    private let lightImpactGenerator = UIImpactFeedbackGenerator(style: .light)
    private let mediumImpactGenerator = UIImpactFeedbackGenerator(style: .medium)
    private let notificationGenerator = UINotificationFeedbackGenerator()

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
                    // Haptic feedback on page change
                    lightImpactGenerator.impactOccurred()
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
            lightImpactGenerator.prepare()
            mediumImpactGenerator.prepare()
            notificationGenerator.prepare()
        }
    }

    // MARK: - Actions

    /// Handle Continue button tap
    private func handleContinue() {
        // Haptic feedback
        mediumImpactGenerator.impactOccurred()

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
        // Haptic feedback
        mediumImpactGenerator.impactOccurred()

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
        // Haptic feedback
        notificationGenerator.notificationOccurred(.success)

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

#Preview {
    OnboardingContainerView()
}
