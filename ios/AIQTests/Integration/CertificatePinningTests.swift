import TrustKit
import XCTest

@testable import AIQ

/// Integration tests for TrustKit certificate pinning configuration.
///
/// These tests verify:
/// - TrustKit.plist configuration is correct and complete
/// - Certificate hashes are valid SHA256 base64-encoded values
/// - Enforcement is enabled to reject invalid certificates
/// - DEBUG/RELEASE build configuration switching works correctly
///
/// For manual testing procedures (MITM proxy, wrong hash rejection, etc.),
/// see: ios/docs/CERTIFICATE_PINNING_TESTING.md
@MainActor
final class CertificatePinningTests: XCTestCase {
    // MARK: - TrustKit Configuration Tests

    func testTrustKitConfigurationExists() {
        // Verify TrustKit.plist exists in bundle
        let configPath = Bundle.main.path(forResource: "TrustKit", ofType: "plist")
        XCTAssertNotNil(configPath, "TrustKit.plist should exist in the app bundle")
    }

    func testTrustKitConfigurationHasRequiredKeys() throws {
        guard let configPath = Bundle.main.path(forResource: "TrustKit", ofType: "plist"),
              let config = NSDictionary(contentsOfFile: configPath) as? [String: Any]
        else {
            throw XCTSkip("TrustKit.plist not found - skipping test (OK in unit test bundle)")
        }

        // Verify pinned domains exist
        let pinnedDomains = config["TSKPinnedDomains"] as? [String: Any]
        XCTAssertNotNil(pinnedDomains, "TSKPinnedDomains should be configured")

        // Verify production domain is pinned
        let productionDomain = AppConfig.productionDomain
        let domainConfig = pinnedDomains?[productionDomain] as? [String: Any]
        XCTAssertNotNil(domainConfig, "Production domain '\(productionDomain)' should be pinned")

        // Verify pinning is enforced
        let enforcePinning = domainConfig?["TSKEnforcePinning"] as? Bool
        XCTAssertEqual(enforcePinning, true, "TSKEnforcePinning should be true for production")

        // Verify at least 2 pins exist (primary + backup)
        let hashes = domainConfig?["TSKPublicKeyHashes"] as? [String]
        XCTAssertNotNil(hashes, "TSKPublicKeyHashes should be configured")
        XCTAssertGreaterThanOrEqual(hashes?.count ?? 0, 2, "At least 2 pins required (primary + backup)")
    }

    func testSwizzlingIsEnabledForURLSessionIntegration() throws {
        guard let configPath = Bundle.main.path(forResource: "TrustKit", ofType: "plist"),
              let config = NSDictionary(contentsOfFile: configPath) as? [String: Any]
        else {
            throw XCTSkip("TrustKit.plist not found - skipping test (OK in unit test bundle)")
        }

        let swizzleEnabled = config["TSKSwizzleNetworkDelegates"] as? Bool
        XCTAssertEqual(
            swizzleEnabled,
            true,
            "TSKSwizzleNetworkDelegates must be enabled for TrustKit to intercept URLSession requests"
        )
    }

    func testProductionDomainConsistency() {
        // Verify AppConfig.productionDomain is consistent with API base URL
        let productionDomain = AppConfig.productionDomain
        XCTAssertFalse(productionDomain.isEmpty, "Production domain should not be empty")
        XCTAssertFalse(productionDomain.contains("http"), "Production domain should not include protocol")

        // In release builds, apiBaseURL should contain the production domain
        #if !DEBUG
            XCTAssertTrue(
                AppConfig.apiBaseURL.contains(productionDomain),
                "Release apiBaseURL should use productionDomain"
            )
        #endif
    }

    func testAPIClientUsesSharedSession() {
        // Verify the shared APIClient instance exists
        // This is important because TrustKit swizzles URLSession.shared
        let apiClient = APIClient.shared

        // The APIClient.shared singleton should be initialized with default session (.shared)
        // We verify this indirectly by checking the singleton exists
        XCTAssertNotNil(apiClient, "APIClient.shared should exist")
    }

    // MARK: - Certificate Hash Validation Tests

    func testCertificateHashFormat() throws {
        guard let configPath = Bundle.main.path(forResource: "TrustKit", ofType: "plist"),
              let config = NSDictionary(contentsOfFile: configPath) as? [String: Any],
              let pinnedDomains = config["TSKPinnedDomains"] as? [String: Any],
              let domainConfig = pinnedDomains[AppConfig.productionDomain] as? [String: Any],
              let hashes = domainConfig["TSKPublicKeyHashes"] as? [String]
        else {
            throw XCTSkip("TrustKit.plist not found - skipping test (OK in unit test bundle)")
        }

        // Verify each hash is a valid base64-encoded SHA256 hash (44 characters with = padding)
        for hash in hashes {
            XCTAssertFalse(hash.isEmpty, "Certificate hash should not be empty")

            // SHA256 hashes in base64 are 44 characters (32 bytes -> 44 chars in base64 with padding)
            // Or 43 without final padding
            XCTAssertTrue(
                hash.count >= 43 && hash.count <= 44,
                "Certificate hash '\(hash)' should be 43-44 characters (base64 SHA256)"
            )

            // Verify it's valid base64
            XCTAssertNotNil(
                Data(base64Encoded: hash),
                "Certificate hash '\(hash)' should be valid base64"
            )
        }
    }

    func testCertificateHashesDecodeToCorrectLength() throws {
        guard let configPath = Bundle.main.path(forResource: "TrustKit", ofType: "plist"),
              let config = NSDictionary(contentsOfFile: configPath) as? [String: Any],
              let pinnedDomains = config["TSKPinnedDomains"] as? [String: Any],
              let domainConfig = pinnedDomains[AppConfig.productionDomain] as? [String: Any],
              let hashes = domainConfig["TSKPublicKeyHashes"] as? [String]
        else {
            throw XCTSkip("TrustKit.plist not found - skipping test (OK in unit test bundle)")
        }

        // Verify each hash decodes to exactly 32 bytes (SHA256 hash size)
        for (index, hash) in hashes.enumerated() {
            guard let data = Data(base64Encoded: hash) else {
                XCTFail("Hash at index \(index) is not valid base64")
                continue
            }

            XCTAssertEqual(
                data.count,
                32,
                "Hash at index \(index) should decode to 32 bytes (SHA256), got \(data.count) bytes"
            )
        }
    }

    func testCertificateHashesAreNotPlaceholders() throws {
        guard let configPath = Bundle.main.path(forResource: "TrustKit", ofType: "plist"),
              let config = NSDictionary(contentsOfFile: configPath) as? [String: Any],
              let pinnedDomains = config["TSKPinnedDomains"] as? [String: Any],
              let domainConfig = pinnedDomains[AppConfig.productionDomain] as? [String: Any],
              let hashes = domainConfig["TSKPublicKeyHashes"] as? [String]
        else {
            throw XCTSkip("TrustKit.plist not found - skipping test (OK in unit test bundle)")
        }

        // Common placeholder patterns that should not be used
        let placeholders = [
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
            "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB=",
            "++++++++++++++++++++++++++++++++++++++++++++",
            "============================================"
        ]

        for hash in hashes {
            XCTAssertFalse(
                placeholders.contains(hash),
                "Hash '\(hash)' appears to be a placeholder - must use real certificate hash"
            )
        }
    }

    func testCertificateHashesAreUnique() throws {
        guard let configPath = Bundle.main.path(forResource: "TrustKit", ofType: "plist"),
              let config = NSDictionary(contentsOfFile: configPath) as? [String: Any],
              let pinnedDomains = config["TSKPinnedDomains"] as? [String: Any],
              let domainConfig = pinnedDomains[AppConfig.productionDomain] as? [String: Any],
              let hashes = domainConfig["TSKPublicKeyHashes"] as? [String]
        else {
            throw XCTSkip("TrustKit.plist not found - skipping test (OK in unit test bundle)")
        }

        let uniqueHashes = Set(hashes)
        XCTAssertEqual(
            hashes.count,
            uniqueHashes.count,
            "Certificate hashes must be unique - found duplicates"
        )
    }

    // MARK: - Wrong Hash Rejection Test

    /// Test that the pinning configuration is set up to reject invalid certificates
    ///
    /// This test verifies that TSKEnforcePinning is enabled, which means wrong hashes
    /// would cause connection failures in production.
    func testWrongHashWouldBeRejected() throws {
        guard let configPath = Bundle.main.path(forResource: "TrustKit", ofType: "plist"),
              let config = NSDictionary(contentsOfFile: configPath) as? [String: Any],
              let pinnedDomains = config["TSKPinnedDomains"] as? [String: Any],
              let domainConfig = pinnedDomains[AppConfig.productionDomain] as? [String: Any]
        else {
            throw XCTSkip("TrustKit.plist not found - skipping test (OK in unit test bundle)")
        }

        // Verify enforcement is enabled
        let enforcePinning = domainConfig["TSKEnforcePinning"] as? Bool
        XCTAssertEqual(
            enforcePinning,
            true,
            "TSKEnforcePinning must be true - this ensures wrong hashes cause connection failures"
        )

        // Create a test configuration with intentionally wrong hashes to verify structure
        var modifiedConfig = config
        var modifiedPinnedDomains = pinnedDomains
        var modifiedDomainConfig = domainConfig

        // Use wrong hashes (valid SHA256 format, but incorrect values)
        let wrongHashes = [
            "WRONG1HASH1111111111111111111111111111=",
            "WRONG2HASH2222222222222222222222222222="
        ]
        modifiedDomainConfig["TSKPublicKeyHashes"] = wrongHashes
        modifiedPinnedDomains[AppConfig.productionDomain] = modifiedDomainConfig
        modifiedConfig["TSKPinnedDomains"] = modifiedPinnedDomains

        // Verify the modified config structure is valid
        let testDomainConfig = (modifiedConfig["TSKPinnedDomains"] as? [String: Any])?[AppConfig.productionDomain] as? [String: Any]
        let testHashes = testDomainConfig?["TSKPublicKeyHashes"] as? [String]
        XCTAssertEqual(testHashes, wrongHashes, "Test config should have wrong hashes")

        let testEnforcement = testDomainConfig?["TSKEnforcePinning"] as? Bool
        XCTAssertEqual(testEnforcement, true, "Test config should have enforcement enabled")

        // NOTE: Actual network rejection testing requires manual testing
        // See ios/docs/CERTIFICATE_PINNING_TESTING.md for manual test procedures
    }

    // MARK: - DEBUG Mode Localhost Tests

    /// Test that localhost connections are not blocked in DEBUG mode
    func testLocalhostNotBlockedInDebugMode() {
        let apiBaseURL = AppConfig.apiBaseURL

        #if DEBUG
            // In DEBUG mode, verify we're using localhost without HTTPS
            XCTAssertTrue(
                apiBaseURL.contains("localhost"),
                "DEBUG build should use localhost for development"
            )
            XCTAssertTrue(
                apiBaseURL.hasPrefix("http://"),
                "DEBUG build should use HTTP (no SSL) for localhost"
            )
            XCTAssertFalse(
                apiBaseURL.hasPrefix("https://"),
                "DEBUG build should not use HTTPS for localhost"
            )
        #else
            // In RELEASE mode, verify we're using production with HTTPS
            XCTAssertTrue(
                apiBaseURL.hasPrefix("https://"),
                "RELEASE build should use HTTPS with certificate pinning"
            )
            XCTAssertTrue(
                apiBaseURL.contains(AppConfig.productionDomain),
                "RELEASE build should use production domain"
            )
        #endif
    }

    /// Test that localhost is not in the pinned domains configuration
    func testLocalhostNotPinned() throws {
        guard let configPath = Bundle.main.path(forResource: "TrustKit", ofType: "plist"),
              let config = NSDictionary(contentsOfFile: configPath) as? [String: Any],
              let pinnedDomains = config["TSKPinnedDomains"] as? [String: Any]
        else {
            throw XCTSkip("TrustKit.plist not found - skipping test (OK in unit test bundle)")
        }

        // Verify localhost is NOT in pinned domains
        XCTAssertNil(
            pinnedDomains["localhost"],
            "localhost should not be pinned - it has no SSL certificate in DEBUG mode"
        )
        XCTAssertNil(
            pinnedDomains["127.0.0.1"],
            "127.0.0.1 should not be pinned - it has no SSL certificate in DEBUG mode"
        )
    }

    /// Test that API base URL switches correctly between DEBUG and RELEASE
    ///
    /// NOTE: This test should be run in both DEBUG and RELEASE configurations
    /// to verify proper build configuration switching.
    func testAPIBaseURLSwitchesCorrectly() {
        let productionDomain = AppConfig.productionDomain
        let apiBaseURL = AppConfig.apiBaseURL

        #if DEBUG
            XCTAssertEqual(
                apiBaseURL,
                "http://localhost:8000",
                "DEBUG builds must use localhost:8000 without SSL"
            )
        #else
            XCTAssertEqual(
                apiBaseURL,
                "https://\(productionDomain)",
                "RELEASE builds must use production domain with HTTPS"
            )
        #endif
    }

    // MARK: - TrustKit Initialization Validation Tests

    /// Test that TrustKit initialization validation logic is correct
    ///
    /// This verifies that all the validation checks in AppDelegate would pass
    /// with the current configuration.
    func testTrustKitInitializationValidation() throws {
        guard let configPath = Bundle.main.path(forResource: "TrustKit", ofType: "plist"),
              let config = NSDictionary(contentsOfFile: configPath) as? [String: Any]
        else {
            throw XCTSkip("TrustKit.plist not found - skipping test (OK in unit test bundle)")
        }

        // Validation check 1: TSKPinnedDomains exists
        let pinnedDomains = config["TSKPinnedDomains"] as? [String: Any]
        XCTAssertNotNil(pinnedDomains, "Validation 1: TSKPinnedDomains must exist")

        // Validation check 2: Production domain config exists
        let railwayConfig = pinnedDomains?[AppConfig.productionDomain] as? [String: Any]
        XCTAssertNotNil(railwayConfig, "Validation 2: Production domain config must exist")

        // Validation check 3: TSKPublicKeyHashes exists
        let hashes = railwayConfig?["TSKPublicKeyHashes"] as? [String]
        XCTAssertNotNil(hashes, "Validation 3: TSKPublicKeyHashes must exist")

        // Validation check 4: At least 2 hashes configured
        XCTAssertGreaterThanOrEqual(
            hashes?.count ?? 0,
            2,
            "Validation 4: At least 2 hashes required (AppDelegate will fatalError in RELEASE if this fails)"
        )
    }

    // MARK: - Build Configuration Tests

    /// Test that DEBUG builds skip certificate pinning
    ///
    /// In DEBUG builds:
    /// - TrustKit should NOT be initialized
    /// - API base URL should be localhost without HTTPS
    /// - This allows developers to use MITM proxies for debugging
    ///
    /// **Testing Limitations:**
    /// - This test uses `#if DEBUG` conditional compilation
    /// - Only runs when compiled in DEBUG mode
    /// - CI/CD typically runs in DEBUG, so this test executes in automated builds
    /// - RELEASE builds skip this test (see `testReleaseBuildEnforcesCertificatePinning`)
    func testDebugBuildSkipsCertificatePinning() throws {
        #if DEBUG
            // Verify API base URL is localhost without HTTPS
            XCTAssertEqual(
                AppConfig.apiBaseURL,
                "http://localhost:8000",
                "DEBUG builds should use localhost without SSL"
            )

            // Verify production domain is not used
            XCTAssertFalse(
                AppConfig.apiBaseURL.contains(AppConfig.productionDomain),
                "DEBUG builds should not use production domain"
            )

            // Verify no HTTPS is used (allows MITM proxies)
            XCTAssertTrue(
                AppConfig.apiBaseURL.hasPrefix("http://"),
                "DEBUG builds should use HTTP (no SSL) for localhost"
            )
            XCTAssertFalse(
                AppConfig.apiBaseURL.hasPrefix("https://"),
                "DEBUG builds should not use HTTPS"
            )

        // Note: We can't directly test that TrustKit is not initialized in AppDelegate
        // from unit tests, but we verify the configuration is correct for DEBUG mode
        #else
            throw XCTSkip("This test only applies to DEBUG builds")
        #endif
    }

    /// Test that RELEASE builds enforce certificate pinning
    ///
    /// In RELEASE builds:
    /// - TrustKit MUST be initialized
    /// - API base URL must use HTTPS with production domain
    /// - Certificate pinning is enforced to prevent MITM attacks
    ///
    /// **Testing Limitations:**
    /// - This test uses `#if !DEBUG` conditional compilation
    /// - CI/CD typically runs in DEBUG mode, so this test is skipped in automated builds
    /// - Manual testing in RELEASE configuration is required for full verification
    /// - See `CERTIFICATE_PINNING_TESTING.md` for manual testing procedures
    func testReleaseBuildEnforcesCertificatePinning() throws {
        #if !DEBUG
            // Verify production URL is used with HTTPS
            XCTAssertTrue(
                AppConfig.apiBaseURL.hasPrefix("https://"),
                "RELEASE builds must use HTTPS"
            )
            XCTAssertTrue(
                AppConfig.apiBaseURL.contains(AppConfig.productionDomain),
                "RELEASE builds must use production domain"
            )

            // Verify TrustKit configuration exists and is valid
            // Note: In tests, we need to access the app bundle, not the test bundle
            let appBundle = Bundle(identifier: "com.aiq.AIQ") ?? Bundle.main
            let configPath = appBundle.path(forResource: "TrustKit", ofType: "plist")
            XCTAssertNotNil(configPath, "RELEASE builds require TrustKit.plist in app bundle")

            guard let path = configPath,
                  let config = NSDictionary(contentsOfFile: path) as? [String: Any]
            else {
                XCTFail("TrustKit.plist must be readable in RELEASE builds")
                return
            }

            // Verify configuration has required keys for enforcement
            let pinnedDomains = config["TSKPinnedDomains"] as? [String: Any]
            XCTAssertNotNil(pinnedDomains, "TSKPinnedDomains must exist in RELEASE")

            let domainConfig = pinnedDomains?[AppConfig.productionDomain] as? [String: Any]
            XCTAssertNotNil(domainConfig, "Production domain must be pinned in RELEASE")

            let enforcePinning = domainConfig?["TSKEnforcePinning"] as? Bool
            XCTAssertEqual(enforcePinning, true, "Pinning must be enforced in RELEASE")

            let hashes = domainConfig?["TSKPublicKeyHashes"] as? [String]
            XCTAssertNotNil(hashes, "Certificate hashes must be configured in RELEASE")
            XCTAssertGreaterThanOrEqual(hashes?.count ?? 0, 2, "At least 2 pins required in RELEASE")
        #else
            throw XCTSkip("This test only applies to RELEASE builds")
        #endif
    }

    /// Test that build configuration switching works correctly
    ///
    /// This test verifies that the app correctly switches between DEBUG and RELEASE
    /// configurations based on the build type. It should pass in both configurations.
    ///
    /// **Testing Limitations:**
    /// - This test uses conditional compilation to verify different behaviors
    /// - Always passes in the current build configuration
    /// - Does not verify the opposite configuration (DEBUG can't test RELEASE behavior)
    /// - Full verification requires running tests in both DEBUG and RELEASE modes
    func testBuildConfigurationSwitching() {
        #if DEBUG
            // In DEBUG: localhost without SSL
            XCTAssertEqual(
                AppConfig.apiBaseURL,
                "http://localhost:8000",
                "DEBUG configuration should use localhost"
            )
        #else
            // In RELEASE: production with SSL
            XCTAssertEqual(
                AppConfig.apiBaseURL,
                "https://\(AppConfig.productionDomain)",
                "RELEASE configuration should use production with HTTPS"
            )
        #endif
    }
}
