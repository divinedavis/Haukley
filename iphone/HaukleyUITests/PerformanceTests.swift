import XCTest

/// Speed and memory on the paths people wait on, added 2026-10-07 with Apple's XCTMetric
/// API. scripts/perf_gate.py fails the ship when a metric is more than 1.5x the median of
/// the last five passing ships (scripts/perf_baseline.json). Simulator numbers catch
/// regressions, not real-world times; those come from MetricKit
/// (Services/MetricsReporter.swift) and the Xcode Organizer (scripts/organizer_report.py).
/// iPhone only: ship.sh skips this class on the iPad pass.
final class PerformanceTests: XCTestCase {
    private let args = ["-uitest-reset"]

    private func home(_ app: XCUIApplication) -> XCUIElement {
        app.descendants(matching: .any).matching(identifier: "hero.play").firstMatch
    }

    /// Cold launch to the first frame someone can touch.
    func testLaunch() {
        let opts = XCTMeasureOptions(); opts.iterationCount = 5
        measure(metrics: [XCTApplicationLaunchMetric(waitUntilResponsive: true)], options: opts) {
            let app = XCUIApplication(); app.launchArguments = args
            app.launch()
        }
    }

    /// Launch until Home's Play button is up behind the splash: what people open it for.
    func testLaunchToHome() {
        let app = XCUIApplication(); app.launchArguments = args
        let opts = XCTMeasureOptions(); opts.iterationCount = 5
        measure(metrics: [XCTClockMetric()], options: opts) {
            app.launch()
            XCTAssertTrue(home(app).waitForExistence(timeout: 40))
            app.terminate()
        }
    }

    /// Flinging Home's rows of posters, and the memory the app holds with the art loaded.
    func testHomeScroll() {
        let app = XCUIApplication(); app.launchArguments = args
        app.launch()
        XCTAssertTrue(home(app).waitForExistence(timeout: 40))
        sleep(4)   // splash fade
        let opts = XCTMeasureOptions(); opts.iterationCount = 5
        opts.invocationOptions = [.manuallyStop]
        measure(metrics: [XCTOSSignpostMetric.scrollDecelerationMetric, XCTMemoryMetric(application: app)],
                options: opts) {
            app.swipeUp(velocity: .fast)
            stopMeasuring()
            app.swipeDown(velocity: .fast)
        }
    }
}
