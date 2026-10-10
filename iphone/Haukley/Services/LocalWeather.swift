import CoreLocation
import Foundation

// "Your weather" for the Haukley Weather live channel: the channel itself is one national
// stream, so the viewer's own forecast is drawn by the app from haukley.com/api/weather.
//
// Location, most private first: automatic (the server estimates the city from the internet
// connection; nothing is sent), a city picked from the list, a ZIP code, or "Use my current
// location", which asks for When-In-Use permission only when that button is tapped (owner
// rule: no prompts on app entry) and sends coordinates rounded to ~1 km. Nothing is stored
// server side; the choice lives in UserDefaults on this device.

struct LocalWeather: Decodable, Equatable {
    struct Place: Decodable, Equatable { let name: String; let source: String?; let lat: Double?; let lon: Double? }
    struct Now: Decodable, Equatable { let temp: Int?; let unit: String?; let text: String?; let wind: String? }
    struct Period: Decodable, Equatable, Identifiable {
        let name: String; let temp: Int?; let text: String?; let day: Bool?
        var id: String { name }
    }
    struct Alert: Decodable, Equatable, Identifiable {
        let event: String; let headline: String?
        var id: String { event + (headline ?? "") }
    }
    let place: Place
    let now: Now
    let periods: [Period]
    let alerts: [Alert]
    let updated: String?
    let attribution: String?

    private enum CodingKeys: String, CodingKey { case place, now, periods, alerts, updated, attribution }
    init(from d: Decoder) throws {
        let c = try d.container(keyedBy: CodingKeys.self)
        place = try c.decode(Place.self, forKey: .place)
        now = try c.decode(Now.self, forKey: .now)
        periods = try c.decodeIfPresent([Period].self, forKey: .periods) ?? []
        alerts = try c.decodeIfPresent([Alert].self, forKey: .alerts) ?? []
        updated = try c.decodeIfPresent(String.self, forKey: .updated)
        attribution = try c.decodeIfPresent(String.self, forKey: .attribution)
    }
}

struct WeatherCity: Decodable, Equatable, Identifiable, Hashable {
    let slug: String
    let name: String
    var id: String { slug }
}

/// Where the viewer wants weather for. Saved on the device only.
enum WeatherLocation: Codable, Equatable {
    case automatic
    case city(slug: String, name: String)
    case zip(String)
    case coordinate(lat: Double, lon: Double)

    static let defaultsKey = "haukley.weather.location.v1"

    static func load(_ defaults: UserDefaults = .standard) -> WeatherLocation {
        guard let data = defaults.data(forKey: defaultsKey),
              let loc = try? JSONDecoder().decode(WeatherLocation.self, from: data) else { return .automatic }
        return loc
    }

    func save(_ defaults: UserDefaults = .standard) {
        if let data = try? JSONEncoder().encode(self) { defaults.set(data, forKey: Self.defaultsKey) }
    }

    /// A ZIP the API can use: exactly five digits.
    static func validZip(_ text: String) -> String? {
        let z = text.trimmingCharacters(in: .whitespacesAndNewlines)
        return z.count == 5 && z.allSatisfy(\.isNumber) ? z : nil
    }

    /// Short label for the chip and the card ("Near you" until the server names the place).
    var label: String {
        switch self {
        case .automatic: return "Near you"
        case .city(_, let name): return name
        case .zip(let z): return "ZIP \(z)"
        case .coordinate: return "Current location"
        }
    }
}

enum WeatherAPI {
    static let base = URL(string: "https://haukley.com/api/weather/")!

    static func localURL(for location: WeatherLocation, base: URL = base) -> URL {
        var c = URLComponents(url: base.appendingPathComponent("local"), resolvingAgainstBaseURL: false)!
        switch location {
        case .automatic: break
        case .city(let slug, _): c.queryItems = [URLQueryItem(name: "city", value: slug)]
        case .zip(let z): c.queryItems = [URLQueryItem(name: "zip", value: z)]
        case .coordinate(let lat, let lon):
            // ~1 km is plenty for a forecast and keeps the request from pinpointing a home.
            c.queryItems = [URLQueryItem(name: "lat", value: String(format: "%.2f", lat)),
                            URLQueryItem(name: "lon", value: String(format: "%.2f", lon))]
        }
        return c.url!
    }

    static func citiesURL(base: URL = base) -> URL { base.appendingPathComponent("cities") }

    enum Failure: Error, Equatable { case unknownLocation, unavailable }

    /// UI tests run with -uitest-weather-stub so they never need the network.
    static var stubbed: Bool { ProcessInfo.processInfo.arguments.contains("-uitest-weather-stub") }

    static let stubJSON = """
    {"place":{"name":"Brooklyn, NY","source":"ip","lat":40.68,"lon":-73.94},
     "now":{"temp":64,"unit":"F","text":"Partly Cloudy","wind":"W 8 mph"},
     "periods":[{"name":"Tonight","temp":55,"text":"Mostly Clear","day":false},
                {"name":"Saturday","temp":68,"text":"Sunny","day":true},
                {"name":"Saturday Night","temp":57,"text":"Partly Cloudy","day":false}],
     "alerts":[],"updated":"2026-10-10T18:00:00Z","attribution":"Data: NOAA / National Weather Service"}
    """
    static let stubCities: [WeatherCity] = [
        WeatherCity(slug: "new-york", name: "New York, NY"), WeatherCity(slug: "los-angeles", name: "Los Angeles, CA"),
        WeatherCity(slug: "chicago", name: "Chicago, IL"), WeatherCity(slug: "atlanta", name: "Atlanta, GA"),
    ]

    static func decode(_ data: Data, status: Int) throws -> LocalWeather {
        switch status {
        case 200: return try JSONDecoder().decode(LocalWeather.self, from: data)
        case 422: throw Failure.unknownLocation
        default: throw Failure.unavailable
        }
    }

    static func fetch(_ location: WeatherLocation) async throws -> LocalWeather {
        if stubbed { return try decode(Data(stubJSON.utf8), status: 200) }
        var req = URLRequest(url: localURL(for: location), timeoutInterval: 15)
        req.cachePolicy = .reloadIgnoringLocalCacheData
        let (data, resp) = try await URLSession.shared.data(for: req)
        return try decode(data, status: (resp as? HTTPURLResponse)?.statusCode ?? 0)
    }

    static func cities() async -> [WeatherCity] {
        if stubbed { return stubCities }
        struct List: Decodable { let cities: [WeatherCity] }
        guard let (data, resp) = try? await URLSession.shared.data(from: citiesURL()),
              (resp as? HTTPURLResponse)?.statusCode == 200,
              let list = try? JSONDecoder().decode(List.self, from: data) else { return [] }
        return list.cities
    }
}

@MainActor
final class WeatherStore: ObservableObject {
    static let shared = WeatherStore()

    @Published private(set) var location: WeatherLocation
    @Published private(set) var weather: LocalWeather?
    @Published private(set) var message: String?
    @Published private(set) var loading = false
    @Published private(set) var cities: [WeatherCity] = []
    private var loadedAt: Date?

    init(defaults: UserDefaults = .standard) {
        location = ProcessInfo.processInfo.arguments.contains("-uitest-reset") ? .automatic : WeatherLocation.load(defaults)
    }

    /// Fetch unless a fresh (10 min) forecast for this location is already on screen.
    func refresh(force: Bool = false) async {
        if !force, weather != nil, let at = loadedAt, Date().timeIntervalSince(at) < 600 { return }
        loading = true
        defer { loading = false }
        do {
            weather = try await WeatherAPI.fetch(location)
            message = nil
            loadedAt = Date()
        } catch WeatherAPI.Failure.unknownLocation {
            weather = nil
            message = "We couldn’t find weather for that place. Pick a city or try another ZIP code."
        } catch {
            weather = nil
            message = "Local weather isn’t available right now."
        }
    }

    func set(_ new: WeatherLocation) {
        location = new
        new.save()
        weather = nil
        loadedAt = nil
        Task { await refresh(force: true) }
    }

    func loadCities() async {
        if cities.isEmpty { cities = await WeatherAPI.cities() }
    }
}

/// Asks for When-In-Use location only when the viewer taps "Use my current location".
@MainActor
final class OneShotLocator: NSObject, ObservableObject, CLLocationManagerDelegate {
    private let manager = CLLocationManager()
    private var continuation: CheckedContinuation<CLLocationCoordinate2D?, Never>?
    @Published private(set) var denied = false

    override init() {
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyKilometer
    }

    func locate() async -> CLLocationCoordinate2D? {
        continuation?.resume(returning: nil)
        return await withCheckedContinuation { c in
            continuation = c
            switch manager.authorizationStatus {
            case .notDetermined: manager.requestWhenInUseAuthorization()
            case .authorizedWhenInUse, .authorizedAlways: manager.requestLocation()
            default: denied = true; finish(nil)
            }
        }
    }

    private func finish(_ c: CLLocationCoordinate2D?) {
        continuation?.resume(returning: c)
        continuation = nil
    }

    nonisolated func locationManagerDidChangeAuthorization(_ m: CLLocationManager) {
        Task { @MainActor in
            guard continuation != nil else { return }
            switch m.authorizationStatus {
            case .authorizedWhenInUse, .authorizedAlways: m.requestLocation()
            case .notDetermined: break
            default: denied = true; finish(nil)
            }
        }
    }

    nonisolated func locationManager(_ m: CLLocationManager, didUpdateLocations locs: [CLLocation]) {
        let c = locs.last?.coordinate
        Task { @MainActor in finish(c) }
    }

    nonisolated func locationManager(_ m: CLLocationManager, didFailWithError error: Error) {
        Task { @MainActor in finish(nil) }
    }
}
