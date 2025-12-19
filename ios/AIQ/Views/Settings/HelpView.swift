import SwiftUI

/// Help and FAQ view for user guidance
struct HelpView: View {
    var body: some View {
        List {
            // Understanding Your Score Section
            Section {
                NavigationLink {
                    ScoreRangeHelpView()
                } label: {
                    HelpRowView(
                        icon: "chart.bar.xaxis",
                        title: "Understanding Score Ranges",
                        description: "Learn what the score range means"
                    )
                }

                NavigationLink {
                    IQScoreHelpView()
                } label: {
                    HelpRowView(
                        icon: "brain.head.profile",
                        title: "How IQ Scores Work",
                        description: "What your score represents"
                    )
                }
            } header: {
                Text("Understanding Your Score")
            }

            // Test Information Section
            Section {
                NavigationLink {
                    TestFrequencyHelpView()
                } label: {
                    HelpRowView(
                        icon: "calendar.badge.clock",
                        title: "Test Frequency",
                        description: "How often you can test"
                    )
                }

                NavigationLink {
                    QuestionTypesHelpView()
                } label: {
                    HelpRowView(
                        icon: "questionmark.circle",
                        title: "Question Types",
                        description: "Categories of cognitive assessment"
                    )
                }
            } header: {
                Text("About the Test")
            }

            // Privacy & Data Section
            Section {
                NavigationLink {
                    DataPrivacyHelpView()
                } label: {
                    HelpRowView(
                        icon: "lock.shield",
                        title: "Your Data & Privacy",
                        description: "How we handle your information"
                    )
                }
            } header: {
                Text("Privacy")
            }
        }
        .navigationTitle("Help & FAQ")
    }
}

// MARK: - Help Row Component

private struct HelpRowView: View {
    let icon: String
    let title: String
    let description: String

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .font(.system(size: 20))
                .foregroundColor(.accentColor)
                .frame(width: 32)

            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.body)
                Text(description)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
        .padding(.vertical, 4)
    }
}

// MARK: - Score Range Help View

struct ScoreRangeHelpView: View {
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                // Header
                VStack(alignment: .leading, spacing: 8) {
                    Image(systemName: "chart.bar.xaxis")
                        .font(.system(size: 40))
                        .foregroundColor(.accentColor)

                    Text("Understanding Your Score Range")
                        .font(.title2)
                        .fontWeight(.bold)
                }
                .padding(.bottom, 8)

                // Main explanation
                VStack(alignment: .leading, spacing: 16) {
                    Text("What is a Score Range?")
                        .font(.headline)

                    Text("""
                    When you receive your IQ score, you may also see a range \
                    (for example, "Range: 101-115"). This range is called a \
                    confidence interval, and it's an important part of \
                    understanding your results.
                    """)
                    .foregroundColor(.secondary)

                    Divider()

                    Text("Why Scores Have Ranges")
                        .font(.headline)

                    Text("""
                    Your displayed score represents our best estimate of your \
                    cognitive ability. However, due to the nature of measurement, \
                    no single test can capture your exact ability with perfect \
                    precision.

                    The score range shows the interval within which your true \
                    ability likely falls. When we report a 95% confidence interval, \
                    it means there's a 95% probability that your true score is \
                    somewhere within that range.
                    """)
                    .foregroundColor(.secondary)

                    Divider()

                    Text("Example")
                        .font(.headline)

                    HStack {
                        Image(systemName: "lightbulb")
                            .foregroundColor(.yellow)
                        Text("""
                        If your score is 108 with a range of 101-115, this means \
                        your cognitive ability most likely falls between 101 and 115, \
                        with 108 being the best single estimate.
                        """)
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    }
                    .padding()
                    .background(Color(.systemGray6))
                    .cornerRadius(12)

                    Divider()

                    Text("What Affects the Range Width?")
                        .font(.headline)

                    Text("""
                    Narrower ranges indicate more precise measurements. The width \
                    of your score range depends on the test's reliability - how \
                    consistently it measures cognitive ability.

                    As more users take tests and we gather more data, our \
                    measurements become more precise, leading to narrower ranges.
                    """)
                    .foregroundColor(.secondary)
                }
            }
            .padding()
        }
        .navigationTitle("Score Ranges")
        .navigationBarTitleDisplayMode(.inline)
    }
}

// MARK: - IQ Score Help View

struct IQScoreHelpView: View {
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                // Header
                VStack(alignment: .leading, spacing: 8) {
                    Image(systemName: "brain.head.profile")
                        .font(.system(size: 40))
                        .foregroundColor(.accentColor)

                    Text("How IQ Scores Work")
                        .font(.title2)
                        .fontWeight(.bold)
                }
                .padding(.bottom, 8)

                VStack(alignment: .leading, spacing: 16) {
                    Text("The IQ Scale")
                        .font(.headline)

                    Text("""
                    IQ scores are standardized so that the average score is 100, \
                    with a standard deviation of 15. This means about 68% of \
                    people score between 85 and 115.
                    """)
                    .foregroundColor(.secondary)

                    // Score ranges table
                    VStack(spacing: 8) {
                        scoreRangeRow("145+", "Highly Gifted", .purple)
                        scoreRangeRow("130-144", "Gifted", .blue)
                        scoreRangeRow("115-129", "Above Average", .cyan)
                        scoreRangeRow("85-114", "Average", .green)
                        scoreRangeRow("70-84", "Below Average", .orange)
                        scoreRangeRow("Below 70", "Significantly Below Average", .red)
                    }
                    .padding()
                    .background(Color(.systemGray6))
                    .cornerRadius(12)

                    Divider()

                    Text("Important Notes")
                        .font(.headline)

                    Text("""
                    This app provides a cognitive performance assessment for \
                    personal insight. It is not a clinical IQ test and should \
                    not be used for diagnostic purposes.

                    Your score may vary between tests due to factors like fatigue, \
                    stress, or practice effects. Focus on your overall trend \
                    rather than any single score.
                    """)
                    .foregroundColor(.secondary)
                }
            }
            .padding()
        }
        .navigationTitle("IQ Scores")
        .navigationBarTitleDisplayMode(.inline)
    }

    private func scoreRangeRow(_ range: String, _ label: String, _ color: Color) -> some View {
        HStack {
            Text(range)
                .font(.subheadline)
                .fontWeight(.medium)
                .frame(width: 80, alignment: .leading)
            Text(label)
                .font(.subheadline)
                .foregroundColor(.secondary)
            Spacer()
            Circle()
                .fill(color)
                .frame(width: 12, height: 12)
        }
    }
}

// MARK: - Test Frequency Help View

struct TestFrequencyHelpView: View {
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                // Header
                VStack(alignment: .leading, spacing: 8) {
                    Image(systemName: "calendar.badge.clock")
                        .font(.system(size: 40))
                        .foregroundColor(.accentColor)

                    Text("Test Frequency")
                        .font(.title2)
                        .fontWeight(.bold)
                }
                .padding(.bottom, 8)

                VStack(alignment: .leading, spacing: 16) {
                    Text("Why 3 Months Between Tests?")
                        .font(.headline)

                    Text("""
                    We recommend waiting at least 3 months between tests for \
                    several important reasons:

                    1. **Avoid Practice Effects**: Taking the same types of \
                    questions too frequently can artificially inflate your scores.

                    2. **Track Meaningful Changes**: Cognitive abilities are \
                    relatively stable over short periods. A 3-month gap allows \
                    for detecting genuine improvements or changes.

                    3. **Fresh Questions**: We ensure you receive different \
                    questions each time, which requires adequate time between tests.

                    4. **Reduce Test Anxiety**: Frequent testing can create \
                    unnecessary stress. Periodic assessments are healthier.
                    """)
                    .foregroundColor(.secondary)

                    Divider()

                    Text("Notifications")
                        .font(.headline)

                    Text("""
                    You can enable notifications in Settings to receive a \
                    reminder when it's time for your next test.
                    """)
                    .foregroundColor(.secondary)
                }
            }
            .padding()
        }
        .navigationTitle("Test Frequency")
        .navigationBarTitleDisplayMode(.inline)
    }
}

// MARK: - Question Types Help View

struct QuestionTypesHelpView: View {
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                // Header
                VStack(alignment: .leading, spacing: 8) {
                    Image(systemName: "questionmark.circle")
                        .font(.system(size: 40))
                        .foregroundColor(.accentColor)

                    Text("Question Types")
                        .font(.title2)
                        .fontWeight(.bold)
                }
                .padding(.bottom, 8)

                VStack(alignment: .leading, spacing: 16) {
                    Text("""
                    Our tests assess multiple cognitive domains to provide a \
                    comprehensive picture of your abilities:
                    """)
                    .foregroundColor(.secondary)

                    domainCard(
                        icon: "square.grid.3x3",
                        name: "Pattern Recognition",
                        description: "Identifying visual patterns and sequences"
                    )

                    domainCard(
                        icon: "arrow.triangle.branch",
                        name: "Logical Reasoning",
                        description: "Drawing conclusions from given information"
                    )

                    domainCard(
                        icon: "cube.transparent",
                        name: "Spatial Reasoning",
                        description: "Mentally manipulating shapes and objects"
                    )

                    domainCard(
                        icon: "function",
                        name: "Mathematical",
                        description: "Numerical problem-solving and calculations"
                    )

                    domainCard(
                        icon: "text.book.closed",
                        name: "Verbal Reasoning",
                        description: "Understanding language and word relationships"
                    )

                    domainCard(
                        icon: "memorychip",
                        name: "Memory",
                        description: "Retaining and recalling information"
                    )
                }
            }
            .padding()
        }
        .navigationTitle("Question Types")
        .navigationBarTitleDisplayMode(.inline)
    }

    private func domainCard(icon: String, name: String, description: String) -> some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .font(.system(size: 24))
                .foregroundColor(.accentColor)
                .frame(width: 40)

            VStack(alignment: .leading, spacing: 4) {
                Text(name)
                    .font(.subheadline)
                    .fontWeight(.semibold)
                Text(description)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            Spacer()
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
}

// MARK: - Data Privacy Help View

struct DataPrivacyHelpView: View {
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                // Header
                VStack(alignment: .leading, spacing: 8) {
                    Image(systemName: "lock.shield")
                        .font(.system(size: 40))
                        .foregroundColor(.accentColor)

                    Text("Your Data & Privacy")
                        .font(.title2)
                        .fontWeight(.bold)
                }
                .padding(.bottom, 8)

                VStack(alignment: .leading, spacing: 16) {
                    Text("What We Collect")
                        .font(.headline)

                    Text("""
                    We collect only the information necessary to provide you \
                    with accurate cognitive assessments:

                    - Your test answers and scores
                    - Time spent on each question
                    - Account information you provide

                    We do not sell your personal data or share it with third parties.
                    """)
                    .foregroundColor(.secondary)

                    Divider()

                    Text("How We Use Your Data")
                        .font(.headline)

                    Text("""
                    Your data helps us:

                    - Calculate accurate scores and track your progress
                    - Improve our questions and scoring algorithms
                    - Provide you with personalized insights

                    All data is stored securely and encrypted.
                    """)
                    .foregroundColor(.secondary)

                    Divider()

                    Text("Your Rights")
                        .font(.headline)

                    Text("""
                    You can request to view, export, or delete your data at \
                    any time by contacting our support team.
                    """)
                    .foregroundColor(.secondary)
                }
            }
            .padding()
        }
        .navigationTitle("Privacy")
        .navigationBarTitleDisplayMode(.inline)
    }
}

// MARK: - Previews

#Preview("Help View") {
    NavigationStack {
        HelpView()
    }
}

#Preview("Score Range Help") {
    NavigationStack {
        ScoreRangeHelpView()
    }
}

#Preview("IQ Score Help") {
    NavigationStack {
        IQScoreHelpView()
    }
}
