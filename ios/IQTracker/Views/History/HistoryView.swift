import SwiftUI

/// History view showing past test results
struct HistoryView: View {
    var body: some View {
        VStack(spacing: 24) {
            Image(systemName: "chart.xyaxis.line")
                .font(.system(size: 60))
                .foregroundColor(.accentColor)

            Text("No test history yet")
                .font(.headline)

            Text("Your test results will appear here once you complete your first IQ test.")
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 40)

            Spacer()
        }
        .padding()
        .padding(.top, 60)
        .navigationTitle("History")
    }
}

#Preview {
    NavigationStack {
        HistoryView()
    }
}
