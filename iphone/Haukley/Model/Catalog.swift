import Foundation

struct Episode: Codable, Hashable, Identifiable {
    let number: Int
    let name: String
    let minutes: Int
    let summary: String
    let stream: String
    var id: Int { number }
}

struct Title: Codable, Hashable, Identifiable {
    let id: String
    let kind: String
    let title: String
    let genre: String
    let year: Int
    let rating: String
    let tagline: String
    let description: String
    let credits: String
    let runtime: String?
    let seasons: Int?
    let stream: String
    let badge: String?
    let heroColor: String
    let episodes: [Episode]
    /// Family-friendly: the only titles a Kids profile sees (same flag the web app uses).
    let kids: Bool?

    var isShow: Bool { kind == "show" }
    var length: String {
        if isShow, let seasons { return "\(seasons) Season\(seasons == 1 ? "" : "s")" }
        return runtime ?? ""
    }
    var poster: URL? { Catalog.asset(id, "poster") }
    var card: URL? { Catalog.asset(id, "card") }
    var backdrop: URL? { Catalog.asset(id, "backdrop") }
    func still(_ episode: Int) -> URL? { Catalog.asset(id, "ep\(episode)") }
}

struct RowSpec: Codable {
    let key: String
    let title: String
    let type: String
    let ids: [String]
}

struct UpNextSeed: Codable {
    let id: String
    let label: String
    let progress: Double
    let episode: Int?
}

private struct CatalogFile: Codable {
    let titles: [Title]
    let featured: [String]
    let upNext: [UpNextSeed]
    let rows: [RowSpec]
}

/// The film catalog: the copy refreshed from haukley.com (see CatalogSync) when there is one,
/// otherwise the copy bundled at build time (scripts/make_ios.py). Every platform reads the
/// same haukley.com/watch/catalog/catalog.json, so new films reach the app without an update.
final class Catalog {
    static let shared = Catalog()

    let titles: [Title]
    let featured: [Title]
    let upNext: [UpNextSeed]
    let rows: [RowSpec]
    private let byId: [String: Title]

    private init() {
        let file: CatalogFile
        if let data = try? Data(contentsOf: CatalogSync.dir.appendingPathComponent("catalog.json")),
           let decoded = try? JSONDecoder().decode(CatalogFile.self, from: data), !decoded.titles.isEmpty {
            file = decoded
        } else if let url = Bundle.main.url(forResource: "catalog", withExtension: "json", subdirectory: "Catalog"),
           let data = try? Data(contentsOf: url),
           let decoded = try? JSONDecoder().decode(CatalogFile.self, from: data) {
            file = decoded
        } else {
            assertionFailure("Catalog/catalog.json missing from the bundle")
            file = CatalogFile(titles: [], featured: [], upNext: [], rows: [])
        }
        let lookup = Dictionary(uniqueKeysWithValues: file.titles.map { ($0.id, $0) })
        titles = file.titles
        byId = lookup
        featured = file.featured.compactMap { lookup[$0] }
        upNext = file.upNext
        rows = file.rows
    }

    func title(_ id: String) -> Title? { byId[id] }
    func titles(_ ids: [String]) -> [Title] { ids.compactMap { byId[$0] } }

    var movies: [Title] { titles.filter { !$0.isShow } }
    var shows: [Title] { titles.filter(\.isShow) }

    func moreLike(_ t: Title) -> [Title] {
        titles.filter { $0.id != t.id && $0.kind == t.kind }
            .sorted { ($0.genre == t.genre ? 0 : 1, $0.title) < ($1.genre == t.genre ? 0 : 1, $1.title) }
    }

    static func asset(_ id: String, _ name: String) -> URL? {
        if let bundled = bundledAsset(id, name) { return bundled }
        let cached = CatalogSync.dir.appendingPathComponent("\(id)/\(name).jpg")
        return FileManager.default.fileExists(atPath: cached.path) ? cached : nil
    }

    static func bundledAsset(_ id: String, _ name: String) -> URL? {
        Bundle.main.url(forResource: name, withExtension: "jpg", subdirectory: "Catalog/\(id)")
    }
}

/// Downloads the live catalog, its ad config and any artwork the bundle lacks into Caches.
/// The new catalog is written last and only once every image arrived, and it takes effect
/// on the next launch, so the UI never shows a title without art.
enum CatalogSync {
    static let base = URL(string: "https://haukley.com/watch/catalog/")!
    static var dir: URL {
        FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("Catalog", isDirectory: true)
    }

    static func refresh() async {
        let fm = FileManager.default
        do {
            let (data, resp) = try await URLSession.shared.data(from: base.appendingPathComponent("catalog.json"))
            guard (resp as? HTTPURLResponse)?.statusCode == 200,
                  let file = try? JSONDecoder().decode(CatalogFile.self, from: data), !file.titles.isEmpty else { return }
            for t in file.titles {
                let names = ["poster", "card", "backdrop"] + t.episodes.map { "ep\($0.number)" }
                for name in names where Catalog.bundledAsset(t.id, name) == nil {
                    let dst = dir.appendingPathComponent("\(t.id)/\(name).jpg")
                    if fm.fileExists(atPath: dst.path) { continue }
                    let (img, r) = try await URLSession.shared.data(from: base.appendingPathComponent("\(t.id)/\(name).jpg"))
                    guard (r as? HTTPURLResponse)?.statusCode == 200 else { return } // incomplete: keep the old catalog
                    try fm.createDirectory(at: dst.deletingLastPathComponent(), withIntermediateDirectories: true)
                    try img.write(to: dst, options: .atomic)
                }
            }
            try fm.createDirectory(at: dir, withIntermediateDirectories: true)
            let (ads, r) = try await URLSession.shared.data(from: base.appendingPathComponent("ads.json"))
            if (r as? HTTPURLResponse)?.statusCode == 200 {
                try ads.write(to: dir.appendingPathComponent("ads.json"), options: .atomic)
            }
            try data.write(to: dir.appendingPathComponent("catalog.json"), options: .atomic)
        } catch {
            // Offline or a partial download: the bundled/previous catalog stays in use.
        }
    }
}
