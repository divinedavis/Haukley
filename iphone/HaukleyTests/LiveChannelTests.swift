import Foundation
import Testing
@testable import Haukley

/// Live channels (kind "live", e.g. Haukley Weather) in the shared catalog.
@MainActor @Suite struct LiveChannelTests {
    private static func title(_ id: String, kind: String, runtime: String? = "1 hr", badge: String? = nil) throws -> Title {
        let json: [String: Any?] = [
            "id": id, "kind": kind, "title": id, "genre": "Weather", "year": 2026, "rating": "TV-G",
            "tagline": "", "description": "", "credits": "", "runtime": runtime, "seasons": nil,
            "stream": "https://haukley.com/live/weather/index.m3u8", "badge": badge, "heroColor": "#2B1A55",
            "episodes": [], "kids": true, "license": "Public domain", "advisory": nil,
        ]
        let data = try JSONSerialization.data(withJSONObject: json.compactMapValues { $0 })
        return try JSONDecoder().decode(Title.self, from: data)
    }

    @Test func decodesLiveKind() throws {
        let t = try Self.title("haukley-weather", kind: "live", runtime: nil, badge: "Live")
        #expect(t.isLive)
        #expect(!t.isMovie && !t.isShow)
        #expect(t.length == "Live")
    }

    private struct Bundled: Decodable { let titles: [Title]; let rows: [RowSpec] }

    /// The catalog this build ships (Catalog.shared may hold a newer copy from haukley.com).
    private static func bundled() throws -> Bundled {
        let url = try #require(Bundle.main.url(forResource: "catalog", withExtension: "json", subdirectory: "Catalog"))
        return try JSONDecoder().decode(Bundled.self, from: Data(contentsOf: url))
    }

    @Test func bundledCatalogShipsTheWeatherChannel() throws {
        let file = try Self.bundled()
        let t = file.titles.first { $0.id == "haukley-weather" }
        #expect(t?.isLive == true)
        #expect(t?.kids == true)
        #expect(file.rows.first?.ids.contains("haukley-weather") == true)
    }

    @Test func liveIsNotAMovieOrShow() throws {
        let titles = try Self.bundled().titles
        #expect(!titles.filter(\.isMovie).contains { $0.isLive })
        #expect(!titles.filter(\.isShow).contains { $0.isLive })
        #expect(!titles.filter(\.isMovie).isEmpty)
        // Catalog.movies uses the same filter, whichever copy is loaded.
        #expect(!Catalog.shared.movies.contains { $0.isLive })
    }

    @Test func moreLikeThisSkipsLive() throws {
        let live = try Self.title("haukley-weather", kind: "live", runtime: nil)
        let film = try Self.title("metropolis", kind: "movie")
        #expect(Catalog.moreLike(live, in: [live, film]).isEmpty)
        #expect(!Catalog.moreLike(film, in: [live, film]).contains { $0.isLive })
    }

    @Test func watchingLiveRecordsNoProgress() throws {
        let library = Library()
        let live = try Self.title("haukley-weather-test", kind: "live", runtime: nil)
        library.record(live, episode: 0, progress: 0.5)
        #expect(!library.continueWatching.contains { $0.titleId == live.id })
        #expect(!library.recentlyWatched.contains { $0.id == live.id })
    }
}
