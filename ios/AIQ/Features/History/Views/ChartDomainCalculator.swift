import AIQAPIClient
import Foundation

/// Utility struct for calculating chart domain and filtering chart data.
/// Extracted from IQTrendChart for testability.
enum ChartDomainCalculator {
    // MARK: - Constants

    /// Minimum Y-axis value for the chart
    private static let minYAxis = 70

    /// Maximum Y-axis value for the chart
    private static let maxYAxis = 160

    /// Padding to add above/below the data range for readability
    private static let axisPadding = 10

    /// Default range when no data is available
    private static let defaultRange = 70 ... 130

    // MARK: - Y Domain Calculation

    /// Calculates the appropriate Y-axis domain for a chart based on test scores and CI bounds.
    ///
    /// The domain:
    /// - Includes all IQ scores from the history
    /// - Includes all confidence interval bounds when present
    /// - Adds padding for readability
    /// - Clamps to 70-160 range (valid IQ display range)
    ///
    /// - Parameter history: Array of test results to calculate domain for
    /// - Returns: A closed range representing the Y-axis domain
    static func calculateYDomain(for history: [TestResult]) -> ClosedRange<Int> {
        guard !history.isEmpty else { return defaultRange }

        // Collect all scores and CI bounds in a single pass for better performance
        var allValues: [Int] = []
        allValues.reserveCapacity(history.count * 3) // Pre-allocate for score + CI bounds

        for result in history {
            allValues.append(result.iqScore)
            if let ciPayload = result.confidenceInterval {
                allValues.append(ciPayload.value1.lower)
                allValues.append(ciPayload.value1.upper)
            }
        }

        let minValue = allValues.min() ?? 100
        let maxValue = allValues.max() ?? 100

        // Add padding to make the chart more readable
        let lowerBound = max(minYAxis, minValue - axisPadding)
        let upperBound = min(maxYAxis, maxValue + axisPadding)

        return lowerBound ... upperBound
    }

    // MARK: - Confidence Interval Detection

    /// Checks if any results in the history have confidence interval data.
    ///
    /// - Parameter history: Array of test results to check
    /// - Returns: True if at least one result has a confidence interval
    static func hasConfidenceIntervals(in history: [TestResult]) -> Bool {
        history.contains { $0.confidenceInterval != nil }
    }

    // MARK: - Data Filtering

    /// Filters test results to only those with confidence intervals.
    ///
    /// Used for rendering CI area marks on the chart.
    ///
    /// - Parameter history: Array of test results to filter
    /// - Returns: Array containing only results with confidence intervals
    static func filterResultsWithCI(from history: [TestResult]) -> [TestResult] {
        history.filter { $0.confidenceInterval != nil }
    }

    // MARK: - Data Sampling

    /// Samples data for chart rendering to improve performance with large datasets.
    ///
    /// For datasets larger than maxDataPoints, this function evenly samples
    /// the data while ensuring the first and last results are always included.
    ///
    /// - Parameters:
    ///   - history: Array of test results to sample
    ///   - maxDataPoints: Maximum number of data points to return (default: 50)
    /// - Returns: Sampled array of test results, sorted by date
    static func sampleData(from history: [TestResult], maxDataPoints: Int = 50) -> [TestResult] {
        guard history.count > maxDataPoints else {
            return history
        }

        // Always include first and last test
        var sampled: [TestResult] = []
        let sortedHistory = history.sorted { $0.completedAt < $1.completedAt }

        // Calculate sampling interval
        let interval = Double(sortedHistory.count) / Double(maxDataPoints)

        for sampleIndex in 0 ..< maxDataPoints {
            let index = min(Int(Double(sampleIndex) * interval), sortedHistory.count - 1)
            sampled.append(sortedHistory[index])
        }

        // Ensure we include the last test if not already included
        if let last = sortedHistory.last, sampled.last?.id != last.id {
            sampled.append(last)
        }

        return sampled
    }
}
