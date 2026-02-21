//
//  AIQUITestsLaunchTests.swift
//  AIQUITests
//
//  Created by Claude Code on 12/24/24.
//

import XCTest

/// Launch tests to verify the app starts correctly
final class AIQUITestsLaunchTests: XCTestCase {
    override static var runsForEachTargetApplicationUIConfiguration: Bool {
        true
    }

    override func setUpWithError() throws {
        continueAfterFailure = false
    }

    /// Test that the app launches successfully
    func testLaunch() {
        let app = XCUIApplication()
        app.launch()

        // Insert steps here to perform after app launch but before taking a screenshot,
        // such as logging into a test account or navigating somewhere in the app

        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = "Launch Screen"
        attachment.lifetime = .keepAlways
        add(attachment)
    }
}
