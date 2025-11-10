import SwiftUI

/// Dashboard/Home view showing user stats and test availability
struct DashboardView: View {
    @StateObject private var authManager = AuthManager.shared
    @State private var navigateToTest = false

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                // Welcome Header
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

                // Empty state for new users
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
        .navigationTitle("Dashboard")
        .navigationDestination(isPresented: $navigateToTest) {
            TestTakingView()
        }
    }
}

#Preview {
    NavigationStack {
        DashboardView()
    }
}
