import SwiftUI
import UIKit

/// Main onboarding container view with page navigation
/// Uses TabView for swipe-based page transitions
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
                        Button("Skip") {
                            handleSkip()
                        }
                        .font(Typography.labelLarge)
                        .foregroundColor(ColorPalette.primary)
                        .frame(minWidth: 44, minHeight: 44)
                        .padding(.horizontal, DesignSystem.Spacing.xl)
                        .padding(.top, DesignSystem.Spacing.md)
                        .accessibilityIdentifier(AccessibilityIdentifiers.OnboardingView.skipButton)
                        .accessibilityHint("Double tap to skip onboarding")
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
                .tabViewStyle(.page(indexDisplayMode: .always))
                .indexViewStyle(PageIndexViewStyle(backgroundDisplayMode: .always))
                .onAppear {
                    configurePageControl()
                }
                .onChange(of: viewModel.currentPage) { _ in
                    // Haptic feedback on page change
                    let generator = UIImpactFeedbackGenerator(style: .light)
                    generator.impactOccurred()
                }

                // Bottom Button Area
                VStack(spacing: DesignSystem.Spacing.md) {
                    if viewModel.isLastPage {
                        // Get Started Button (final page only)
                        PrimaryButton(
                            title: "Get Started",
                            action: handleGetStarted,
                            accessibilityId: AccessibilityIdentifiers.OnboardingView.getStartedButton
                        )
                        .padding(.horizontal, DesignSystem.Spacing.xxl)
                    } else {
                        // Continue Button (pages 0-2)
                        PrimaryButton(
                            title: "Continue",
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
    }

    // MARK: - Actions

    /// Handle Continue button tap
    private func handleContinue() {
        // Haptic feedback
        let generator = UIImpactFeedbackGenerator(style: .medium)
        generator.impactOccurred()

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
        let generator = UIImpactFeedbackGenerator(style: .medium)
        generator.impactOccurred()

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
        let generator = UINotificationFeedbackGenerator()
        generator.notificationOccurred(.success)

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

    // MARK: - Configuration

    /// Configure UIPageControl appearance for onboarding
    /// - Note: This modifies the global UIPageControl appearance, affecting all TabView page indicators
    ///   throughout the app. SwiftUI does not currently provide a scoped API for customizing
    ///   page indicators within a single TabView. If different styling is needed elsewhere,
    ///   consider implementing a custom page indicator component.
    private func configurePageControl() {
        let appearance = UIPageControl.appearance()
        appearance.currentPageIndicatorTintColor = UIColor(ColorPalette.primary)
        appearance.pageIndicatorTintColor = UIColor(ColorPalette.textTertiary)
    }
}

#Preview {
    OnboardingContainerView()
}
