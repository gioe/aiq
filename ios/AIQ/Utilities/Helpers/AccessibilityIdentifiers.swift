//
//  AccessibilityIdentifiers.swift
//  AIQ
//
//  Created by Claude Code on 12/25/24.
//

import Foundation

/// Centralized accessibility identifiers for UI testing
///
/// Usage:
/// ```swift
/// .accessibilityIdentifier(AccessibilityIdentifiers.WelcomeView.emailTextField)
/// ```
///
/// These identifiers provide stable element references for UI tests,
/// preventing test breakage when UI text changes due to localization or copy updates.
enum AccessibilityIdentifiers {
    // MARK: - Onboarding View

    enum OnboardingView {
        static let containerView = "onboardingView.containerView"
        static let page1 = "onboardingView.page1"
        static let page2 = "onboardingView.page2"
        static let page3 = "onboardingView.page3"
        static let page4 = "onboardingView.page4"
        static let continueButton = "onboardingView.continueButton"
        static let skipButton = "onboardingView.skipButton"
        static let getStartedButton = "onboardingView.getStartedButton"
        static let privacyPolicyLink = "onboardingView.privacyPolicyLink"
    }

    // MARK: - Privacy Consent View

    enum PrivacyConsentView {
        static let privacyIcon = "privacyConsentView.privacyIcon"
        static let privacyPolicyLink = "privacyConsentView.privacyPolicyLink"
        static let termsOfServiceLink = "privacyConsentView.termsOfServiceLink"
        static let acceptButton = "privacyConsentView.acceptButton"
    }

    // MARK: - Welcome View

    enum WelcomeView {
        static let emailTextField = "welcomeView.emailTextField"
        static let passwordTextField = "welcomeView.passwordTextField"
        static let signInButton = "welcomeView.signInButton"
        static let createAccountButton = "welcomeView.createAccountButton"
        static let brainIcon = "welcomeView.brainIcon"
        static let errorBanner = "welcomeView.errorBanner"
    }

    // MARK: - Registration View

    enum RegistrationView {
        static let firstNameTextField = "registrationView.firstNameTextField"
        static let lastNameTextField = "registrationView.lastNameTextField"
        static let emailTextField = "registrationView.emailTextField"
        static let passwordTextField = "registrationView.passwordTextField"
        static let confirmPasswordTextField = "registrationView.confirmPasswordTextField"
        static let createAccountButton = "registrationView.createAccountButton"
        static let signInLink = "registrationView.signInLink"
    }

    // MARK: - Dashboard View

    enum DashboardView {
        static let scrollView = "dashboardView.scrollView"
        static let testsTakenStat = "dashboardView.testsTakenStat"
        static let averageIQStat = "dashboardView.averageIQStat"
        static let latestTestCard = "dashboardView.latestTestCard"
        static let actionButton = "dashboardView.actionButton"
        static let resumeButton = "dashboardView.resumeButton"
        static let inProgressTestCard = "dashboardView.inProgressTestCard"
        static let abandonTestButton = "dashboardView.abandonTestButton"
        static let emptyStateView = "dashboardView.emptyStateView"
    }

    // MARK: - Test Taking View

    enum TestTakingView {
        static let questionCard = "testTakingView.questionCard"
        static let questionText = "testTakingView.questionText"
        static let progressLabel = "testTakingView.progressLabel"
        static let progressBar = "testTakingView.progressBar"
        static let answerTextField = "testTakingView.answerTextField"
        // Append index: answerButton.0, answerButton.1, etc.
        static let answerButtonPrefix = "testTakingView.answerButton"
        static let previousButton = "testTakingView.previousButton"
        static let nextButton = "testTakingView.nextButton"
        static let submitButton = "testTakingView.submitButton"
        static let exitButton = "testTakingView.exitButton"
        static let timerLabel = "testTakingView.timerLabel"
        static let timeWarningBanner = "testTakingView.timeWarningBanner"
        static let questionNavigationGrid = "testTakingView.questionNavigationGrid"

        /// Generate identifier for answer button at specific index
        static func answerButton(at index: Int) -> String {
            "\(answerButtonPrefix).\(index)"
        }

        /// Generate identifier for question navigation button at specific index
        static func questionNavigationButton(at index: Int) -> String {
            "testTakingView.questionNavigationButton.\(index)"
        }
    }

    // MARK: - Test Results View

    enum TestResultsView {
        static let scoreLabel = "testResultsView.scoreLabel"
        static let performanceLabel = "testResultsView.performanceLabel"
        static let domainScoresSection = "testResultsView.domainScoresSection"
        static let doneButton = "testResultsView.doneButton"
        static let shareButton = "testResultsView.shareButton"
    }

    // MARK: - Test Detail View

    enum TestDetailView {
        static let container = "testDetailView"
        static let scoreLabel = "testDetailView.scoreLabel"
        static let dateLabel = "testDetailView.dateLabel"
        static let domainScoresSection = "testDetailView.domainScoresSection"
        static let backButton = "testDetailView.backButton"
    }

    // MARK: - Settings View

    enum SettingsView {
        static let accountSection = "settingsView.accountSection"
        static let notificationsSection = "settingsView.notificationsSection"
        static let helpButton = "settingsView.helpButton"
        static let logoutButton = "settingsView.logoutButton"
        static let deleteAccountButton = "settingsView.deleteAccountButton"
        static let appVersionLabel = "settingsView.appVersionLabel"
        static let debugSection = "settingsView.debugSection"
        static let testCrashButton = "settingsView.testCrashButton"
    }

    // MARK: - History View

    enum HistoryView {
        static let scrollView = "historyView.scrollView"
        static let emptyStateView = "historyView.emptyStateView"
        static let chartView = "historyView.chartView"
        static let testListPrefix = "historyView.testRow" // Append index: testRow.0, testRow.1, etc.

        /// Generate identifier for test row at specific index
        static func testRow(at index: Int) -> String {
            "\(testListPrefix).\(index)"
        }
    }

    // MARK: - Navigation Tabs

    enum TabBar {
        static let dashboardTab = "tabBar.dashboardTab"
        static let historyTab = "tabBar.historyTab"
        static let settingsTab = "tabBar.settingsTab"
    }

    // MARK: - Common Components

    enum Common {
        static let loadingView = "common.loadingView"
        static let errorView = "common.errorView"
        static let retryButton = "common.retryButton"
        static let primaryButton = "common.primaryButton"
        static let secondaryButton = "common.secondaryButton"
    }

    // MARK: - Notification Settings

    enum NotificationSettings {
        static let enableNotificationsToggle = "notificationSettings.enableNotificationsToggle"
        static let permissionButton = "notificationSettings.permissionButton"
        static let statusLabel = "notificationSettings.statusLabel"
    }

    // MARK: - Help View

    enum HelpView {
        static let scrollView = "helpView.scrollView"
        static let contactSupportButton = "helpView.contactSupportButton"
        static let faqSection = "helpView.faqSection"
    }
}
