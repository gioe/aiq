import Foundation

/// Represents the What's New content bundled with the app.
///
/// This model is decoded from `WhatsNew.json`, which is written by Fastlane at build time
/// and committed as a seed file for the initial release. It contains the app version string
/// and a list of categorized change entries.
struct WhatsNew: Codable {
    /// The app version string, e.g. "1.0.0 (42)"
    let version: String
    /// ISO 8601 timestamp of when the file was generated
    let generatedAt: String?
    /// Ordered list of change categories
    let categories: [Category]

    /// A named grouping of release notes items
    struct Category: Codable, Identifiable {
        /// The category name, e.g. "New Features"
        let name: String
        /// The individual items in this category
        let items: [String]
        /// Stable identity derived from the category name
        var id: String {
            name
        }
    }

    enum CodingKeys: String, CodingKey {
        case version
        case generatedAt = "generated_at"
        case categories
    }

    /// Loads and decodes `WhatsNew.json` from the main bundle.
    ///
    /// Returns `nil` if the file is missing or cannot be decoded. This is expected
    /// in development builds before Fastlane has run.
    static func loadFromBundle() -> WhatsNew? {
        guard let url = Bundle.main.url(forResource: "WhatsNew", withExtension: "json"),
              let data = try? Data(contentsOf: url) else {
            return nil
        }
        return try? JSONDecoder().decode(WhatsNew.self, from: data)
    }
}
