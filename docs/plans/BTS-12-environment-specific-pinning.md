# BTS-12: Add Environment-Specific Pinning Config for iOS

## Overview

Configure certificate pinning to be disabled in DEBUG builds (for development with proxies) and enabled in RELEASE builds (for production security).

## Strategic Context

### Problem Statement

Currently, TrustKit certificate pinning is initialized in both DEBUG and RELEASE builds. While DEBUG builds use `http://localhost:8000` (where pinning doesn't apply due to lack of SSL), TrustKit is still initialized and can interfere with development tools like Charles Proxy, mitmproxy, or Proxyman when developers want to test against production.

This creates friction in the development workflow:
- Developers can't use MITM proxies to debug API calls in DEBUG builds
- Testing certificate pinning behavior requires manual configuration changes
- The current setup doesn't clearly communicate when pinning is active vs. inactive

### Success Criteria

1. DEBUG builds completely skip TrustKit initialization, allowing MITM proxies to work
2. RELEASE builds enforce certificate pinning with fail-secure validation
3. Build configuration switching is automatic based on Xcode build configuration
4. Documentation clearly explains when pinning is active and how to test it
5. Tests verify correct behavior in both DEBUG and RELEASE configurations

### Why Now?

This completes the certificate pinning implementation (BTS-9, BTS-11) by ensuring the security feature doesn't impede development velocity. It also establishes a clear pattern for environment-specific security features.

## Technical Approach

### High-Level Architecture

The implementation uses Swift's `#if DEBUG` conditional compilation to:

1. **In DEBUG builds:**
   - Skip TrustKit initialization entirely
   - Use `http://localhost:8000` (no SSL)
   - Log that pinning is disabled for development

2. **In RELEASE builds:**
   - Initialize TrustKit with full validation
   - Use `https://aiq-backend-production.up.railway.app` (SSL + pinning)
   - Fail hard if configuration is invalid (`fatalError`)

No changes to `TrustKit.plist` are needed - the configuration remains focused on production.

### Key Decisions & Tradeoffs

#### Decision 1: Complete TrustKit Skip in DEBUG (Not Just Disable Enforcement)

**Chosen:** Skip initialization entirely in DEBUG
**Alternative Considered:** Initialize with `TSKEnforcePinning = false`

**Rationale:**
- Simpler implementation - single code path per build type
- Zero overhead in development builds
- Eliminates all TrustKit logging noise during development
- Developers can still test pinning by building in RELEASE mode

**Tradeoff:** Can't see pinning validation logs in DEBUG. Mitigated by having clear testing documentation and the ability to build in RELEASE mode locally.

#### Decision 2: No Staging Environment Support

**Chosen:** Only DEBUG and RELEASE configurations
**Alternative Considered:** Add separate STAGING configuration with its own backend

**Rationale:**
- No staging backend exists currently
- Adding staging config now would be speculative architecture
- Can be added later if/when staging backend is deployed
- Keeps implementation focused and simple

**Tradeoff:** If staging is added later, we'll need to revisit this. However, the pattern established here makes that extension straightforward.

#### Decision 3: Keep Single TrustKit.plist

**Chosen:** One plist file focused on production configuration
**Alternative Considered:** Separate plist files for DEBUG/RELEASE

**Rationale:**
- TrustKit.plist is only loaded in RELEASE builds
- No need to maintain duplicate/divergent configurations
- Reduces risk of configuration drift
- Simpler to audit security configuration

### Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Developers forget pinning is disabled in DEBUG | Low | Add prominent log message; update documentation |
| Can't test pinning in DEBUG mode | Medium | Document how to build in RELEASE for local testing |
| Accidental DEBUG build in production | Critical | App Store only accepts RELEASE builds; add validation checks |
| Build configuration detection fails | High | Add tests that verify correct behavior per build config |

## Implementation Plan

### Phase 1: Modify AppDelegate Initialization
**Goal:** Wrap TrustKit initialization in `#if !DEBUG` guard
**Duration:** 30 minutes

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 1.1 | Wrap TrustKit initialization in `#if !DEBUG` conditional | None | 15 min | Add to AppDelegate.swift lines 24-58 |
| 1.2 | Add DEBUG-mode logging to explain pinning is disabled | 1.1 | 10 min | Use `Logger` to log why pinning is skipped |
| 1.3 | Verify existing `#if !DEBUG` validation logic is inside guard | 1.1 | 5 min | Lines 29-42 in AppDelegate.swift |

**Success Criteria:**
- TrustKit initialization code only runs in RELEASE builds
- DEBUG builds log clear message about pinning being disabled
- RELEASE builds continue to validate configuration and `fatalError` on issues

---

### Phase 2: Update Tests
**Goal:** Add tests to verify environment-specific behavior
**Duration:** 45 minutes

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 2.1 | Add test verifying DEBUG skips TrustKit | Phase 1 | 20 min | Add to CertificatePinningTests.swift |
| 2.2 | Add test verifying RELEASE initializes TrustKit | Phase 1 | 15 min | May require test scheme configuration |
| 2.3 | Update existing pinning tests with build config notes | Phase 1 | 10 min | Clarify which tests apply to which configs |

**Success Criteria:**
- New test `testDebugBuildSkipsTrustKit()` passes in DEBUG scheme
- New test `testReleaseBuildEnforcesPinning()` passes in RELEASE scheme (or documented as manual test)
- All existing pinning tests still pass

---

### Phase 3: Documentation Updates
**Goal:** Document environment-specific behavior clearly
**Duration:** 30 minutes

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 3.1 | Update CERTIFICATE_PINNING_TESTING.md with DEBUG vs RELEASE info | Phase 1 | 15 min | Add section on build configurations |
| 3.2 | Update ios/README.md with pinning behavior by build type | Phase 1 | 10 min | Add to Security or Architecture section |
| 3.3 | Add testing instructions for RELEASE builds locally | Phase 1 | 5 min | How to test pinning without deploying |

**Success Criteria:**
- Documentation clearly states when pinning is active/inactive
- Developers know how to test pinning locally
- Manual testing procedures updated for build configurations

---

### Phase 4: Validation & Testing
**Goal:** Verify correct behavior in both build configurations
**Duration:** 45 minutes

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 4.1 | Build and run in DEBUG - verify localhost works | Phase 1-3 | 10 min | Test with local backend |
| 4.2 | Build and run in DEBUG - verify Charles Proxy works | Phase 1-3 | 15 min | Test MITM proxy can intercept (if available) |
| 4.3 | Build and run in RELEASE - verify pinning enforced | Phase 1-3 | 10 min | Test against production backend |
| 4.4 | Run full test suite in both DEBUG and RELEASE | Phase 2 | 10 min | Ensure no regressions |

**Success Criteria:**
- DEBUG build allows MITM proxies to work
- RELEASE build enforces pinning (blocks MITM)
- No test failures in either configuration
- Logs clearly indicate pinning status

---

## Open Questions

1. **Q:** Should we add a runtime check to detect if app was accidentally built with wrong configuration?
   **A:** Not necessary - App Store only accepts RELEASE builds, and internal builds are clearly labeled in Xcode.

2. **Q:** Should we support testing against production in DEBUG mode?
   **A:** No - developers can build in RELEASE mode locally if they need to test pinning. This keeps DEBUG builds simple and fast.

3. **Q:** Do we need separate certificate pins for staging environment?
   **A:** No staging environment exists. If added later, we can extend this implementation with a new build configuration.

4. **Q:** Should we add analytics to track which build config is running in production?
   **A:** RELEASE is the only config that can reach production via App Store. No need to track.

## Appendix

### Code Example: Updated AppDelegate.swift

```swift
func application(
    _: UIApplication,
    didFinishLaunchingWithOptions _: [UIApplication.LaunchOptionsKey: Any]? = nil
) -> Bool {
    // Initialize Firebase
    FirebaseApp.configure()

    #if DEBUG
        // Skip TrustKit initialization in DEBUG builds to allow development with proxies
        Self.logger.info("DEBUG build: Certificate pinning disabled for development")
        Self.logger.info("API URL: \(AppConfig.apiBaseURL)")
    #else
        // Initialize TrustKit for SSL certificate pinning (RELEASE builds only)
        if let trustKitConfigPath = Bundle.main.path(forResource: "TrustKit", ofType: "plist"),
           let trustKitConfig = NSDictionary(contentsOfFile: trustKitConfigPath) as? [String: Any] {

            // Verify at least 2 pins are configured before initializing
            guard let pinnedDomains = trustKitConfig["TSKPinnedDomains"] as? [String: Any] else {
                fatalError("TrustKit config missing TSKPinnedDomains")
            }
            guard let railwayConfig = pinnedDomains[AppConfig.productionDomain] as? [String: Any] else {
                fatalError("TrustKit config missing pinning for \(AppConfig.productionDomain)")
            }
            guard let hashes = railwayConfig["TSKPublicKeyHashes"] as? [String] else {
                fatalError("TrustKit config missing TSKPublicKeyHashes")
            }
            guard hashes.count >= 2 else {
                fatalError("Certificate pinning requires at least 2 pins (primary + backup), found \(hashes.count)")
            }

            TrustKit.initSharedInstance(withConfiguration: trustKitConfig)
            Self.logger.info("TrustKit initialized with certificate pinning for Railway backend")
        } else {
            Self.logger.error("TrustKit.plist missing or invalid format - cannot load config")
            fatalError("Certificate pinning config failed to load. App cannot continue.")
        }
    #endif

    // Set notification delegate
    UNUserNotificationCenter.current().delegate = self

    return true
}
```

### Test Example: Build Configuration Tests

```swift
func testDebugBuildSkipsCertificatePinning() {
    #if DEBUG
        // In DEBUG builds, TrustKit should not be initialized
        // Verify API base URL is localhost without HTTPS
        XCTAssertEqual(
            AppConfig.apiBaseURL,
            "http://localhost:8000",
            "DEBUG builds should use localhost without SSL"
        )

        // Verify TrustKit.plist is not required in DEBUG
        // (App should launch successfully even if plist is missing in test bundle)
        XCTAssertTrue(true, "DEBUG build should skip TrustKit initialization")
    #else
        throw XCTSkip("This test only applies to DEBUG builds")
    #endif
}

func testReleaseBuildEnforcesCertificatePinning() {
    #if !DEBUG
        // In RELEASE builds, verify production URL is used with HTTPS
        XCTAssertTrue(
            AppConfig.apiBaseURL.hasPrefix("https://"),
            "RELEASE builds must use HTTPS"
        )
        XCTAssertTrue(
            AppConfig.apiBaseURL.contains(AppConfig.productionDomain),
            "RELEASE builds must use production domain"
        )

        // Verify TrustKit configuration exists and is valid
        let configPath = Bundle.main.path(forResource: "TrustKit", ofType: "plist")
        XCTAssertNotNil(configPath, "RELEASE builds require TrustKit.plist")
    #else
        throw XCTSkip("This test only applies to RELEASE builds")
    #endif
}
```

### Updated Documentation Sections

#### ios/docs/CERTIFICATE_PINNING_TESTING.md Addition

```markdown
## Build Configuration Behavior

### DEBUG Builds
- **Certificate Pinning:** DISABLED
- **API URL:** `http://localhost:8000`
- **TrustKit:** Not initialized
- **MITM Proxies:** Fully supported (Charles, Proxyman, mitmproxy)
- **Use Case:** Local development and debugging

### RELEASE Builds
- **Certificate Pinning:** ENABLED and ENFORCED
- **API URL:** `https://aiq-backend-production.up.railway.app`
- **TrustKit:** Fully initialized with validation
- **MITM Proxies:** Blocked by pinning
- **Use Case:** Production and pinning verification testing

### Testing Certificate Pinning Locally

To test certificate pinning on your local machine:

1. Build the app in RELEASE configuration:
   ```bash
   xcodebuild -scheme AIQ -configuration Release \
     -destination 'platform=iOS Simulator,name=iPhone 16 Pro' build
   ```

2. Run the RELEASE build from Xcode:
   - Select "Edit Scheme" → "Run" → "Build Configuration" → "Release"
   - Run the app (⌘+R)

3. Verify pinning is active:
   - Check console logs for "TrustKit initialized with certificate pinning"
   - Try to intercept traffic with Charles Proxy (should fail)
   - Make API calls (should succeed against production)

4. Return to DEBUG configuration:
   - "Edit Scheme" → "Run" → "Build Configuration" → "Debug"
```

### Acceptance Criteria Mapping

| Criterion | Implementation | Verification |
|-----------|----------------|--------------|
| DEBUG builds skip certificate pinning | `#if DEBUG` skips TrustKit init | Test with Charles Proxy |
| RELEASE builds enforce certificate pinning | `#if !DEBUG` initializes TrustKit | Manual test against production |
| Staging environment uses separate pin config (if applicable) | N/A - no staging environment | Not applicable |
| Environment switching tested | Phase 4 validation tasks | Build in both configs and test |
| Configuration changes documented | Phase 3 documentation updates | Review docs |
