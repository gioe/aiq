import SwiftUI

/// Dashboard/Home view showing user stats and test availability
struct DashboardView: View {
    @StateObject private var authManager = AuthManager.shared

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

                // Placeholder for test availability
                VStack(spacing: 16) {
                    Image(systemName: "brain.head.profile")
                        .font(.system(size: 60))
                        .foregroundColor(.accentColor)

                    Text("Test-taking coming soon!")
                        .font(.headline)

                    Text("IQ testing functionality will be available once the test service is integrated.")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal)
                }
                .padding(.vertical, 40)
                .frame(maxWidth: .infinity)
                .background(Color(.systemGray6))
                .cornerRadius(16)

                Spacer()
            }
            .padding()
        }
        .navigationTitle("Dashboard")
    }
}

#Preview {
    NavigationStack {
        DashboardView()
    }
}
