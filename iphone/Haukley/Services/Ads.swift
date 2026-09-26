import Foundation

/// Ad tag + per-film ad tracking, shared with the TV apps through Catalog/ads.json.
enum Ads {
    private struct Config: Codable {
        let adTagTemplate: String
        let trackingUrl: String
        let publishableKey: String
    }

    private static let config: Config? = {
        let cached = CatalogSync.dir.appendingPathComponent("ads.json")
        guard let url = FileManager.default.fileExists(atPath: cached.path)
                ? cached : Bundle.main.url(forResource: "ads", withExtension: "json", subdirectory: "Catalog"),
              let data = try? Data(contentsOf: url) else { return nil }
        return try? JSONDecoder().decode(Config.self, from: data)
    }()

    /// title_id rides in the ad request so the ad server can report revenue per film.
    static func tag(for t: Title) -> String? {
        guard let template = config?.adTagTemplate else { return nil }
        return template
            .replacingOccurrences(of: "{TITLE_ID}", with: t.id)
            .replacingOccurrences(of: "{KIND}", with: t.kind)
            .replacingOccurrences(of: "{CORRELATOR}", with: String(Int(Date().timeIntervalSince1970 * 1000)))
    }

    enum Event: String { case started = "ad_started", completed = "ad_completed" }

    /// Fire-and-forget with one retry; tracking must never interrupt playback.
    static func log(_ event: Event, title: Title, episode: Int, session: UUID) {
        guard let config, let url = URL(string: config.trackingUrl) else { return }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue(config.publishableKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("return=minimal", forHTTPHeaderField: "Prefer")
        request.httpBody = try? JSONSerialization.data(withJSONObject: [
            "title_id": title.id, "episode": episode, "platform": "ios",
            "event": event.rawValue, "session_id": session.uuidString.lowercased(),
        ])
        Task.detached {
            for attempt in 0..<2 {
                if let (_, response) = try? await URLSession.shared.data(for: request),
                   let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) {
                    return
                }
                if attempt == 0 { try? await Task.sleep(for: .seconds(3)) }
            }
        }
    }
}
