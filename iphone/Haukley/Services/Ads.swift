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

    /// start_playback lives next to log_ad_events in the same API.
    static func startPlaybackURL(from trackingUrl: String) -> URL? {
        guard trackingUrl.hasSuffix("log_ad_events") else { return nil }
        return URL(string: String(trackingUrl.dropLast("log_ad_events".count)) + "start_playback")
    }

    /// The JSON body of one ad event. With a server ticket it carries the signed token and a
    /// per-event seq; without one (the ticket request failed) it is stored but never counted.
    static func eventBody(_ event: Event, titleID: String, episode: Int, session: String,
                          token: String?, seq: Int) -> [String: Any] {
        var body: [String: Any] = ["title_id": titleID, "episode": episode, "platform": "ios",
                                   "event": event.rawValue, "session_id": session]
        if let token { body["token"] = token; body["seq"] = seq }
        return body
    }

    /// One tracker per playback. It asks the server for a signed playback ticket as soon as
    /// the player opens; only events carrying that ticket count toward filmmaker payouts. Each
    /// event gets its own seq, so the one retry can never be counted twice.
    /// Fire-and-forget: tracking must never interrupt playback.
    actor Tracker {
        private struct Ticket: Decodable { let session_id: String; let token: String }
        private let titleID: String
        private let episode: Int
        private let fallbackSession = UUID().uuidString.lowercased()
        private var ticket: Task<Ticket?, Never>?
        private var seq = 0

        init(title: Title, episode: Int) {
            titleID = title.id
            self.episode = episode
        }

        private static func request(_ url: URL, _ body: [String: Any], key: String) -> URLRequest {
            var r = URLRequest(url: url)
            r.httpMethod = "POST"
            r.setValue(key, forHTTPHeaderField: "apikey")
            r.setValue("application/json", forHTTPHeaderField: "Content-Type")
            r.setValue("return=minimal", forHTTPHeaderField: "Prefer")
            r.httpBody = try? JSONSerialization.data(withJSONObject: body)
            return r
        }

        /// Called when the player opens, so the ticket is ready before the first ad.
        func start() {
            guard ticket == nil else { return }
            let titleID = titleID, episode = episode
            ticket = Task {
                guard let config, let url = startPlaybackURL(from: config.trackingUrl) else { return nil }
                let req = Self.request(url, ["title_id": titleID, "episode": episode, "platform": "ios"],
                                       key: config.publishableKey)
                guard let (data, response) = try? await URLSession.shared.data(for: req),
                      let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else { return nil }
                return try? JSONDecoder().decode(Ticket.self, from: data)
            }
        }

        func log(_ event: Event) {
            start()
            seq += 1
            let mySeq = seq, titleID = titleID, episode = episode, fallback = fallbackSession, ticket = ticket
            Task.detached {
                guard let config, let url = URL(string: config.trackingUrl) else { return }
                let t = await ticket?.value
                let req = Tracker.request(url, eventBody(event, titleID: titleID, episode: episode,
                                                         session: t?.session_id ?? fallback,
                                                         token: t?.token, seq: mySeq),
                                          key: config.publishableKey)
                for attempt in 0..<2 {
                    if let (_, response) = try? await URLSession.shared.data(for: req),
                       let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) {
                        return
                    }
                    if attempt == 0 { try? await Task.sleep(for: .seconds(3)) }
                }
            }
        }
    }
}
