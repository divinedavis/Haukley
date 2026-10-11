import Foundation
import Testing
@testable import Haukley

/// haukley:// links used by App Store In-App Events.
struct DeepLinkTests {
    private func link(_ s: String) -> DeepLink? { URL(string: s).flatMap(DeepLink.init(url:)) }

    @Test func rowLink() {
        #expect(link("haukley://row/horror") == .row("horror"))
        #expect(link("HAUKLEY://Row/Horror") == .row("horror"))
        #expect(link("haukley://row/silent-comedy/") == .row("silent-comedy"))
    }

    @Test func titleLink() {
        #expect(link("haukley://title/nosferatu") == .title("nosferatu"))
    }

    @Test func unknownOrGarbageIsNil() {
        #expect(link("haukley://player/nosferatu") == nil)
        #expect(link("haukley://row") == nil)
        #expect(link("haukley://row/") == nil)
        #expect(link("https://haukley.com/row/horror") == nil)
        #expect(link("haukley://row/../../etc") == nil)
        #expect(link("haukley://title/a%20b") == nil)
    }

    @MainActor @Test func routerOpensRowAndTitle() {
        let router = Router()
        router.homeReady = true
        let library = Library()
        router.tab = .mine
        router.open(URL(string: "haukley://row/horror")!, library: library)
        #expect(router.tab == .home)
        #expect(router.scrollToRow == (Catalog.shared.rows.contains { $0.key == "horror" } ? "horror" : nil))

        router.open(URL(string: "haukley://row/no-such-row")!, library: library)
        #expect(router.scrollToRow == nil)
        #expect(router.tab == .home)

        if let t = Catalog.shared.titles.first(where: library.allows) {
            router.open(URL(string: "haukley://title/\(t.id)")!, library: library)
            #expect(router.detail?.id == t.id)
        }
        router.open(URL(string: "haukley://title/no-such-title")!, library: library)
        #expect(router.detail == nil)
        #expect(router.tab == .home)
    }
}
