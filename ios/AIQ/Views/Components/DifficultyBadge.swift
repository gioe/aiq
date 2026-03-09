import SwiftUI

struct DifficultyBadge: View {
    let difficultyLevel: String

    var body: some View {
        HStack(spacing: 4) {
            ForEach(0 ..< 3) { index in
                Circle()
                    .fill(index < difficultyCircles ? colorForDifficulty : Color.gray.opacity(0.2))
                    .frame(width: 8, height: 8)
                    .accessibilityHidden(true)
            }

            Text(difficultyLevel.capitalized)
                .font(.caption)
                .fontWeight(.medium)
                .foregroundColor(.secondary)
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Difficulty: \(difficultyLevel.capitalized)")
    }

    var difficultyCircles: Int {
        switch difficultyLevel {
        case "easy": 1
        case "medium": 2
        case "hard": 3
        default: 2
        }
    }

    var colorForDifficulty: Color {
        switch difficultyLevel {
        case "easy": .green
        case "medium": .orange
        case "hard": .red
        default: .orange
        }
    }
}

#Preview("All Difficulties") {
    VStack(spacing: 16) {
        DifficultyBadge(difficultyLevel: "easy")
        DifficultyBadge(difficultyLevel: "medium")
        DifficultyBadge(difficultyLevel: "hard")
    }
    .padding()
}
