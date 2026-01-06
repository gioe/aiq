# IQTrendChart Accessibility Spike (BTS-166)

**Author:** ios-engineer agent
**Date:** 2026-01-05
**Status:** Research Complete
**Related Ticket:** BTS-166

## Executive Summary

This spike investigated best practices for making the IQTrendChart component accessible to users with visual impairments. The primary finding is that **Swift Charts provides automatic Audio Graph support** (iOS 15+), which is the gold standard for chart accessibility on iOS. However, our current implementation using `.accessibilityElement(children: .combine)` with a text description provides a solid baseline.

**Recommendation:** Implement Audio Graphs using `AXChartDescriptor` to provide industry-leading accessibility for blind and low-vision users.

---

## Current Implementation Analysis

### What We Have

Location: `ios/AIQ/Views/History/IQTrendChart.swift`

**Accessibility Features:**
- `.accessibilityElement(children: .combine)` - Combines chart elements into single VoiceOver element
- Detailed text accessibility label with:
  - Number of test results
  - Score range (min/max)
  - Average score
  - Date range
  - Confidence interval explanation (when applicable)
- Legend has separate accessibility label for "95% CI"

**Strengths:**
- Provides comprehensive text description
- Conveys all key statistics (range, average, count)
- Explains confidence intervals
- Follows current coding standards

**Limitations:**
- Text-only - users cannot explore individual data points
- No audio representation of trends
- Cannot navigate through specific test results
- Missing the interactive "audio graph" feature available in iOS 15+

---

## Investigation Findings

### 1. iOS Chart Accessibility Best Practices

#### Apple's Recommendations

**From WWDC21 "Bring accessibility to charts in your app":**
- Charts should provide multiple accessibility modes:
  1. **Summary** - Brief description of key insights
  2. **Individual data point navigation** - Let users explore each point
  3. **Audio Graphs** - Sonification of data for blind users

**Key Principle:** "Charts are not inherently accessible for blind or low-vision people. There's no value in a visual chart if you can't see it."

#### WCAG Guidelines for Data Visualization

Based on WCAG 2.1 Level AA standards:

1. **Text Alternatives (1.1.1):**
   - Provide alt text describing purpose and key insights
   - Include data tables as alternatives to complex visualizations
   - Current implementation: PARTIAL - We have text description but no data table

2. **Color Contrast (1.4.3, 1.4.11):**
   - 4.5:1 for text, 3:1 for graphical objects
   - Don't rely solely on color to convey information
   - Current implementation: PASS - Using DesignSystem colors with sufficient contrast

3. **Non-Text Contrast (1.4.11):**
   - Chart elements need sufficient contrast from background
   - Use patterns/textures in addition to colors
   - Current implementation: PARTIAL - Using color but could add patterns for confidence intervals

4. **Keyboard Accessibility (2.1.1):**
   - Interactive charts must be keyboard navigable
   - Current implementation: N/A - Chart is not interactive

**Sources:**
- [WWDC21: Bring accessibility to charts in your app](https://developer.apple.com/videos/play/wwdc2021/10122/)
- [iOS Accessibility Guidelines: Best Practices for 2025](https://medium.com/@david-auerbach/ios-accessibility-guidelines-best-practices-for-2025-6ed0d256200e)

### 2. VoiceOver Audio Graph Support (iOS 15+)

#### What is AXChartDescriptor?

`AXChartDescriptor` is Apple's framework for creating accessible charts. It provides:
- **Semantic description** of chart data that VoiceOver can understand
- **Audio representation** (sonification) of data trends
- **Interactive exploration** of individual data points

**Components:**
```swift
AXChartDescriptor(
    title: String,           // Chart title
    summary: String?,        // 1-2 sentence key insights (like alt text)
    xAxis: AXDataAxisDescriptor,   // X-axis descriptor
    yAxis: AXNumericDataAxisDescriptor,  // Y-axis descriptor (must be numeric)
    series: [AXDataSeriesDescriptor]     // Data series
)
```

#### How Audio Graphs Work

**Sonification:**
- VoiceOver plays tones representing data values
- **Higher pitch = higher value, lower pitch = lower value**
- Users can "listen" to trends in the data

**User Interaction via VoiceOver Rotor:**
1. **Describe Chart** - Reads title and summary
2. **Play Audio Graph** - Plays sonified data (pitch changes with values)
3. **Chart Details** - Opens interactive exploration mode
   - Users can swipe through individual data points
   - Double-tap and drag to scrub through data at their own pace
   - VoiceOver announces values as user navigates

**Example Use Case:**
A blind user could identify the baby boom era (peak birth rate around 1960) by listening for the highest pitch in a birth rate chart, then pausing to hear the exact value.

**Requirements:**
- **iOS 15+** minimum
- Conform to `AXChartDescriptorRepresentable` protocol (SwiftUI) or `AXChart` protocol (UIKit)
- **Does NOT work in iOS Simulator** - requires physical device for testing
- Swift Charts provides automatic Audio Graph support

**Sources:**
- [Kodeco: Create Accessible Charts using Audio Graphs](https://www.kodeco.com/31561694-ios-accessibility-in-swiftui-create-accessible-charts-using-audio-graphs)
- [Apple Developer: Representing chart data as an audio graph](https://developer.apple.com/documentation/accessibility/representing-chart-data-as-an-audio-graph)
- [Swift with Majid: Audio graphs in SwiftUI](https://swiftwithmajid.com/2021/09/29/audio-graphs-in-swiftui/)

### 3. Swift Charts Accessibility Features

#### Built-in Features

Swift Charts (iOS 16+) provides **automatic accessibility** for free:

**Automatic Features:**
- Builds accessibility tree from chart data automatically
- VoiceOver can navigate through data points
- **Audio Graphs support is automatic** - no manual `AXChartDescriptor` creation needed
- Accessibility labels generated from `PlottableValue` labels

**What You Need to Provide:**
- Meaningful labels in `.value()` calls for PlottableValue
- Optional: Custom accessibility labels/values using modifiers

**Example:**
```swift
Chart {
    ForEach(testHistory) { result in
        LineMark(
            x: .value("Date", result.completedAt),  // "Date" becomes axis label
            y: .value("IQ Score", result.iqScore)   // "IQ Score" becomes value label
        )
        .accessibilityLabel("Test on \(result.completedAt.formatted())")  // Optional custom label
        .accessibilityValue("\(result.iqScore) IQ points")  // Optional custom value
    }
}
```

**Chart Summary for Audio Graphs:**
Swift Charts automatically generates summaries and statistics for VoiceOver, but you can customize:

```swift
Chart { /* chart content */ }
    .accessibilityLabel("IQ Score Trend")  // Chart title
    .accessibilityValue("Showing \(count) test results from \(dateRange)")  // Chart summary
```

**Key Insight:** Since we're already using Swift Charts, we get Audio Graph support nearly for free - we just need to ensure our `.value()` labels are descriptive.

**Sources:**
- [Swift with Majid: Mastering charts in SwiftUI - Accessibility](https://swiftwithmajid.com/2023/02/28/mastering-charts-in-swiftui-accessibility/)
- [Create with Swift: Making charts accessible with Swift Charts](https://www.createwithswift.com/making-charts-accessible-with-swift-charts/)

### 4. Alternative Data Presentation

#### Data Table Alternative

**Best Practice:** WCAG recommends providing the underlying data in an accessible table format as an alternative to visual charts.

**Benefits:**
- Screen reader users can navigate tabular data easily
- Provides exact values without approximation
- Works on all devices and assistive technologies
- No iOS version requirements

**Implementation Options:**

**Option A: Collapsible Data Table Below Chart**
```swift
VStack {
    IQTrendChart(testHistory: testHistory)

    if showDataTable {
        DataTableView(testHistory: testHistory)
            .accessibilityLabel("IQ test results data table")
    }

    Button("Toggle Data Table") {
        showDataTable.toggle()
    }
}
```

**Option B: Sheet/Modal with Data Table**
```swift
IQTrendChart(testHistory: testHistory)
    .toolbar {
        Button("View Data Table") {
            showingDataTable = true
        }
        .accessibilityHint("Opens table with exact test result values")
    }
    .sheet(isPresented: $showingDataTable) {
        TestHistoryTableView(testHistory: testHistory)
    }
```

**Recommendation:** Option B (sheet) is cleaner for our UI and follows iOS patterns.

#### Audio Descriptions

**What We Already Have:**
Our current accessibility label provides a good audio description:
- "IQ score trend chart showing 4 test results"
- "Scores range from 105 to 125 with an average of 115"
- "Tests span from Dec 5 to Jan 4"
- "Shaded areas show 95% confidence intervals"

**Enhancement Opportunity:**
For Audio Graphs, we could provide more context in the summary:
- "Your IQ scores show an upward trend, increasing from 105 to 125 over the past month"
- "Your most recent score of 125 is your highest to date"

#### Confidence Interval Representation

**Challenge:** Confidence intervals are visually represented as shaded areas, which is difficult to convey to screen reader users.

**Current Approach:**
- Text description: "Shaded areas show 95% confidence intervals for measurement uncertainty"
- This explains WHAT they are but not the specific bounds

**Enhanced Approach for Audio Graphs:**
When users navigate to a specific data point, VoiceOver could announce:
- "December 15, 2025: IQ Score 112, confidence interval 105 to 119"
- This provides the exact range for each test

**Implementation:**
```swift
LineMark(...)
    .accessibilityLabel("Test on \(date)")
    .accessibilityValue(makeAccessibilityValue(for: result))

private func makeAccessibilityValue(for result: TestResult) -> String {
    var value = "\(result.iqScore) IQ points"
    if let ci = result.confidenceInterval {
        value += ", confidence interval \(Int(ci.lower)) to \(Int(ci.upper))"
    }
    return value
}
```

**Sources:**
- [Highcharts Accessibility Demos](https://www.highcharts.com/blog/accessibility/)
- [Accessible Graphics: Sonification](https://accessiblegraphics.org/formats/sonification/)

### 5. Competitor Approaches

#### Apple Health and Fitness Apps

**Implementation:**
- Use Swift Charts framework (or similar internal framework)
- Provide Audio Graph support for all time-series charts (heart rate, steps, etc.)
- Charts are accessible via VoiceOver rotor
- Users can navigate through individual data points
- Summary descriptions provide context ("Your heart rate averaged 72 BPM this week")

**Key Patterns:**
- **Trends are emphasized** in accessibility descriptions ("up 15% from last week")
- **Context is provided** (comparing to goals, averages, previous periods)
- **Units are always included** in VoiceOver announcements

#### Third-Party Apps

**Highcharts (Web-based, but relevant patterns):**
- Provides tooltips accessible to screen readers
- Offers data table export
- Supports keyboard navigation
- Implements sonification API

**Banking/Finance Apps:**
- Combine charts with tabular data
- Provide summary statistics prominently
- Use clear, descriptive axis labels
- Often include "insights" section with key takeaways

**Best Practice Synthesis:**
1. **Multi-modal access** - Provide both visual and non-visual ways to understand data
2. **Context over raw data** - Explain what the data means, not just the numbers
3. **Navigation flexibility** - Let users explore at different levels of detail (summary → individual points)

**Sources:**
- [Highcharts Sonification](https://www.highcharts.com/docs/accessibility/sonification)
- [Perkins School: Sonification Summary](https://www.perkins.org/resource/sonification-summary-page/)

---

## Recommended Implementation Approach

### Primary Recommendation: Audio Graphs with Enhanced Accessibility Labels

**Why This Approach:**
- Leverages Swift Charts' built-in Audio Graph support (we get most of it for free)
- Industry-leading accessibility for blind/low-vision users
- Minimal implementation effort since we already use Swift Charts
- Aligns with Apple's own Health/Fitness app patterns
- iOS 16+ requirement matches our minimum iOS version

**Implementation Steps:**

#### 1. Add Meaningful PlottableValue Labels
Ensure all `.value()` calls have descriptive labels:

```swift
LineMark(
    x: .value("Test Date", result.completedAt),
    y: .value("IQ Score", result.iqScore)
)
```

#### 2. Add Custom Accessibility Labels to Marks
Provide detailed context for each data point:

```swift
LineMark(...)
    .accessibilityLabel("Test on \(result.completedAt.toShortString())")
    .accessibilityValue(makeAccessibilityValue(for: result))

PointMark(...)
    .accessibilityLabel("Test on \(result.completedAt.toShortString())")
    .accessibilityValue(makeAccessibilityValue(for: result))
```

#### 3. Add Chart-Level Accessibility Context
Provide a summary that Audio Graphs will use:

```swift
Chart { /* content */ }
    .accessibilityLabel("IQ Score Trend Chart")
    .accessibilityValue(chartAccessibilitySummary)

private var chartAccessibilitySummary: String {
    guard !testHistory.isEmpty else {
        return "No test data available"
    }

    let scores = testHistory.map(\.iqScore)
    let trend = calculateTrend(scores)

    return """
    Showing \(testHistory.count) test results from \(dateRangeDescription).
    Your scores \(trend) from \(scores.first!) to \(scores.last!), with an average of \(avgScore).
    \(hasConfidenceIntervals ? "Confidence intervals show measurement uncertainty." : "")
    """
}

private func calculateTrend(_ scores: [Int]) -> String {
    guard let first = scores.first, let last = scores.last else {
        return "show no change"
    }

    if last > first {
        return "increased"
    } else if last < first {
        return "decreased"
    } else {
        return "remained stable"
    }
}
```

#### 4. Handle Confidence Intervals
Add CI bounds to individual data point announcements:

```swift
private func makeAccessibilityValue(for result: TestResult) -> String {
    var value = "\(result.iqScore) IQ points"

    if let ci = result.confidenceInterval {
        let lower = Int(ci.lower)
        let upper = Int(ci.upper)
        value += ". Confidence interval: \(lower) to \(upper)"
    }

    return value
}
```

#### 5. Test with VoiceOver
**CRITICAL:** Audio Graphs only work on physical devices, not simulators.

Testing checklist:
- [ ] Enable VoiceOver on iPhone
- [ ] Navigate to IQTrendChart
- [ ] Use rotor to find "Chart Details"
- [ ] Verify "Play Audio Graph" option appears
- [ ] Test sonification (pitch changes with IQ scores)
- [ ] Swipe through individual data points
- [ ] Verify confidence intervals are announced
- [ ] Test with 2, 5, and 20+ data points

**Effort Estimate:** LOW
- 2-4 hours implementation
- 1-2 hours testing on device
- Mostly additive changes to existing code

---

### Secondary Recommendation: Add Data Table Alternative

**Why This Approach:**
- Complements Audio Graphs (defense in depth)
- Meets WCAG 1.1.1 requirement for text alternatives
- Works on all iOS versions and assistive technologies
- Useful for all users, not just those with visual impairments

**Implementation:**

#### Option A: Sheet with Data Table
```swift
struct IQTrendChart: View {
    let testHistory: [TestResult]
    @State private var showingDataTable = false

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("IQ Score Trend")
                    .font(.headline)

                Spacer()

                Button {
                    showingDataTable = true
                } label: {
                    Image(systemName: "tablecells")
                }
                .accessibilityLabel("View data table")
                .accessibilityHint("Opens a table showing all test results with exact values")
            }

            // Existing chart code...
        }
        .sheet(isPresented: $showingDataTable) {
            TestHistoryTableView(testHistory: testHistory)
        }
    }
}
```

#### Create TestHistoryTableView Component
```swift
struct TestHistoryTableView: View {
    let testHistory: [TestResult]
    @Environment(\.dismiss) var dismiss

    var body: some View {
        NavigationView {
            List {
                ForEach(testHistory.sorted(by: { $0.completedAt > $1.completedAt })) { result in
                    VStack(alignment: .leading, spacing: 8) {
                        Text(result.completedAt.formatted(date: .abbreviated, time: .omitted))
                            .font(Typography.labelMedium)
                            .foregroundColor(ColorPalette.textSecondary)

                        HStack {
                            Text("IQ Score:")
                                .font(Typography.bodyMedium)
                            Text("\(result.iqScore)")
                                .font(Typography.bodyMedium)
                                .fontWeight(.semibold)
                        }

                        if let ci = result.confidenceInterval {
                            HStack {
                                Text("95% CI:")
                                    .font(Typography.bodySmall)
                                    .foregroundColor(ColorPalette.textSecondary)
                                Text("\(Int(ci.lower)) - \(Int(ci.upper))")
                                    .font(Typography.bodySmall)
                                    .foregroundColor(ColorPalette.textSecondary)
                            }
                        }
                    }
                    .accessibilityElement(children: .combine)
                    .accessibilityLabel(makeRowAccessibilityLabel(for: result))
                }
            }
            .navigationTitle("Test Results")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") {
                        dismiss()
                    }
                }
            }
        }
    }

    private func makeRowAccessibilityLabel(for result: TestResult) -> String {
        var label = "Test on \(result.completedAt.formatted(date: .abbreviated, time: .omitted)). IQ Score: \(result.iqScore)"

        if let ci = result.confidenceInterval {
            label += ". Confidence interval: \(Int(ci.lower)) to \(Int(ci.upper))"
        }

        return label
    }
}
```

**Effort Estimate:** LOW-MEDIUM
- 3-5 hours implementation
- 1-2 hours testing
- New component but straightforward List implementation

---

### Tertiary Recommendation: Enhanced Text Descriptions

**Why This Approach:**
- Quick win - minimal effort
- Improves current accessibility immediately
- Works as baseline even if Audio Graphs aren't available

**Implementation:**

Update `chartAccessibilityLabel` to include trend information:

```swift
private var chartAccessibilityLabel: String {
    guard !testHistory.isEmpty else {
        return "IQ score trend chart with no data"
    }

    let scores = testHistory.map(\.iqScore)
    let minScore = scores.min() ?? 0
    let maxScore = scores.max() ?? 0
    let avgScore = scores.reduce(0, +) / scores.count
    let trend = calculateTrend(scores)

    var label = "IQ score trend chart showing \(testHistory.count) test results. "
    label += "Your scores \(trend) from \(scores.first!) to \(scores.last!), "
    label += "with scores ranging from \(minScore) to \(maxScore) and an average of \(avgScore). "
    label += dateRangeDescription

    if hasConfidenceIntervals {
        label += "Shaded areas show 95% confidence intervals representing measurement uncertainty."
    }

    return label
}

private func calculateTrend(_ scores: [Int]) -> String {
    guard let first = scores.first, let last = scores.last else {
        return "show no change"
    }

    if last > first {
        return "increased"
    } else if last < first {
        return "decreased"
    } else {
        return "remained stable"
    }
}
```

**Effort Estimate:** VERY LOW
- 30 minutes implementation
- 15 minutes testing
- Single function modification

---

## Implementation Roadmap

### Phase 1: Quick Wins (Sprint 1)
**Goal:** Improve current accessibility with minimal effort

1. **Enhanced Text Descriptions** (30 min)
   - Add trend calculation
   - Update `chartAccessibilityLabel`
   - Test with VoiceOver

**Deliverable:** Improved baseline accessibility

### Phase 2: Audio Graphs (Sprint 2)
**Goal:** Implement industry-leading accessibility

1. **Add Custom Accessibility Labels** (2 hours)
   - Update LineMark and PointMark with `.accessibilityLabel()` and `.accessibilityValue()`
   - Create `makeAccessibilityValue()` helper for CI bounds
   - Add chart-level summary

2. **Test on Physical Device** (2 hours)
   - Test VoiceOver navigation
   - Verify Audio Graph playback
   - Test with various data set sizes

**Deliverable:** Full Audio Graph support

### Phase 3: Data Table Alternative (Sprint 3)
**Goal:** Provide alternative data access method

1. **Create TestHistoryTableView** (3 hours)
   - Build List-based table view
   - Add accessibility labels
   - Create sheet presentation

2. **Integrate with Chart** (1 hour)
   - Add button to IQTrendChart header
   - Wire up sheet presentation

3. **Test Accessibility** (1 hour)
   - VoiceOver navigation through table
   - Verify all data is readable

**Deliverable:** Accessible data table alternative

---

## Technical Considerations

### iOS Version Support

| Feature | Minimum iOS | Notes |
|---------|------------|-------|
| Swift Charts | iOS 16+ | Already our minimum version |
| Audio Graphs | iOS 15+ | Works with Swift Charts on iOS 16+ |
| AXChartDescriptor | iOS 15+ | Auto-generated by Swift Charts |
| Basic VoiceOver | iOS 3+ | Current text description works everywhere |

**Decision:** No compatibility concerns - all recommendations work with our iOS 16+ requirement.

### Performance Impact

**Audio Graphs:**
- Negligible - descriptors built on-demand when VoiceOver accesses chart
- No impact on users without VoiceOver enabled
- No rendering overhead

**Data Table:**
- Memory: Small - List is lazy-loaded
- Rendering: Fast - simple List with text elements
- Concern: Large data sets (100+ results) should paginate

**Recommendation:** Implement data table with pagination if `testHistory.count > 50`

### Testing Limitations

**Simulator:**
- VoiceOver works
- Text descriptions work
- **Audio Graphs DO NOT WORK** - requires physical device

**Physical Device Required For:**
- Audio Graph playback testing
- Sonification verification
- Rotor chart details testing

**Testing Strategy:**
- Unit test accessibility label generation
- Manual VoiceOver testing on device for Audio Graphs
- Include accessibility testing in QA checklist

---

## Code Examples / Pseudocode

### Complete Implementation: Audio Graphs Enhancement

```swift
// ios/AIQ/Views/History/IQTrendChart.swift

import Charts
import SwiftUI

/// Chart component displaying IQ score trends over time
struct IQTrendChart: View {
    let testHistory: [TestResult]

    // Maximum number of data points to render for performance
    private let maxDataPoints = 50

    /// Whether any results have confidence interval data
    private var hasConfidenceIntervals: Bool {
        ChartDomainCalculator.hasConfidenceIntervals(in: testHistory)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("IQ Score Trend")
                    .font(.headline)
                    .foregroundColor(.primary)

                Spacer()

                // Legend for confidence interval band (when applicable)
                if hasConfidenceIntervals {
                    HStack(spacing: 4) {
                        RoundedRectangle(cornerRadius: 2)
                            .fill(Color.accentColor.opacity(0.2))
                            .frame(width: 12, height: 8)
                        Text("95% CI")
                            .font(.caption2)
                            .foregroundColor(.secondary)
                    }
                    .accessibilityLabel("Shaded area shows 95% confidence interval")
                }
            }

            if testHistory.count >= 2 {
                Chart {
                    // Confidence interval area
                    ForEach(sampledDataWithCI) { result in
                        if let ci = result.confidenceInterval {
                            AreaMark(
                                x: .value("Test Date", result.completedAt),
                                yStart: .value("CI Lower", ci.lower),
                                yEnd: .value("CI Upper", ci.upper)
                            )
                            .foregroundStyle(Color.accentColor.opacity(0.15))
                            .interpolationMethod(.linear)
                            // Area marks are decorative - individual points have CI info
                            .accessibilityHidden(true)
                        }
                    }

                    // Main score line
                    ForEach(sampledData) { result in
                        LineMark(
                            x: .value("Test Date", result.completedAt),
                            y: .value("IQ Score", result.iqScore)
                        )
                        .foregroundStyle(Color.accentColor)
                        .lineStyle(StrokeStyle(lineWidth: 2))
                        .accessibilityLabel("Test on \(result.completedAt.toShortString())")
                        .accessibilityValue(makeAccessibilityValue(for: result))

                        PointMark(
                            x: .value("Test Date", result.completedAt),
                            y: .value("IQ Score", result.iqScore)
                        )
                        .foregroundStyle(Color.accentColor)
                        .symbolSize(60)
                        .accessibilityLabel("Test on \(result.completedAt.toShortString())")
                        .accessibilityValue(makeAccessibilityValue(for: result))
                    }

                    // Reference line at average IQ (100)
                    RuleMark(y: .value("Average IQ", 100))
                        .foregroundStyle(Color.secondary.opacity(0.3))
                        .lineStyle(StrokeStyle(lineWidth: 1, dash: [5, 5]))
                        .annotation(position: .top, alignment: .trailing) {
                            Text("Avg (100)")
                                .font(.caption2)
                                .foregroundColor(.secondary)
                        }
                        .accessibilityLabel("Reference line at average IQ of 100")
                }
                .chartYScale(domain: chartYDomain)
                .chartXAxis {
                    AxisMarks(values: .automatic(desiredCount: 3)) { _ in
                        AxisGridLine()
                        AxisValueLabel(format: .dateTime.month(.abbreviated).day())
                    }
                }
                .chartYAxis {
                    AxisMarks(position: .leading)
                }
                .frame(height: 200)
                .drawingGroup()
                // Chart-level accessibility for Audio Graphs
                .accessibilityLabel("IQ Score Trend Chart")
                .accessibilityValue(chartAccessibilitySummary)
            } else {
                VStack(spacing: 8) {
                    Image(systemName: "chart.xyaxis.line")
                        .font(.largeTitle)
                        .foregroundColor(.secondary)

                    Text("Not enough data")
                        .font(.subheadline)
                        .foregroundColor(.secondary)

                    Text("Complete at least 2 tests to see your trend")
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                }
                .frame(height: 200)
                .frame(maxWidth: .infinity)
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: Color.black.opacity(0.05), radius: 4, x: 0, y: 2)
    }

    // MARK: - Private Computed Properties

    /// Sampled data for rendering (improves performance with large datasets)
    private var sampledData: [TestResult] {
        ChartDomainCalculator.sampleData(from: testHistory, maxDataPoints: maxDataPoints)
    }

    /// Sampled data filtered to only results with confidence intervals
    private var sampledDataWithCI: [TestResult] {
        ChartDomainCalculator.filterResultsWithCI(from: sampledData)
    }

    /// Calculate appropriate Y-axis domain based on score range (including CI bounds)
    private var chartYDomain: ClosedRange<Int> {
        ChartDomainCalculator.calculateYDomain(for: testHistory)
    }

    // MARK: - Accessibility Helpers

    /// Chart summary for Audio Graphs - describes key insights
    private var chartAccessibilitySummary: String {
        guard !testHistory.isEmpty else {
            return "No test data available"
        }

        let scores = testHistory.map(\.iqScore)
        let minScore = scores.min() ?? 0
        let maxScore = scores.max() ?? 0
        let avgScore = scores.reduce(0, +) / scores.count
        let trend = calculateTrend(scores)

        var summary = "Showing \(testHistory.count) test results from \(dateRangeDescription). "
        summary += "Your scores \(trend) from \(scores.first!) to \(scores.last!), "
        summary += "with scores ranging from \(minScore) to \(maxScore) and an average of \(avgScore). "

        if hasConfidenceIntervals {
            summary += "Confidence intervals show measurement uncertainty for each test."
        }

        return summary
    }

    /// Creates accessibility value for individual data point including confidence interval
    private func makeAccessibilityValue(for result: TestResult) -> String {
        var value = "\(result.iqScore) IQ points"

        if let ci = result.confidenceInterval {
            let lower = Int(ci.lower)
            let upper = Int(ci.upper)
            value += ". Confidence interval: \(lower) to \(upper)"
        }

        return value
    }

    /// Calculate trend direction from score series
    private func calculateTrend(_ scores: [Int]) -> String {
        guard let first = scores.first, let last = scores.last else {
            return "show no change"
        }

        if last > first {
            return "increased"
        } else if last < first {
            return "decreased"
        } else {
            return "remained stable"
        }
    }

    /// Formatted date range description for accessibility
    private var dateRangeDescription: String {
        let sortedDates = testHistory.map(\.completedAt).sorted()
        guard let firstDate = sortedDates.first,
              let lastDate = sortedDates.last else {
            return ""
        }

        // If all tests are on the same day, just mention that date
        if Calendar.current.isDate(firstDate, inSameDayAs: lastDate) {
            return "Tests taken on \(firstDate.toShortString())"
        }

        return "\(firstDate.toShortString()) to \(lastDate.toShortString())"
    }
}

// Existing previews remain unchanged...
```

**Changes Summary:**
1. Added descriptive labels to all `.value()` calls ("Test Date", "IQ Score", "CI Lower", etc.)
2. Added `.accessibilityLabel()` and `.accessibilityValue()` to LineMark and PointMark
3. Created `makeAccessibilityValue()` helper to include confidence interval bounds
4. Replaced old `chartAccessibilityLabel` with new `chartAccessibilitySummary` that includes trend
5. Added `calculateTrend()` helper to describe score direction
6. Updated chart-level modifiers to use `.accessibilityValue()` for summary (Audio Graphs use this)
7. Added `.accessibilityHidden(true)` to AreaMark (CI info is on individual points)
8. Added accessibility label to RuleMark reference line

---

## Final Recommendation

**Implement all three phases sequentially:**

### Phase 1: Enhanced Text Descriptions (Immediate - 30 min)
- Quick win that improves accessibility today
- No dependencies, minimal risk
- Sets foundation for Audio Graphs

### Phase 2: Audio Graphs (Next Sprint - 4 hours)
- Industry-leading accessibility
- Leverages Swift Charts' automatic support
- Aligns with Apple's own apps
- **Highest impact for blind/low-vision users**

### Phase 3: Data Table Alternative (Following Sprint - 4 hours)
- Meets WCAG compliance
- Useful for all users (including sighted users who want exact values)
- Provides redundancy if Audio Graphs have issues

**Total Effort:** 8-9 hours across 3 sprints

**Complexity:** LOW-MEDIUM
- Phase 1: Very Low
- Phase 2: Low (mostly leveraging built-in features)
- Phase 3: Medium (new component)

**Risk:** LOW
- Changes are additive (no breaking changes)
- Swift Charts handles Audio Graph complexity
- Well-documented APIs with Apple resources

**Impact:** HIGH
- Makes chart accessible to blind/low-vision users
- Demonstrates commitment to accessibility
- Future-proofs as accessibility standards evolve

---

## Testing Checklist

### VoiceOver Testing (Physical Device Required)

- [ ] **Chart Summary**
  - [ ] Navigate to IQTrendChart with VoiceOver
  - [ ] Verify chart summary is read with trend information
  - [ ] Confirm count, range, and average are announced

- [ ] **Audio Graph Access**
  - [ ] Use rotor to find "Chart Details"
  - [ ] Verify "Play Audio Graph" option appears
  - [ ] Test audio playback (pitch corresponds to IQ values)
  - [ ] Confirm higher scores = higher pitch

- [ ] **Individual Data Point Navigation**
  - [ ] Swipe through data points in Audio Graph detail view
  - [ ] Verify each point announces date and score
  - [ ] Confirm confidence intervals are announced when present
  - [ ] Test scrubbing (double-tap and drag)

- [ ] **Edge Cases**
  - [ ] Test with 2 data points (minimum)
  - [ ] Test with 10+ data points
  - [ ] Test with no confidence intervals
  - [ ] Test with all results having confidence intervals
  - [ ] Test with mixed (some have CI, some don't)

### Dynamic Type Testing

- [ ] Test chart at Medium (default) text size
- [ ] Test at Extra Large (XL)
- [ ] Test at Accessibility XXXL (AX5)
- [ ] Verify all text elements scale appropriately
- [ ] Confirm chart remains usable at largest sizes

### Color Contrast Testing

- [ ] Verify chart elements meet 3:1 contrast ratio
- [ ] Test in light mode
- [ ] Test in dark mode
- [ ] Confirm confidence interval shading is distinguishable

### Data Table Testing (Phase 3)

- [ ] Open data table sheet
- [ ] Navigate through table with VoiceOver
- [ ] Verify all values are announced
- [ ] Test with large data sets (20+ results)
- [ ] Confirm dismiss button is accessible

---

## References

### Apple Documentation
- [Representing chart data as an audio graph](https://developer.apple.com/documentation/accessibility/representing-chart-data-as-an-audio-graph)
- [AXChartDescriptor](https://developer.apple.com/documentation/accessibility/axchartdescriptor)
- [WWDC21: Bring accessibility to charts in your app](https://developer.apple.com/videos/play/wwdc2021/10122/)
- [WWDC22: Design an effective chart](https://developer.apple.com/videos/play/wwdc2022/110340/)
- [Swift Charts Documentation](https://developer.apple.com/documentation/charts)
- [Accessibility Guidelines](https://developer.apple.com/design/human-interface-guidelines/accessibility)

### Community Resources
- [Swift with Majid: Mastering charts in SwiftUI - Accessibility](https://swiftwithmajid.com/2023/02/28/mastering-charts-in-swiftui-accessibility/)
- [Swift with Majid: Audio graphs in SwiftUI](https://swiftwithmajid.com/2021/09/29/audio-graphs-in-swiftui/)
- [Kodeco: Create Accessible Charts using Audio Graphs](https://www.kodeco.com/31561694-ios-accessibility-in-swiftui-create-accessible-charts-using-audio-graphs)
- [Create with Swift: Making charts accessible with Swift Charts](https://www.createwithswift.com/making-charts-accessible-with-swift-charts/)
- [iOS Accessibility Guidelines: Best Practices for 2025](https://medium.com/@david-auerbach/ios-accessibility-guidelines-best-practices-for-2025-6ed0d256200e)

### Accessibility Standards
- [Accessible Graphics: Sonification](https://accessiblegraphics.org/formats/sonification/)
- [Perkins School: Sonification Summary](https://www.perkins.org/resource/sonification-summary-page/)
- [Highcharts Accessibility Demos](https://www.highcharts.com/blog/accessibility/)
- [Highcharts Sonification](https://www.highcharts.com/docs/accessibility/sonification)

### Tools and Libraries
- [Airo Global: Beginning with Audio Graphs in Swift and iOS 15](https://airoglobal.com/blog/post/beginning-with-audio-graphs-in-swift-and-ios-15)

---

## Appendix: WCAG Compliance Matrix

| WCAG Criterion | Level | Current Status | After Phase 1 | After Phase 2 | After Phase 3 |
|----------------|-------|----------------|---------------|---------------|---------------|
| 1.1.1 Non-text Content | A | Partial | Pass | Pass | Pass |
| 1.4.3 Contrast (Minimum) | AA | Pass | Pass | Pass | Pass |
| 1.4.11 Non-text Contrast | AA | Pass | Pass | Pass | Pass |
| 2.1.1 Keyboard | A | N/A | N/A | Pass | Pass |
| 2.4.4 Link Purpose | A | Pass | Pass | Pass | Pass |
| 4.1.2 Name, Role, Value | A | Partial | Pass | Pass | Pass |

**Legend:**
- **Pass**: Fully compliant
- **Partial**: Basic implementation, room for improvement
- **N/A**: Not applicable to current implementation

---

## Appendix: Glossary

**Audio Graphs**: iOS accessibility feature that sonifies chart data, playing pitches that correspond to data values.

**AXChartDescriptor**: Apple's descriptor type for creating accessible charts, containing title, summary, axes, and data series information.

**Sonification**: The use of non-speech audio to convey information or represent data.

**VoiceOver Rotor**: A gesture-based navigation tool in VoiceOver that allows users to quickly jump between different types of content.

**Confidence Interval (CI)**: A range of values that likely contains the true value being measured; in our case, the range where a user's true IQ score likely falls.

**Swift Charts**: Apple's declarative framework for creating charts in iOS 16+, with built-in accessibility support.

**PlottableValue**: Swift Charts type representing a data point with a label and value.

---

## Next Steps

1. **Review this document** with product/design team
2. **Prioritize phases** based on upcoming sprint capacity
3. **Create implementation tickets** for each phase
4. **Acquire physical device** for Audio Graph testing (if not already available)
5. **Schedule accessibility review** with QA after Phase 2 implementation

---

**End of Spike Investigation**
