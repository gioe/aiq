# BTS-108: Education Level Picker Test - Analysis

**Issue:** BTS-108 - Add Education Level Picker Test
**Created:** From PR #397 review feedback
**Labels:** deferred, post-launch, ui-tests, registration

## Executive Summary

**Recommendation:** **Implement the test** - The education level picker is a fully functional UI component in the registration flow, and the test helper property should be used to verify its interaction.

**Rationale:** The `educationLevelButton` property in `RegistrationHelper` is not unused due to missing functionality—it's unused because the corresponding test was never written. The education level picker exists in production code and should be tested.

---

## Current State Analysis

### 1. Production Code Status

**File:** `/Users/mattgioe/aiq/ios/AIQ/Views/Auth/RegistrationView.swift` (lines 211-252)

The education level picker **IS implemented** in the registration flow:

```swift
// Education Level picker
VStack(alignment: .leading, spacing: DesignSystem.Spacing.xs) {
    Text("Education Level (Optional)")
        .font(Typography.captionLarge)
        .foregroundColor(ColorPalette.textSecondary)

    Menu {
        Button("None selected") {
            viewModel.selectedEducationLevel = nil
        }

        ForEach(EducationLevel.allCases, id: \.self) { level in
            Button(level.displayName) {
                viewModel.selectedEducationLevel = level
            }
        }
    } label: {
        HStack {
            Text(viewModel.selectedEducationLevel?.displayName ?? "Select education level")
                .font(Typography.bodyMedium)
                .foregroundColor(
                    viewModel.selectedEducationLevel == nil
                        ? ColorPalette.textSecondary
                        : ColorPalette.textPrimary
                )

            Spacer()

            Image(systemName: "chevron.down")
                .font(.system(size: DesignSystem.IconSize.sm))
                .foregroundColor(ColorPalette.textSecondary)
        }
        .padding(DesignSystem.Spacing.md)
        .background(ColorPalette.backgroundSecondary)
        .cornerRadius(DesignSystem.CornerRadius.md)
    }
    .accessibilityLabel(
        "Education Level, optional, " +
            "\(viewModel.selectedEducationLevel?.displayName ?? "not selected")"
    )
    .accessibilityHint("Double tap to open menu and select your education level")
}
```

**Key Observations:**
- The picker is fully implemented with proper accessibility labels
- It's part of the optional demographic fields section
- It uses a native SwiftUI `Menu` component
- The label text is "Select education level" (matches the test helper query)
- It has proper accessibility support for VoiceOver

### 2. Test Helper Status

**File:** `/Users/mattgioe/aiq/ios/AIQUITests/Helpers/RegistrationHelper.swift` (lines 84-87)

```swift
/// Education Level menu button (optional)
var educationLevelButton: XCUIElement {
    app.buttons["Select education level"]
}
```

**Status:** Property defined but never used in any tests.

### 3. Test Coverage Gap

**File:** `/Users/mattgioe/aiq/ios/AIQUITests/RegistrationFlowTests.swift`

The test file includes:
- ✅ Tests for other optional demographic fields (birth year, country, region)
- ✅ Test method `fillDemographicFields()` that fills birth year, country, and region
- ❌ **No test for education level picker interaction**
- ❌ **No method to fill education level in `RegistrationHelper`**

**Current `fillDemographicFields` method** (lines 230-269):
```swift
func fillDemographicFields(
    birthYear: String? = nil,
    country: String? = nil,
    region: String? = nil
) -> Bool {
    // Fills birth year, country, region
    // Education level is MISSING
}
```

---

## Gap Analysis

### Why This Wasn't Implemented Initially

Based on PR #397 review comments, this was flagged as **technical debt** during code review:

> **Issue #5: Missing Education Level Implementation**
>
> This element is defined but never used in any helper methods or tests. The `fillDemographicFields` method doesn't include education level.
>
> **Recommendation:** Either implement education level filling or add a comment explaining why it's not included.

The property was added for completeness but the test was never written, likely because:
1. The picker uses a `Menu` component (more complex to test than text fields)
2. Time constraints during initial implementation
3. Deferred as "nice to have" since it's an optional field

---

## Why We Should Implement the Test

### 1. Feature Exists in Production
The education level picker is a real UI component that users interact with. If it's worth building, it's worth testing.

### 2. Consistency with Other Optional Fields
All other optional demographic fields (birth year, country, region) are tested. Education level should be too.

### 3. Data Quality for Research
The registration view explicitly states:
> "Help Improve Our Research - This optional information helps us validate test accuracy."

Education level is important demographic data for cognitive assessment research.

### 4. Accessibility Coverage
The picker has proper accessibility labels and hints. We should verify they work correctly.

### 5. Regression Protection
Without tests, we risk:
- Breaking the picker during refactoring
- Accessibility regressions
- Menu interaction issues on different iOS versions

---

## Implementation Approach

### Recommended Subagent: `ios-engineer`

**Reason:** This requires:
- Swift/SwiftUI knowledge for UI test patterns
- Understanding of XCTest framework
- Knowledge of XCUITest menu interaction patterns
- Following existing test patterns in the codebase

### Implementation Tasks

#### Task 1: Add `fillEducationLevel` method to `RegistrationHelper`

**Location:** `ios/AIQUITests/Helpers/RegistrationHelper.swift`

```swift
/// Fill education level field
/// - Parameter level: The education level display name (e.g., "High School", "Bachelor's Degree")
/// - Returns: true if field was filled, false otherwise
@discardableResult
func fillEducationLevel(_ level: String) -> Bool {
    guard educationLevelButton.waitForExistence(timeout: timeout) else {
        XCTFail("Education level button not found")
        return false
    }

    // Tap to open the menu
    educationLevelButton.tap()

    // Wait for menu to appear and select the option
    let menuItem = app.buttons[level]
    guard menuItem.waitForExistence(timeout: timeout) else {
        XCTFail("Education level option '\(level)' not found in menu")
        return false
    }

    menuItem.tap()

    return true
}
```

#### Task 2: Update `fillDemographicFields` to include education level

```swift
func fillDemographicFields(
    birthYear: String? = nil,
    country: String? = nil,
    region: String? = nil,
    educationLevel: String? = nil  // NEW PARAMETER
) -> Bool {
    if let birthYear {
        guard birthYearTextField.waitForExistence(timeout: timeout) else {
            XCTFail("Birth Year field not found")
            return false
        }
        birthYearTextField.tap()
        birthYearTextField.typeText(birthYear)
    }

    // NEW: Education level handling
    if let educationLevel {
        guard fillEducationLevel(educationLevel) else {
            return false
        }
    }

    if let country {
        guard countryTextField.waitForExistence(timeout: timeout) else {
            XCTFail("Country field not found")
            return false
        }
        countryTextField.tap()
        countryTextField.typeText(country)
    }

    if let region {
        guard regionTextField.waitForExistence(timeout: timeout) else {
            XCTFail("Region field not found")
            return false
        }
        regionTextField.tap()
        regionTextField.typeText(region)
    }

    return true
}
```

#### Task 3: Add test to `RegistrationFlowTests`

```swift
func testEducationLevelPickerSelection() throws {
    // Skip: Requires backend connection
    throw XCTSkip("Example test - requires backend connection")

    // Navigate to registration
    registrationHelper.navigateToRegistration()

    // Scroll down to see education level picker
    let scrollView = app.scrollViews.firstMatch
    scrollView.swipeUp()

    // Verify picker exists
    assertExists(
        registrationHelper.educationLevelButton,
        "Education level picker should exist"
    )

    // Select an education level
    let success = registrationHelper.fillEducationLevel("Bachelor's Degree")
    XCTAssertTrue(success, "Should select education level")

    // Verify selection is displayed
    XCTAssertTrue(
        registrationHelper.educationLevelButton.label.contains("Bachelor's Degree"),
        "Selected education level should be displayed"
    )

    takeScreenshot(named: "EducationLevelSelected")
}
```

#### Task 4: Update `completeRegistration` to optionally include education level

```swift
func completeRegistration(
    firstName: String,
    lastName: String,
    email: String,
    password: String,
    confirmPassword: String? = nil,
    includeDemographics: Bool = false,
    educationLevel: String? = nil  // NEW PARAMETER
) -> Bool {
    // Navigate to registration screen
    guard navigateToRegistration() else {
        return false
    }

    // Fill required fields
    let confirmPwd = confirmPassword ?? password
    guard fillRegistrationForm(
        firstName: firstName,
        lastName: lastName,
        email: email,
        password: password,
        confirmPassword: confirmPwd
    ) else {
        return false
    }

    // Fill optional fields if requested
    if includeDemographics {
        fillDemographicFields(
            birthYear: "1990",
            country: "United States",
            region: "California",
            educationLevel: educationLevel  // NEW: Pass through
        )
    }

    // Submit registration
    return submitRegistration()
}
```

---

## Technical Considerations

### Challenge: Testing SwiftUI Menu Components

**Issue:** SwiftUI `Menu` components present differently than standard pickers:
- They appear as buttons that open a popup menu
- Menu items are rendered as separate button elements in the accessibility tree
- Need to wait for menu animation to complete before tapping menu items

**Solution:** The implementation above handles this by:
1. Tapping the menu button to open the menu
2. Waiting for the menu item to appear with `waitForExistence`
3. Tapping the specific menu item

### Accessibility Testing

The current implementation has good accessibility support:
- `accessibilityLabel` provides context: "Education Level, optional, not selected"
- `accessibilityHint` explains interaction: "Double tap to open menu and select your education level"

The test should verify this works as expected.

---

## Acceptance Criteria

### Definition of Done

- [ ] `fillEducationLevel()` method added to `RegistrationHelper`
- [ ] `fillDemographicFields()` updated with `educationLevel` parameter
- [ ] Test `testEducationLevelPickerSelection()` added to `RegistrationFlowTests`
- [ ] Test verifies picker can be opened and selection made
- [ ] Test verifies selected value is displayed correctly
- [ ] Test includes appropriate screenshot capture
- [ ] Test follows existing skip pattern (skipped by default with `XCTSkip`)
- [ ] `completeRegistration()` method updated to support education level
- [ ] All changes follow existing test patterns and conventions
- [ ] Documentation updated if needed

### Success Metrics

- No new test failures introduced
- Education level picker can be successfully automated in UI tests
- Test passes when backend is connected (manual verification)
- Pattern can be reused for other menu-based pickers in the future

---

## Effort Estimate

**Complexity:** Low-Medium
**Estimated Time:** 1-2 hours

**Breakdown:**
- Add `fillEducationLevel()` method: 20 minutes
- Update `fillDemographicFields()`: 10 minutes
- Add test case: 30 minutes
- Update `completeRegistration()`: 10 minutes
- Testing and verification: 20-30 minutes
- Documentation: 10 minutes

**Risk Factors:**
- SwiftUI Menu behavior may differ across iOS versions
- Menu animation timing might need adjustment
- May discover accessibility issues in production code

---

## Alternative Considered: Remove the Property

### Why NOT Recommended

**Pros of removing:**
- Eliminates unused code
- Reduces maintenance surface area
- Simple solution

**Cons of removing:**
- Feature exists in production and deserves test coverage
- Creates inconsistency (other optional fields are tested)
- Loses opportunity to catch bugs
- Doesn't align with test-driven development best practices

**Verdict:** Removing is the wrong choice. The feature exists, is user-facing, and collects important research data. It should be tested.

---

## Related Issues

- **ICG-145** (from PLAN-IOS-CODEBASE-GAPS.md): Implement or remove education level picker test
- **ICG-144**: Add accessibility identifiers to registration views (would improve test reliability)
- **BTS-108**: This Jira task

---

## Next Steps

1. **Assign to ios-engineer subagent** for implementation
2. Follow the implementation approach outlined above
3. Test manually with backend connection to verify picker interaction
4. Consider addressing ICG-144 (accessibility identifiers) at the same time for better test reliability
5. Close BTS-108 when complete

---

## References

### Files to Modify
1. `/Users/mattgioe/aiq/ios/AIQUITests/Helpers/RegistrationHelper.swift`
2. `/Users/mattgioe/aiq/ios/AIQUITests/RegistrationFlowTests.swift`

### Files to Reference
1. `/Users/mattgioe/aiq/ios/AIQ/Views/Auth/RegistrationView.swift` (production implementation)
2. `/Users/mattgioe/aiq/ios/AIQ/ViewModels/RegistrationViewModel.swift` (likely contains EducationLevel enum)

### Related Documentation
- PR #397 review comments
- iOS Coding Standards: `/Users/mattgioe/aiq/ios/docs/CODING_STANDARDS.md`
- Gap Analysis: `/Users/mattgioe/aiq/docs/plans/PLAN-IOS-CODEBASE-GAPS.md` (ICG-145)

---

**Analysis Date:** 2026-01-12
**Analyst:** Claude Code (Technical Product Manager)
