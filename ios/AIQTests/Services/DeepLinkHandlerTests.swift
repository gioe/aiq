import XCTest

@testable import AIQ

/// Tests for DeepLinkHandler URL parsing functionality
final class DeepLinkHandlerTests: XCTestCase {
    var sut: DeepLinkHandler!

    override func setUp() {
        super.setUp()
        sut = DeepLinkHandler()
    }

    override func tearDown() {
        sut = nil
        super.tearDown()
    }

    // MARK: - URL Scheme Tests - Test Results

    func testParseURLScheme_TestResults_ValidID() {
        // Given
        let url = URL(string: "aiq://test/results/123")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .testResults(id: 123), "should parse test results with valid ID")
    }

    func testParseURLScheme_TestResults_LargeID() {
        // Given
        let url = URL(string: "aiq://test/results/999999")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .testResults(id: 999_999), "should handle large IDs")
    }

    func testParseURLScheme_TestResults_InvalidID_NonNumeric() {
        // Given
        let url = URL(string: "aiq://test/results/abc")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .invalid, "should return invalid for non-numeric ID")
    }

    func testParseURLScheme_TestResults_MissingID() {
        // Given
        let url = URL(string: "aiq://test/results")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .invalid, "should return invalid when ID is missing")
    }

    func testParseURLScheme_TestResults_ExtraPathComponents() {
        // Given
        let url = URL(string: "aiq://test/results/123/extra")!

        // When
        let result = sut.parse(url)

        // Then
        // Note: Current implementation allows extra path components
        // This test documents the current behavior
        XCTAssertEqual(result, .testResults(id: 123), "should parse ID even with extra components")
    }

    // MARK: - URL Scheme Tests - Resume Test

    func testParseURLScheme_ResumeTest_ValidSessionID() {
        // Given
        let url = URL(string: "aiq://test/resume/456")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .resumeTest(sessionId: 456), "should parse resume test with valid session ID")
    }

    func testParseURLScheme_ResumeTest_LargeSessionID() {
        // Given
        let url = URL(string: "aiq://test/resume/888888")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .resumeTest(sessionId: 888_888), "should handle large session IDs")
    }

    func testParseURLScheme_ResumeTest_InvalidSessionID_NonNumeric() {
        // Given
        let url = URL(string: "aiq://test/resume/xyz")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .invalid, "should return invalid for non-numeric session ID")
    }

    func testParseURLScheme_ResumeTest_MissingSessionID() {
        // Given
        let url = URL(string: "aiq://test/resume")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .invalid, "should return invalid when session ID is missing")
    }

    // MARK: - URL Scheme Tests - Settings

    func testParseURLScheme_Settings_Valid() {
        // Given
        let url = URL(string: "aiq://settings")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .settings, "should parse settings route")
    }

    func testParseURLScheme_Settings_WithTrailingSlash() {
        // Given
        let url = URL(string: "aiq://settings/")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .settings, "should parse settings with trailing slash")
    }

    func testParseURLScheme_Settings_WithExtraPath() {
        // Given
        let url = URL(string: "aiq://settings/notifications")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .invalid, "should return invalid for settings with extra path")
    }

    // MARK: - URL Scheme Tests - Invalid Routes

    func testParseURLScheme_EmptyPath() {
        // Given
        let url = URL(string: "aiq://")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .invalid, "should return invalid for empty path")
    }

    func testParseURLScheme_UnrecognizedHost() {
        // Given
        let url = URL(string: "aiq://unknown/path")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .invalid, "should return invalid for unrecognized host")
    }

    func testParseURLScheme_TestWithoutAction() {
        // Given
        let url = URL(string: "aiq://test")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .invalid, "should return invalid for test without action")
    }

    func testParseURLScheme_TestWithInvalidAction() {
        // Given
        let url = URL(string: "aiq://test/invalid/123")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .invalid, "should return invalid for unrecognized test action")
    }

    // MARK: - Universal Link Tests - Test Results

    func testParseUniversalLink_TestResults_ValidID() {
        // Given
        let url = URL(string: "https://aiq.app/test/results/789")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .testResults(id: 789), "should parse universal link test results with valid ID")
    }

    func testParseUniversalLink_TestResults_LargeID() {
        // Given
        let url = URL(string: "https://aiq.app/test/results/111111")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .testResults(id: 111_111), "should handle large IDs in universal links")
    }

    func testParseUniversalLink_TestResults_InvalidID_NonNumeric() {
        // Given
        let url = URL(string: "https://aiq.app/test/results/def")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .invalid, "should return invalid for non-numeric ID in universal link")
    }

    func testParseUniversalLink_TestResults_MissingID() {
        // Given
        let url = URL(string: "https://aiq.app/test/results")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .invalid, "should return invalid when ID is missing in universal link")
    }

    // MARK: - Universal Link Tests - Resume Test

    func testParseUniversalLink_ResumeTest_ValidSessionID() {
        // Given
        let url = URL(string: "https://aiq.app/test/resume/321")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .resumeTest(sessionId: 321), "should parse universal link resume test with valid session ID")
    }

    func testParseUniversalLink_ResumeTest_LargeSessionID() {
        // Given
        let url = URL(string: "https://aiq.app/test/resume/777777")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .resumeTest(sessionId: 777_777), "should handle large session IDs in universal links")
    }

    func testParseUniversalLink_ResumeTest_InvalidSessionID_NonNumeric() {
        // Given
        let url = URL(string: "https://aiq.app/test/resume/invalid")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .invalid, "should return invalid for non-numeric session ID in universal link")
    }

    func testParseUniversalLink_ResumeTest_MissingSessionID() {
        // Given
        let url = URL(string: "https://aiq.app/test/resume")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .invalid, "should return invalid when session ID is missing in universal link")
    }

    // MARK: - Universal Link Tests - Settings

    func testParseUniversalLink_Settings_Valid() {
        // Given
        let url = URL(string: "https://aiq.app/settings")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .settings, "should parse settings from universal link")
    }

    func testParseUniversalLink_Settings_WithTrailingSlash() {
        // Given
        let url = URL(string: "https://aiq.app/settings/")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .settings, "should parse settings with trailing slash in universal link")
    }

    func testParseUniversalLink_Settings_WithExtraPath() {
        // Given
        let url = URL(string: "https://aiq.app/settings/extra")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .invalid, "should return invalid for settings with extra path in universal link")
    }

    // MARK: - Universal Link Tests - Invalid Routes

    func testParseUniversalLink_EmptyPath() {
        // Given
        let url = URL(string: "https://aiq.app/")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .invalid, "should return invalid for empty path in universal link")
    }

    func testParseUniversalLink_RootPath() {
        // Given
        let url = URL(string: "https://aiq.app")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .invalid, "should return invalid for root path in universal link")
    }

    func testParseUniversalLink_UnrecognizedPath() {
        // Given
        let url = URL(string: "https://aiq.app/unknown")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .invalid, "should return invalid for unrecognized path in universal link")
    }

    func testParseUniversalLink_TestWithoutAction() {
        // Given
        let url = URL(string: "https://aiq.app/test")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .invalid, "should return invalid for test without action in universal link")
    }

    func testParseUniversalLink_TestWithInvalidAction() {
        // Given
        let url = URL(string: "https://aiq.app/test/unknown/123")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .invalid, "should return invalid for unrecognized test action in universal link")
    }

    // MARK: - Development Domain Universal Link Tests

    func testParseUniversalLink_DevDomain_TestResults_ValidID() {
        // Given
        let url = URL(string: "https://dev.aiq.app/test/results/123")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .testResults(id: 123), "should parse test results from dev domain")
    }

    func testParseUniversalLink_DevDomain_ResumeTest_ValidSessionID() {
        // Given
        let url = URL(string: "https://dev.aiq.app/test/resume/456")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .resumeTest(sessionId: 456), "should parse resume test from dev domain")
    }

    func testParseUniversalLink_DevDomain_Settings() {
        // Given
        let url = URL(string: "https://dev.aiq.app/settings")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .settings, "should parse settings from dev domain")
    }

    func testParseUniversalLink_DevDomain_InvalidRoute() {
        // Given
        let url = URL(string: "https://dev.aiq.app/unknown")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .invalid, "should return invalid for unrecognized route on dev domain")
    }

    func testParseUniversalLink_DevDomain_EmptyPath() {
        // Given
        let url = URL(string: "https://dev.aiq.app/")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .invalid, "should return invalid for empty path on dev domain")
    }

    func testParseUniversalLink_DevDomain_TestResults_InvalidID() {
        // Given
        let url = URL(string: "https://dev.aiq.app/test/results/abc")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .invalid, "should return invalid for non-numeric ID on dev domain")
    }

    func testParseUniversalLink_DevDomain_EquivalentToProd() {
        // Given - same path on prod and dev domains
        let prodURL = URL(string: "https://aiq.app/test/results/789")!
        let devURL = URL(string: "https://dev.aiq.app/test/results/789")!

        // When
        let prodResult = sut.parse(prodURL)
        let devResult = sut.parse(devURL)

        // Then
        XCTAssertEqual(prodResult, devResult, "dev and prod domains should produce equivalent results")
        XCTAssertEqual(devResult, .testResults(id: 789))
    }

    // MARK: - Invalid URL Tests

    func testParse_InvalidScheme_HTTP() {
        // Given
        let url = URL(string: "http://aiq.app/test/results/123")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .invalid, "should return invalid for http scheme")
    }

    func testParse_InvalidScheme_Custom() {
        // Given
        let url = URL(string: "custom://test/results/123")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .invalid, "should return invalid for custom scheme")
    }

    func testParse_InvalidHost_UniversalLink() {
        // Given
        let url = URL(string: "https://other.app/test/results/123")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .invalid, "should return invalid for wrong host in universal link")
    }

    func testParse_InvalidHost_WWW() {
        // Given
        let url = URL(string: "https://www.aiq.app/test/results/123")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .invalid, "should return invalid for www subdomain")
    }

    // MARK: - Edge Case Tests

    func testParse_URLWithQueryParameters_URLScheme() {
        // Given
        let url = URL(string: "aiq://test/results/123?source=notification")!

        // When
        let result = sut.parse(url)

        // Then
        // Query parameters should be ignored
        XCTAssertEqual(result, .testResults(id: 123), "should parse URL ignoring query parameters")
    }

    func testParse_URLWithQueryParameters_UniversalLink() {
        // Given
        let url = URL(string: "https://aiq.app/test/results/456?utm_source=email")!

        // When
        let result = sut.parse(url)

        // Then
        // Query parameters should be ignored
        XCTAssertEqual(result, .testResults(id: 456), "should parse universal link ignoring query parameters")
    }

    func testParse_URLWithFragment_URLScheme() {
        // Given
        let url = URL(string: "aiq://test/results/789#section")!

        // When
        let result = sut.parse(url)

        // Then
        // Fragments should be ignored
        XCTAssertEqual(result, .testResults(id: 789), "should parse URL ignoring fragments")
    }

    func testParse_URLWithFragment_UniversalLink() {
        // Given
        let url = URL(string: "https://aiq.app/settings#notifications")!

        // When
        let result = sut.parse(url)

        // Then
        // Fragments should be ignored
        XCTAssertEqual(result, .settings, "should parse universal link ignoring fragments")
    }

    func testParse_URLWithLeadingZeros_URLScheme() {
        // Given
        let url = URL(string: "aiq://test/results/00123")!

        // When
        let result = sut.parse(url)

        // Then
        // Leading zeros should be handled by Int parsing
        XCTAssertEqual(result, .testResults(id: 123), "should handle IDs with leading zeros")
    }

    func testParse_URLWithNegativeID_URLScheme() {
        // Given
        let url = URL(string: "aiq://test/results/-123")!

        // When
        let result = sut.parse(url)

        // Then
        // Negative IDs are invalid - database IDs must be positive
        XCTAssertEqual(result, .invalid, "should reject negative IDs")
    }

    func testParse_URLWithZeroID_URLScheme() {
        // Given
        let url = URL(string: "aiq://test/results/0")!

        // When
        let result = sut.parse(url)

        // Then
        // Zero is invalid - database IDs must be positive
        XCTAssertEqual(result, .invalid, "should reject zero as ID")
    }

    func testParse_URLWithNegativeSessionID_URLScheme() {
        // Given
        let url = URL(string: "aiq://test/resume/-456")!

        // When
        let result = sut.parse(url)

        // Then
        // Negative session IDs are invalid
        XCTAssertEqual(result, .invalid, "should reject negative session IDs")
    }

    func testParse_URLWithZeroSessionID_URLScheme() {
        // Given
        let url = URL(string: "aiq://test/resume/0")!

        // When
        let result = sut.parse(url)

        // Then
        // Zero is invalid - database IDs must be positive
        XCTAssertEqual(result, .invalid, "should reject zero as session ID")
    }

    // MARK: - Integer Overflow Edge Case Tests

    func testParse_URLWithIntegerOverflow_URLScheme() {
        // Given - value exceeding Int.max
        let url = URL(string: "aiq://test/results/99999999999999999999999999999")!

        // When
        let result = sut.parse(url)

        // Then
        // Integer overflow should return invalid (Int parsing fails)
        XCTAssertEqual(result, .invalid, "should reject integer overflow values")
    }

    func testParse_URLWithIntegerOverflow_UniversalLink() {
        // Given - value exceeding Int.max
        let url = URL(string: "https://aiq.app/test/resume/99999999999999999999999999999")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .invalid, "should reject integer overflow values in universal links")
    }

    // MARK: - Decimal Value Edge Case Tests

    func testParse_URLWithDecimalID_URLScheme() {
        // Given
        let url = URL(string: "aiq://test/results/123.456")!

        // When
        let result = sut.parse(url)

        // Then
        // Decimal values should return invalid (Int parsing fails)
        XCTAssertEqual(result, .invalid, "should reject decimal IDs")
    }

    func testParse_URLWithDecimalSessionID_URLScheme() {
        // Given
        let url = URL(string: "aiq://test/resume/456.789")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .invalid, "should reject decimal session IDs")
    }

    func testParse_URLWithDecimalID_UniversalLink() {
        // Given
        let url = URL(string: "https://aiq.app/test/results/123.456")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .invalid, "should reject decimal IDs in universal links")
    }

    // MARK: - URL Encoding Edge Case Tests

    func testParse_URLWithEncodedSpaces_URLScheme() {
        // Given - ID with URL-encoded spaces
        let url = URL(string: "aiq://test/results/123%20456")!

        // When
        let result = sut.parse(url)

        // Then
        // URL-encoded spaces should fail Int parsing
        XCTAssertEqual(result, .invalid, "should reject IDs with encoded spaces")
    }

    func testParse_URLWithEncodedSlash_URLScheme() {
        // Given - ID with URL-encoded slash (%2F = /)
        // Note: URL.pathComponents behavior changed in iOS 18.4+
        // - iOS 18.3 and earlier: %2F becomes a path separator after decoding
        //   → pathComponents = ["results", "123", "456"] → testResults(id: 123)
        // - iOS 18.4+: %2F decodes within the component, preserving boundaries
        //   → pathComponents = ["results", "123/456"] → Int fails → .invalid
        let url = URL(string: "aiq://test/results/123%2F456")!

        // When
        let result = sut.parse(url)

        // Then - behavior depends on iOS version
        let osVersion = ProcessInfo.processInfo.operatingSystemVersion
        if osVersion.majorVersion > 18 || (osVersion.majorVersion == 18 && osVersion.minorVersion >= 4) {
            // iOS 18.4+: encoded slash decodes within component
            XCTAssertEqual(result, .invalid, "encoded slash decodes within component, not as path separator")
        } else {
            // iOS 18.3 and earlier: encoded slash becomes path separator
            XCTAssertEqual(result, .testResults(id: 123), "encoded slash becomes path separator on iOS < 18.4")
        }
    }

    func testParse_URLWithEncodedPath_UniversalLink() {
        // Given - path with URL-encoded characters
        let url = URL(string: "https://aiq.app/test/results/123%00456")!

        // When
        let result = sut.parse(url)

        // Then
        // URL with null byte should be handled gracefully
        XCTAssertEqual(result, .invalid, "should reject IDs with encoded null bytes")
    }

    func testParse_URLWithPlusSign_URLScheme() {
        // Given - ID with plus sign (sometimes used as space encoding)
        let url = URL(string: "aiq://test/results/123+456")!

        // When
        let result = sut.parse(url)

        // Then
        XCTAssertEqual(result, .invalid, "should reject IDs with plus signs")
    }

    // MARK: - DeepLink Equality Tests

    func testDeepLink_Equality_TestResults_SameID() {
        // Given
        let link1 = DeepLink.testResults(id: 100)
        let link2 = DeepLink.testResults(id: 100)

        // Then
        XCTAssertEqual(link1, link2, "test results with same ID should be equal")
    }

    func testDeepLink_Equality_TestResults_DifferentID() {
        // Given
        let link1 = DeepLink.testResults(id: 100)
        let link2 = DeepLink.testResults(id: 200)

        // Then
        XCTAssertNotEqual(link1, link2, "test results with different IDs should not be equal")
    }

    func testDeepLink_Equality_ResumeTest_SameSessionID() {
        // Given
        let link1 = DeepLink.resumeTest(sessionId: 50)
        let link2 = DeepLink.resumeTest(sessionId: 50)

        // Then
        XCTAssertEqual(link1, link2, "resume test with same session ID should be equal")
    }

    func testDeepLink_Equality_ResumeTest_DifferentSessionID() {
        // Given
        let link1 = DeepLink.resumeTest(sessionId: 50)
        let link2 = DeepLink.resumeTest(sessionId: 75)

        // Then
        XCTAssertNotEqual(link1, link2, "resume test with different session IDs should not be equal")
    }

    func testDeepLink_Equality_Settings() {
        // Given
        let link1 = DeepLink.settings
        let link2 = DeepLink.settings

        // Then
        XCTAssertEqual(link1, link2, "settings links should be equal")
    }

    func testDeepLink_Equality_Invalid() {
        // Given
        let link1 = DeepLink.invalid
        let link2 = DeepLink.invalid

        // Then
        XCTAssertEqual(link1, link2, "invalid links should be equal")
    }

    func testDeepLink_Equality_DifferentTypes() {
        // Given
        let link1 = DeepLink.testResults(id: 100)
        let link2 = DeepLink.settings
        let link3 = DeepLink.invalid

        // Then
        XCTAssertNotEqual(link1, link2, "different link types should not be equal")
        XCTAssertNotEqual(link1, link3, "different link types should not be equal")
        XCTAssertNotEqual(link2, link3, "different link types should not be equal")
    }

    // MARK: - Case Sensitivity Tests

    func testParse_CaseSensitive_Host_URLScheme() {
        // Given - URL schemes are case-insensitive for the scheme, but host is treated as path
        let urlLower = URL(string: "aiq://test/results/123")!
        let urlUpper = URL(string: "aiq://TEST/results/123")!

        // When
        let resultLower = sut.parse(urlLower)
        let resultUpper = sut.parse(urlUpper)

        // Then
        XCTAssertEqual(resultLower, .testResults(id: 123), "lowercase should work")
        XCTAssertEqual(resultUpper, .invalid, "uppercase host should be invalid")
    }

    func testParse_CaseSensitive_Path_URLScheme() {
        // Given
        let urlLower = URL(string: "aiq://test/results/123")!
        let urlMixed = URL(string: "aiq://test/Results/123")!

        // When
        let resultLower = sut.parse(urlLower)
        let resultMixed = sut.parse(urlMixed)

        // Then
        XCTAssertEqual(resultLower, .testResults(id: 123), "lowercase path should work")
        XCTAssertEqual(resultMixed, .invalid, "mixed case path should be invalid")
    }

    func testParse_CaseSensitive_UniversalLink() {
        // Given
        let urlLower = URL(string: "https://aiq.app/test/results/123")!
        let urlMixed = URL(string: "https://aiq.app/Test/Results/123")!

        // When
        let resultLower = sut.parse(urlLower)
        let resultMixed = sut.parse(urlMixed)

        // Then
        XCTAssertEqual(resultLower, .testResults(id: 123), "lowercase path should work")
        XCTAssertEqual(resultMixed, .invalid, "mixed case path should be invalid")
    }

    // MARK: - Integration Tests

    func testParse_AllSupportedRoutes_URLScheme() {
        // Test all supported URL scheme routes
        let testCases: [(String, DeepLink)] = [
            ("aiq://test/results/1", .testResults(id: 1)),
            ("aiq://test/results/999", .testResults(id: 999)),
            ("aiq://test/resume/50", .resumeTest(sessionId: 50)),
            ("aiq://test/resume/123", .resumeTest(sessionId: 123)),
            ("aiq://settings", .settings)
        ]

        for (urlString, expected) in testCases {
            guard let url = URL(string: urlString) else {
                XCTFail("Failed to create URL from \(urlString)")
                continue
            }

            let result = sut.parse(url)
            XCTAssertEqual(result, expected, "Failed to parse \(urlString)")
        }
    }

    func testParse_AllSupportedRoutes_UniversalLink() {
        // Test all supported universal link routes (production domain)
        let testCases: [(String, DeepLink)] = [
            ("https://aiq.app/test/results/1", .testResults(id: 1)),
            ("https://aiq.app/test/results/999", .testResults(id: 999)),
            ("https://aiq.app/test/resume/50", .resumeTest(sessionId: 50)),
            ("https://aiq.app/test/resume/123", .resumeTest(sessionId: 123)),
            ("https://aiq.app/settings", .settings)
        ]

        for (urlString, expected) in testCases {
            guard let url = URL(string: urlString) else {
                XCTFail("Failed to create URL from \(urlString)")
                continue
            }

            let result = sut.parse(url)
            XCTAssertEqual(result, expected, "Failed to parse \(urlString)")
        }
    }

    func testParse_AllSupportedRoutes_UniversalLink_DevDomain() {
        // Test all supported universal link routes (development domain)
        let testCases: [(String, DeepLink)] = [
            ("https://dev.aiq.app/test/results/1", .testResults(id: 1)),
            ("https://dev.aiq.app/test/results/999", .testResults(id: 999)),
            ("https://dev.aiq.app/test/resume/50", .resumeTest(sessionId: 50)),
            ("https://dev.aiq.app/test/resume/123", .resumeTest(sessionId: 123)),
            ("https://dev.aiq.app/settings", .settings)
        ]

        for (urlString, expected) in testCases {
            guard let url = URL(string: urlString) else {
                XCTFail("Failed to create URL from \(urlString)")
                continue
            }

            let result = sut.parse(url)
            XCTAssertEqual(result, expected, "Failed to parse dev domain URL: \(urlString)")
        }
    }

    func testParse_URLSchemeAndUniversalLink_Equivalence() {
        // Verify that URL scheme and universal link produce same result
        let equivalentPairs: [(String, String)] = [
            ("aiq://test/results/123", "https://aiq.app/test/results/123"),
            ("aiq://test/resume/456", "https://aiq.app/test/resume/456"),
            ("aiq://settings", "https://aiq.app/settings")
        ]

        for (urlScheme, universalLink) in equivalentPairs {
            guard let url1 = URL(string: urlScheme),
                  let url2 = URL(string: universalLink) else {
                XCTFail("Failed to create URLs")
                continue
            }

            let result1 = sut.parse(url1)
            let result2 = sut.parse(url2)

            XCTAssertEqual(result1, result2, "URL scheme \(urlScheme) and universal link \(universalLink) should produce same result")
        }
    }

    // MARK: - Deep Link Navigation Tests

    // Note: testHandleNavigation_Settings is intentionally not tested here because
    // settings deep links are handled at the tab level in MainTabView, not via
    // handleNavigation(). Calling handleNavigation() with .settings is a programming
    // error and results in fatalError.

    @MainActor
    func testHandleNavigation_ResumeTest_NavigatesToTestTakingWithSessionId() async {
        // Given
        let deepLink = DeepLink.resumeTest(sessionId: 123)
        let mockRouter = AppRouter()

        // When
        let result = await sut.handleNavigation(deepLink, router: mockRouter)

        // Then
        // Session resumption navigates to testTaking with the sessionId
        XCTAssertTrue(result, "Resume test navigation should return true")
        XCTAssertEqual(mockRouter.depth, 1, "Should have navigated to testTaking")
    }

    @MainActor
    func testHandleNavigation_Invalid_ReturnsFalse() async {
        // Given
        let deepLink = DeepLink.invalid
        let mockRouter = AppRouter()

        // When
        let result = await sut.handleNavigation(deepLink, router: mockRouter)

        // Then
        XCTAssertFalse(result, "Invalid navigation should return false")
        XCTAssertEqual(mockRouter.depth, 0, "Should not have navigated")
    }

    // MARK: - Test Results Deep Link Navigation Tests (with Mock API)

    @MainActor
    func testHandleNavigation_TestResults_Success_NavigatesToTestDetail() async {
        // Given
        let testId = 123
        let deepLink = DeepLink.testResults(id: testId)
        let mockRouter = AppRouter()
        let mockAPIClient = MockAPIClient()

        // Create a mock test result that will be returned by the API
        let mockTestResult = MockDataFactory.makeTestResult(
            id: testId,
            testSessionId: 456,
            userId: 1,
            iqScore: 110,
            totalQuestions: 20,
            correctAnswers: 15,
            accuracyPercentage: 75.0,
            completedAt: Date()
        )

        // Configure mock to return the test result
        await mockAPIClient.setResponse(mockTestResult, for: .testResults(String(testId)))

        // When
        let result = await sut.handleNavigation(deepLink, router: mockRouter, apiClient: mockAPIClient)

        // Then
        XCTAssertTrue(result, "Navigation should return true on successful API call")
        XCTAssertEqual(mockRouter.depth, 1, "Should have navigated to testDetail")

        // Verify the API was called
        let requestCalled = await mockAPIClient.requestCalled
        XCTAssertTrue(requestCalled, "API client should have been called")
    }

    @MainActor
    func testHandleNavigation_TestResults_APIError_ReturnsFalse() async {
        // Given
        let testId = 999
        let deepLink = DeepLink.testResults(id: testId)
        let mockRouter = AppRouter()
        let mockAPIClient = MockAPIClient()

        // Configure mock to throw an error (simulating test not found)
        await mockAPIClient.setError(APIError.notFound(message: "Test result not found"), for: .testResults(String(testId)))

        // When
        let result = await sut.handleNavigation(deepLink, router: mockRouter, apiClient: mockAPIClient)

        // Then
        XCTAssertFalse(result, "Navigation should return false on API error")
        XCTAssertEqual(mockRouter.depth, 0, "Should not have navigated")

        // Verify the API was called
        let requestCalled = await mockAPIClient.requestCalled
        XCTAssertTrue(requestCalled, "API client should have been called")
    }

    @MainActor
    func testHandleNavigation_TestResults_NetworkError_ReturnsFalse() async {
        // Given
        let testId = 456
        let deepLink = DeepLink.testResults(id: testId)
        let mockRouter = AppRouter()
        let mockAPIClient = MockAPIClient()

        // Configure mock to throw a network error
        let networkError = URLError(.notConnectedToInternet)
        await mockAPIClient.setError(APIError.networkError(networkError), for: .testResults(String(testId)))

        // When
        let result = await sut.handleNavigation(deepLink, router: mockRouter, apiClient: mockAPIClient)

        // Then
        XCTAssertFalse(result, "Navigation should return false on network error")
        XCTAssertEqual(mockRouter.depth, 0, "Should not have navigated")
    }

    @MainActor
    func testHandleNavigation_TestResults_ServerError_ReturnsFalse() async {
        // Given
        let testId = 789
        let deepLink = DeepLink.testResults(id: testId)
        let mockRouter = AppRouter()
        let mockAPIClient = MockAPIClient()

        // Configure mock to throw a server error
        await mockAPIClient.setError(APIError.serverError(statusCode: 500, message: "Internal server error"), for: .testResults(String(testId)))

        // When
        let result = await sut.handleNavigation(deepLink, router: mockRouter, apiClient: mockAPIClient)

        // Then
        XCTAssertFalse(result, "Navigation should return false on server error")
        XCTAssertEqual(mockRouter.depth, 0, "Should not have navigated")
    }

    @MainActor
    func testHandleNavigation_TestResults_NavigatesToSpecifiedTab() async {
        // Given
        let testId = 123
        let deepLink = DeepLink.testResults(id: testId)
        let mockRouter = AppRouter()
        let mockAPIClient = MockAPIClient()

        // Create a mock test result
        let mockTestResult = MockDataFactory.makeTestResult(
            id: testId,
            testSessionId: 456,
            userId: 1,
            iqScore: 105,
            totalQuestions: 20,
            correctAnswers: 14,
            accuracyPercentage: 70.0,
            completedAt: Date()
        )

        await mockAPIClient.setResponse(mockTestResult, for: .testResults(String(testId)))

        // When - navigate to history tab explicitly
        let result = await sut.handleNavigation(deepLink, router: mockRouter, tab: .history, apiClient: mockAPIClient)

        // Then
        XCTAssertTrue(result, "Navigation should return true")
        XCTAssertEqual(mockRouter.depth(in: .history), 1, "Should have navigated in history tab")
        XCTAssertEqual(mockRouter.depth(in: .dashboard), 0, "Dashboard should remain at root")
    }

    @MainActor
    func testHandleNavigation_TestResults_UsesCurrentTabWhenTabNotSpecified() async {
        // Given
        let testId = 123
        let deepLink = DeepLink.testResults(id: testId)
        let mockRouter = AppRouter()
        let mockAPIClient = MockAPIClient()

        // Set current tab to history
        mockRouter.currentTab = .history

        // Create a mock test result
        let mockTestResult = MockDataFactory.makeTestResult(
            id: testId,
            testSessionId: 456,
            userId: 1,
            iqScore: 115,
            totalQuestions: 20,
            correctAnswers: 16,
            accuracyPercentage: 80.0,
            completedAt: Date()
        )

        await mockAPIClient.setResponse(mockTestResult, for: .testResults(String(testId)))

        // When - don't specify tab, should use router's currentTab
        let result = await sut.handleNavigation(deepLink, router: mockRouter, apiClient: mockAPIClient)

        // Then
        XCTAssertTrue(result, "Navigation should return true")
        XCTAssertEqual(mockRouter.depth(in: .history), 1, "Should have navigated in current tab (history)")
        XCTAssertEqual(mockRouter.depth(in: .dashboard), 0, "Dashboard should remain at root")
    }

    // MARK: - DeepLink Analytics Destination Type Tests

    func testDeepLink_AnalyticsDestinationType_TestResults() {
        // Given
        let deepLink = DeepLink.testResults(id: 123)

        // Then
        XCTAssertEqual(deepLink.analyticsDestinationType, "test_results")
    }

    func testDeepLink_AnalyticsDestinationType_ResumeTest() {
        // Given
        let deepLink = DeepLink.resumeTest(sessionId: 456)

        // Then
        XCTAssertEqual(deepLink.analyticsDestinationType, "resume_test")
    }

    func testDeepLink_AnalyticsDestinationType_Settings() {
        // Given
        let deepLink = DeepLink.settings

        // Then
        XCTAssertEqual(deepLink.analyticsDestinationType, "settings")
    }

    func testDeepLink_AnalyticsDestinationType_Invalid() {
        // Given
        let deepLink = DeepLink.invalid

        // Then
        XCTAssertEqual(deepLink.analyticsDestinationType, "invalid")
    }

    // MARK: - DeepLinkSource Tests

    func testDeepLinkSource_RawValues() {
        // Verify all source raw values are correctly defined
        XCTAssertEqual(DeepLinkSource.pushNotification.rawValue, "push_notification")
        XCTAssertEqual(DeepLinkSource.externalApp.rawValue, "external_app")
        XCTAssertEqual(DeepLinkSource.safari.rawValue, "safari")
        XCTAssertEqual(DeepLinkSource.urlScheme.rawValue, "url_scheme")
        XCTAssertEqual(DeepLinkSource.universalLink.rawValue, "universal_link")
        XCTAssertEqual(DeepLinkSource.unknown.rawValue, "unknown")
    }
}
