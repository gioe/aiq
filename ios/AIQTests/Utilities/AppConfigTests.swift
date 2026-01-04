import XCTest

@testable import AIQ

/// Tests for AppConfig constants and URLs
@MainActor
final class AppConfigTests: XCTestCase {
    // MARK: - Privacy Policy URL Tests

    func testPrivacyPolicyURLIsValid() {
        // Validate URL is correctly formed
        let url = AppConfig.privacyPolicyURL
        XCTAssertNotNil(url.scheme, "Privacy policy URL should have a scheme")
        XCTAssertEqual(url.scheme, "https", "Privacy policy URL should use HTTPS")
        XCTAssertNotNil(url.host, "Privacy policy URL should have a host")
    }

    func testPrivacyPolicyURLHasCorrectHost() {
        let url = AppConfig.privacyPolicyURL
        XCTAssertEqual(url.host, "aiq.app", "Privacy policy URL should point to aiq.app")
    }

    func testPrivacyPolicyURLHasCorrectPath() {
        let url = AppConfig.privacyPolicyURL
        XCTAssertEqual(url.path, "/privacy-policy", "Privacy policy URL should have correct path")
    }

    // MARK: - API URL Tests

    func testAPIBaseURLIsValid() {
        let urlString = AppConfig.apiBaseURL
        XCTAssertNotNil(URL(string: urlString), "API base URL should be a valid URL")
    }

    func testProductionDomainIsNotEmpty() {
        XCTAssertFalse(AppConfig.productionDomain.isEmpty, "Production domain should not be empty")
    }

    // MARK: - Version Tests

    func testAppVersionFormat() {
        let version = AppConfig.appVersion
        // Version should match semver format (X.Y.Z)
        let regex = try? NSRegularExpression(pattern: #"^\d+\.\d+\.\d+$"#)
        let range = NSRange(version.startIndex..., in: version)
        XCTAssertNotNil(regex?.firstMatch(in: version, range: range), "App version should be semver format")
    }

    func testBuildNumberIsNumeric() {
        let buildNumber = AppConfig.buildNumber
        XCTAssertNotNil(Int(buildNumber), "Build number should be numeric")
    }
}
