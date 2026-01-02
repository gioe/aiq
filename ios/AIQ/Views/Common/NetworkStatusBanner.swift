import SwiftUI

/// Banner that appears when network connectivity is lost
struct NetworkStatusBanner: View {
    let isConnected: Bool

    @Environment(\.accessibilityReduceMotion) var reduceMotion

    var body: some View {
        if !isConnected {
            HStack(spacing: 12) {
                Image(systemName: "wifi.slash")
                    .foregroundColor(.white)

                Text("network.no.connection".localized)
                    .font(.subheadline)
                    .foregroundColor(.white)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 12)
            .background(Color.orange)
            .transition(reduceMotion ? .opacity : .move(edge: .top).combined(with: .opacity))
        }
    }
}

#Preview {
    VStack {
        NetworkStatusBanner(isConnected: false)
        Spacer()
    }
}
