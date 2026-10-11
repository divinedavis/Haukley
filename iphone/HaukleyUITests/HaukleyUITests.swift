import XCTest

final class HaukleyUITests: XCTestCase {
    private var app: XCUIApplication!

    override func setUp() {
        continueAfterFailure = false
        app = XCUIApplication()
        // -uitest-weather-stub: Haukley Weather's local forecast comes from a fixture, not the network.
        app.launchArguments = ["-uitest-reset", "-uitest-weather-stub"]
        app.launch()
        // The splash folds away on its own; test the outcome, not the decoration.
        let splash = app.descendants(matching: .any).matching(identifier: "splash").firstMatch
        expectation(for: NSPredicate(format: "exists == false"), evaluatedWith: splash)
        // iPad simulators launch slower (the splash itself is ~4 s), and a loaded Mac can take
        // well over 20 s to get a cold launch past it.
        waitForExpectations(timeout: 40)
    }

    private func element(_ id: String) -> XCUIElement {
        app.descendants(matching: .any).matching(identifier: id).firstMatch
    }

    private func snap(_ name: String) {
        let shot = XCTAttachment(screenshot: app.screenshot())
        shot.name = name
        shot.lifetime = .keepAlways
        add(shot)
    }

    /// iOS 26 tab taps can land on nothing; a coordinate tap + isSelected is the reliable pair.
    private func tapTab(_ name: String) {
        // iPhone: bottom tab bar. iPad: the tabs sit in a floating bar at the top, which isn't
        // always exposed as a tabBar, so fall back to the button with that label.
        var tab = app.tabBars.buttons[name]
        if !tab.waitForExistence(timeout: 3) {
            tab = app.buttons.matching(NSPredicate(format: "label == %@", name)).firstMatch
        }
        XCTAssertTrue(tab.waitForExistence(timeout: 5), "tab \(name) missing")
        for attempt in 0..<3 {
            if tab.isSelected { return }
            if attempt == 0 { tab.tap() } else { tab.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap() }
            let deadline = Date().addingTimeInterval(3)
            while Date() < deadline {
                if tab.isSelected { return }
                RunLoop.current.run(until: Date().addingTimeInterval(0.2))
            }
        }
        XCTFail("tab \(name) never became selected")
    }

    /// In-App Event deep link: haukley://row/horror lands on Home with Classic Horror on screen.
    func testRowDeepLinkScrollsToClassicHorror() {
        XCTAssertTrue(element("hero.play").waitForExistence(timeout: 5))
        tapTab("My Haukley")
        XCUIDevice.shared.system.open(URL(string: "haukley://row/horror")!)
        // A link to the app's own scheme can raise SpringBoard's "Open in Haukley?" confirmation.
        let springboard = XCUIApplication(bundleIdentifier: "com.apple.springboard")
        let openButton = springboard.buttons["Open"]
        if openButton.waitForExistence(timeout: 3) { openButton.tap() }
        let row = app.staticTexts["Classic Horror"]
        XCTAssertTrue(row.waitForExistence(timeout: 10), "Classic Horror row not found")
        let deadline = Date().addingTimeInterval(5)
        while !row.isHittable && Date() < deadline { RunLoop.current.run(until: Date().addingTimeInterval(0.2)) }
        XCTAssertTrue(row.isHittable, "Classic Horror row not scrolled on screen")
        XCTAssertTrue(app.tabBars.buttons["Home"].exists ? app.tabBars.buttons["Home"].isSelected : true)
        snap("deeplink-row-horror")
    }

    /// Same link from a cold start (app not running): the splash folds away onto Classic Horror.
    func testRowDeepLinkColdLaunch() {
        app.terminate()
        XCUIDevice.shared.system.open(URL(string: "haukley://row/horror")!)
        let springboard = XCUIApplication(bundleIdentifier: "com.apple.springboard")
        let openButton = springboard.buttons["Open"]
        if openButton.waitForExistence(timeout: 5) { openButton.tap() }
        XCTAssertTrue(app.wait(for: .runningForeground, timeout: 15))
        let row = app.staticTexts["Classic Horror"]
        XCTAssertTrue(row.waitForExistence(timeout: 40), "Classic Horror row not found after cold launch")
        let deadline = Date().addingTimeInterval(8)
        while !row.isHittable && Date() < deadline { RunLoop.current.run(until: Date().addingTimeInterval(0.2)) }
        XCTAssertTrue(row.isHittable, "Classic Horror row not scrolled on screen after cold launch")
        snap("deeplink-row-horror-cold")
    }

    // No prompt, sheet or alert between launch and the Home screen (see feedback: no unsolicited prompts).
    func testLaunchLandsOnHomeWithNoPrompt() {
        XCTAssertTrue(element("hero.play").waitForExistence(timeout: 5))
        XCTAssertTrue(element("hero.play").isHittable)
        XCTAssertEqual(app.alerts.count, 0)
        XCTAssertEqual(app.sheets.count, 0)
        snap("home")
    }

    func testMyListFromHeroShowsInMyHaukley() {
        tapTab("My Haukley")
        XCTAssertTrue(element("mine.mylist.empty").waitForExistence(timeout: 5))
        tapTab("Home")
        element("hero.mylist").tap()
        tapTab("My Haukley")
        XCTAssertTrue(element("mine.mylist").waitForExistence(timeout: 5))
        XCTAssertFalse(element("mine.mylist.empty").exists)
        snap("my-haukley")
    }

    /// Any poster in Home's rows opens that title's sheet (ids "poster.<title id>").
    func testPosterInARowOpensDetail() {
        let poster = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'poster.'")).firstMatch
        for _ in 0..<4 where !poster.isHittable { app.swipeUp() }
        XCTAssertTrue(poster.waitForExistence(timeout: 5), "no poster rows on Home")
        let name = poster.label
        poster.tap()
        let title = element("detail.title")
        XCTAssertTrue(title.waitForExistence(timeout: 8))
        // The poster speaks the title (initialisms spaced out: "D O A" for "D.O.A.").
        let spoken = title.label.replacingOccurrences(of: ".", with: " ").trimmingCharacters(in: .whitespaces)
        XCTAssertTrue(title.label == name || spoken == name, "opened \(title.label), tapped \(name)")
        element("detail.close").tap()
    }

    func testDetailSheetOpensAndCloses() {
        element("hero.poster").tap()
        let title = element("detail.title")
        XCTAssertTrue(title.waitForExistence(timeout: 5))
        XCTAssertTrue(element("detail.play").exists)
        snap("detail")
        element("detail.close").tap()
        XCTAssertTrue(element("hero.play").waitForExistence(timeout: 5))
    }

    /// iOS 26 floats the search tab as its own button beside the tab bar, not inside it.
    /// Tap until the field really holds keyboard focus (iPad drops it after menus and Clear).
    private func focus(_ field: XCUIElement) {
        for _ in 0..<3 where (field.value(forKey: "hasKeyboardFocus") as? Bool) != true {
            field.tap()
            sleep(1)
        }
    }

    private func openSearch() -> XCUIElement {
        let button = app.buttons.matching(NSPredicate(format: "label == 'Search'")).firstMatch
        XCTAssertTrue(button.waitForExistence(timeout: 5), "search tab missing")
        let field = app.searchFields.firstMatch
        for attempt in 0..<3 where !field.exists {
            if attempt == 0 { button.tap() } else { button.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap() }
            _ = field.waitForExistence(timeout: 3)
        }
        return field
    }

    func testSearchOpensFilmDetail() {
        let field = openSearch()
        XCTAssertTrue(field.waitForExistence(timeout: 5))
        field.tap()
        field.typeText("Nosferatu")
        let result = element("search.result.nosferatu")
        XCTAssertTrue(result.waitForExistence(timeout: 5))
        snap("search")
        // Under load (several simulators at once) the sheet can take longer than 5 s to appear.
        result.tap()
        XCTAssertTrue(element("detail.play").waitForExistence(timeout: 12))
        // Every title page carries its rights line (Creative Commons titles require attribution).
        XCTAssertTrue(element("detail.license").exists)
        snap("film-detail")
    }

    func testSeriesDetailListsItsEpisodes() {
        let field = openSearch()
        XCTAssertTrue(field.waitForExistence(timeout: 5))
        focus(field)
        field.typeText("Sherlock Holmes")
        let result = element("search.result.sherlock-holmes-1954")
        XCTAssertTrue(result.waitForExistence(timeout: 5))
        result.tap()
        XCTAssertTrue(element("detail.play").waitForExistence(timeout: 12))
        XCTAssertTrue(app.staticTexts["Episodes"].waitForExistence(timeout: 5))
        let first = app.staticTexts.matching(NSPredicate(format: "label CONTAINS 'The Case of the Cunningham Heritage'")).firstMatch
        XCTAssertTrue(first.exists, "first real episode title")
        snap("series-detail")
    }

    func testTitleWithAdvisoryShowsIt() {
        let field = openSearch()
        XCTAssertTrue(field.waitForExistence(timeout: 5))
        focus(field)
        field.typeText("Blood of Jesus")
        let result = element("search.result.the-blood-of-jesus")
        XCTAssertTrue(result.waitForExistence(timeout: 5))
        result.tap()
        XCTAssertTrue(element("detail.play").waitForExistence(timeout: 12))
        XCTAssertTrue(element("detail.advisory").exists, "content advisory on the title page")
        snap("advisory-detail")
    }

    func testKidsProfileOnlyShowsFamilyTitles() {
        tapTab("My Haukley")
        let profile = element("mine.profile")
        XCTAssertTrue(profile.waitForExistence(timeout: 5))
        profile.tap()
        let kids = app.buttons["Kids"]
        XCTAssertTrue(kids.waitForExistence(timeout: 5))
        kids.tap()
        // Confirm the switch took before searching (the menu tap can lag under load).
        let switched = NSPredicate(format: "label CONTAINS 'Kids'")
        expectation(for: switched, evaluatedWith: profile)
        waitForExpectations(timeout: 10)
        let field = openSearch()
        XCTAssertTrue(field.waitForExistence(timeout: 5))
        focus(field)
        field.typeText("Nosferatu")
        XCTAssertFalse(element("search.result.nosferatu").waitForExistence(timeout: 3), "Kids profile must not see horror")
        field.buttons["Clear text"].firstMatch.tap()
        // On iPad, Clear text also drops keyboard focus.
        focus(field)
        field.typeText("The General")
        XCTAssertTrue(element("search.result.the-general").waitForExistence(timeout: 5))
        snap("kids-search")
    }

    func testClipsFeedAppears() {
        tapTab("Clips")
        XCTAssertTrue(element("clips.feed").waitForExistence(timeout: 5))
        // The film is letterboxed (aspect fit), not cropped to fill the portrait page.
        let video = element("clip.video")
        XCTAssertTrue(video.waitForExistence(timeout: 5))
        XCTAssertEqual(video.value as? String, "fit")
        sleep(2)
        snap("clips")
    }

    func testFilterChipNarrowsHome() {
        element("chip.movies").tap()
        XCTAssertTrue(app.staticTexts["Movies"].waitForExistence(timeout: 3))
        XCTAssertTrue(element("chip.clear").exists)
        snap("home-movies")
        element("chip.clear").tap()
        XCTAssertFalse(element("chip.clear").waitForExistence(timeout: 2))
        XCTAssertTrue(element("chip.movies").exists)
    }

    /// The Live TV row leads Home; the weather channel's page offers "Watch Live" and plays.
    func testLiveTVRowOpensWeatherChannel() {
        // The row sits under the tall hero card on iPhone: scroll it into view first.
        XCTAssertTrue(element("hero.play").waitForExistence(timeout: 8))
        let tile = element("poster.haukley-weather")
        for _ in 0..<5 where !(tile.exists && tile.isHittable) { app.swipeUp() }
        XCTAssertTrue(tile.waitForExistence(timeout: 5), "Live TV row missing")
        XCTAssertTrue(app.staticTexts["Live TV"].exists, "Live TV row header missing")
        snap("home-live-row")
        tile.tap()
        let play = element("detail.play")
        XCTAssertTrue(play.waitForExistence(timeout: 12))
        XCTAssertEqual(play.label, "Watch Live")
        XCTAssertTrue(element("detail.live").exists, "LIVE badge on the channel page")
        let card = element("weather.card")
        for _ in 0..<3 where !card.exists { app.swipeUp() }
        XCTAssertTrue(card.waitForExistence(timeout: 8), "Your weather card on the channel page")
        XCTAssertTrue(element("weather.place").waitForExistence(timeout: 8), "forecast place shown")
        snap("weather-card")
        element("weather.change").tap()
        XCTAssertTrue(element("weather.useLocation").waitForExistence(timeout: 5), "location sheet opens")
        XCTAssertTrue(element("weather.city.chicago").waitForExistence(timeout: 5), "city list shown")
        snap("weather-location-sheet")
        element("weather.city.chicago").tap()
        XCTAssertTrue(element("weather.card").waitForExistence(timeout: 5))
        for _ in 0..<3 where !play.isHittable { app.swipeDown() }
        play.tap()
        XCTAssertTrue(element("player.live").waitForExistence(timeout: 15), "LIVE tag in the player")
        XCTAssertTrue(element("player.weatherChip").waitForExistence(timeout: 8), "local temperature chip over the player")
        sleep(8)
        snap("live-player")
        element("player.close").tap()
    }

    func testPlayerOpensAndCloses() {
        let play = element("hero.play")
        XCTAssertTrue(play.waitForExistence(timeout: 8))
        // Let the home screen settle (hero fade-in) so the tap isn't swallowed mid-animation.
        let settled = NSPredicate(format: "isHittable == true")
        expectation(for: settled, evaluatedWith: play)
        waitForExpectations(timeout: 8)
        sleep(1)
        play.tap()
        let close = element("player.close")
        XCTAssertTrue(close.waitForExistence(timeout: 8))
        sleep(6)
        snap("player")
        close.tap()
        XCTAssertTrue(element("hero.play").waitForExistence(timeout: 8))
    }

    // iPad only: the app must fill the screen and work in both orientations (Netflix-style
    // billboard, top tab bar), not run as a stretched phone window.
    func testIPadLayoutInBothOrientations() throws {
        try XCTSkipUnless(UIDevice.current.userInterfaceIdiom == .pad, "iPad only")
        XCUIDevice.shared.orientation = .portrait
        XCTAssertTrue(element("hero.play").waitForExistence(timeout: 8))
        let window = app.windows.firstMatch.frame
        let screen = app.frame
        XCTAssertGreaterThan(window.width, screen.width * 0.9, "app should fill the iPad screen")
        snap("ipad-portrait")
        XCUIDevice.shared.orientation = .landscapeLeft
        sleep(2)
        XCTAssertTrue(element("hero.play").exists)
        XCTAssertTrue(element("hero.play").isHittable)
        snap("ipad-landscape")
        element("hero.poster").tap()
        XCTAssertTrue(element("detail.play").waitForExistence(timeout: 5))
        snap("ipad-detail")
        element("detail.close").tap()
        XCUIDevice.shared.orientation = .portrait
    }
}
