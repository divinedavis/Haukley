import Foundation
import Testing
@testable import Haukley

/// "Your weather" on Haukley Weather: API decoding, the saved location choice, request URLs.
@Suite struct LocalWeatherTests {
    @Test func decodesTheLocalForecast() throws {
        let w = try WeatherAPI.decode(Data(WeatherAPI.stubJSON.utf8), status: 200)
        #expect(w.place.name == "Brooklyn, NY")
        #expect(w.now.temp == 64)
        #expect(w.periods.count == 3)
        #expect(w.alerts.isEmpty)
        #expect(w.attribution?.contains("National Weather Service") == true)
    }

    @Test func toleratesMissingOptionalFields() throws {
        let json = #"{"place":{"name":"Somewhere"},"now":{"temp":null}}"#
        let w = try WeatherAPI.decode(Data(json.utf8), status: 200)
        #expect(w.periods.isEmpty && w.alerts.isEmpty && w.now.temp == nil)
    }

    @Test func mapsErrorStatuses() {
        #expect(throws: WeatherAPI.Failure.unknownLocation) {
            try WeatherAPI.decode(Data(#"{"error":"unknown_location"}"#.utf8), status: 422)
        }
        #expect(throws: WeatherAPI.Failure.unavailable) {
            try WeatherAPI.decode(Data(#"{"error":"unavailable"}"#.utf8), status: 503)
        }
    }

    @Test func buildsRequestURLs() {
        #expect(WeatherAPI.localURL(for: .automatic).absoluteString == "https://haukley.com/api/weather/local")
        #expect(WeatherAPI.localURL(for: .zip("11201")).absoluteString == "https://haukley.com/api/weather/local?zip=11201")
        #expect(WeatherAPI.localURL(for: .city(slug: "new-york", name: "New York, NY")).absoluteString
                == "https://haukley.com/api/weather/local?city=new-york")
        // coordinates are rounded to ~1 km before they leave the phone
        #expect(WeatherAPI.localURL(for: .coordinate(lat: 40.712776, lon: -74.005974)).absoluteString
                == "https://haukley.com/api/weather/local?lat=40.71&lon=-74.01")
        #expect(WeatherAPI.citiesURL().absoluteString == "https://haukley.com/api/weather/cities")
    }

    @Test func savesAndLoadsTheChoice() throws {
        let d = try #require(UserDefaults(suiteName: "LocalWeatherTests.\(UUID().uuidString)"))
        #expect(WeatherLocation.load(d) == .automatic)   // default: IP-based, nothing sent
        for loc: WeatherLocation in [.zip("10001"), .city(slug: "chicago", name: "Chicago, IL"),
                                     .coordinate(lat: 33.75, lon: -84.39), .automatic] {
            loc.save(d)
            #expect(WeatherLocation.load(d) == loc)
        }
    }

    @Test func validatesZips() {
        #expect(WeatherLocation.validZip(" 11201 ") == "11201")
        #expect(WeatherLocation.validZip("1120") == nil)
        #expect(WeatherLocation.validZip("11201-1234") == nil)
        #expect(WeatherLocation.validZip("abcde") == nil)
    }
}
