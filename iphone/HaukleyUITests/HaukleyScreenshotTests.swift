import XCTest

/// Raw App Store screenshots. Skipped unless the runner gets SCREENSHOT_DIR, e.g.
///   TEST_RUNNER_SCREENSHOT_DIR=/tmp/shots xcodebuild test -only-testing:HaukleyUITests/HaukleyScreenshotTests …
/// The PNGs feed scripts/make_pinterest_screenshots.py.
final class HaukleyScreenshotTests: XCTestCase {
    private var app: XCUIApplication!
    private var dir: URL!

    override func setUpWithError() throws {
        guard let path = ProcessInfo.processInfo.environment["SCREENSHOT_DIR"], !path.isEmpty else {
            throw XCTSkip("SCREENSHOT_DIR not set")
        }
        dir = URL(fileURLWithPath: path)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        continueAfterFailure = false
        XCUIDevice.shared.orientation = .portrait
        app = XCUIApplication()
        app.launchArguments = ["-uitest-reset"]
        app.launch()
        let splash = app.descendants(matching: .any).matching(identifier: "splash").firstMatch
        expectation(for: NSPredicate(format: "exists == false"), evaluatedWith: splash)
        waitForExpectations(timeout: 20)
    }

    private func element(_ id: String) -> XCUIElement {
        app.descendants(matching: .any).matching(identifier: id).firstMatch
    }

    private func save(_ name: String, settle: UInt32 = 3) {
        sleep(settle)  // let posters and video frames load
        let png = XCUIScreen.main.screenshot().pngRepresentation
        try? png.write(to: dir.appendingPathComponent("\(name).png"))
    }

    private func tab(_ name: String) {
        var t = app.tabBars.buttons[name]
        if !t.waitForExistence(timeout: 3) {
            t = app.buttons.matching(NSPredicate(format: "label == %@", name)).firstMatch
        }
        XCTAssertTrue(t.waitForExistence(timeout: 5))
        t.tap()
        if !t.isSelected { t.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap() }
    }

    func testCaptureStoreScreens() {
        // Wait for real content, not a clock: under load the first frames are still blank.
        XCTAssertTrue(element("hero.play").waitForExistence(timeout: 30))
        save("home", settle: 6)

        tab("Search")
        let field = app.searchFields.firstMatch
        XCTAssertTrue(field.waitForExistence(timeout: 5))
        field.tap()
        field.typeText("Keaton")
        app.keyboards.buttons.matching(NSPredicate(format: "label ==[c] 'search'")).firstMatch.tap()
        save("search")

        let result = element("search.result.the-general")
        XCTAssertTrue(result.waitForExistence(timeout: 5))
        result.tap()
        XCTAssertTrue(element("detail.play").waitForExistence(timeout: 12))
        save("detail")
        element("detail.play").tap()
        save("player", settle: 12)
        app.terminate()

        app.launchArguments = []
        app.launch()
        sleep(6)
        tab("Clips")
        save("clips", settle: 6)
        tab("My Haukley")
        save("mine")

        // Last: scrolling Home shrinks the iOS 26 tab bar, which hides the other tabs.
        tab("Home")
        XCTAssertTrue(element("hero.play").waitForExistence(timeout: 15))
        app.swipeUp()
        save("rows")
    }
}
