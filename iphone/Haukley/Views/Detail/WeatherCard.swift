import SwiftUI

/// "Your weather" on the Haukley Weather title page: the viewer's own forecast beside the
/// national live channel, with a "Change" sheet to pick a city, a ZIP or current location.
struct WeatherCard: View {
    @ObservedObject var store = WeatherStore.shared
    @State private var picking = false

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .firstTextBaseline) {
                Text("Your weather").scaledFont(17, weight: .bold)
                Spacer()
                Button("Change") { picking = true }
                    .scaledFont(14, weight: .semibold)
                    .foregroundStyle(.white)
                    .padding(.horizontal, 12).padding(.vertical, 6)
                    .background(Color(white: 0.22), in: Capsule())
                    .accessibilityLabel("Change weather location")
                    .accessibilityIdentifier("weather.change")
            }
            if let w = store.weather {
                forecast(w)
            } else if let msg = store.message {
                Text(msg).scaledFont(14).foregroundStyle(.secondary)
                    .accessibilityIdentifier("weather.message")
            } else {
                HStack(spacing: 8) { ProgressView(); Text("Loading your forecast…").scaledFont(14) }
                    .foregroundStyle(.secondary)
            }
        }
        .padding(14)
        .background(Color(white: 0.14), in: RoundedRectangle(cornerRadius: 12))
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("weather.card")
        .task { await store.refresh() }
        .sheet(isPresented: $picking) { LocationPicker() }
    }

    @ViewBuilder private func forecast(_ w: LocalWeather) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Label(w.place.name, systemImage: w.place.source == "gps" ? "location.fill" : "mappin.and.ellipse")
                .scaledFont(15, weight: .semibold)
                .accessibilityIdentifier("weather.place")
            HStack(alignment: .firstTextBaseline, spacing: 10) {
                if let t = w.now.temp {
                    Text("\(t)°").scaledFont(40, weight: .bold).accessibilityLabel("\(t) degrees")
                }
                VStack(alignment: .leading, spacing: 2) {
                    if let text = w.now.text { Text(text).scaledFont(15) }
                    if let wind = w.now.wind, !wind.isEmpty {
                        Text("Wind \(wind)").scaledFont(13).foregroundStyle(.secondary)
                    }
                }
            }
        }
        ForEach(w.alerts) { a in
            Label(a.headline ?? a.event, systemImage: "exclamationmark.triangle.fill")
                .scaledFont(13, weight: .semibold)
                .foregroundStyle(.white)
                .padding(8)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Color.live, in: RoundedRectangle(cornerRadius: 8))
        }
        if !w.periods.isEmpty {
            // A grid, not a sideways scroll: a tile cut off at the screen edge fails the
            // accessibility audit's contrast check, and every period stays visible.
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 96), spacing: 8)], spacing: 8) {
                ForEach(w.periods.prefix(6)) { p in
                    VStack(alignment: .leading, spacing: 3) {
                        Text(p.name).scaledFont(12, weight: .bold).lineLimit(2)
                        if let t = p.temp { Text("\(t)°").scaledFont(20, weight: .semibold) }
                        if let text = p.text { Text(text).scaledFont(12).lineLimit(2) }
                    }
                    .foregroundStyle(.white)
                    .frame(maxWidth: .infinity, minHeight: 72, alignment: .topLeading)
                    .padding(10)
                    .background(Color(white: 0.2), in: RoundedRectangle(cornerRadius: 8))
                    .accessibilityElement(children: .combine)
                }
            }
        }
        if let a = w.attribution {
            Text(a).scaledFont(11).foregroundStyle(Color(white: 0.7))
        }
    }
}

/// Pick where "Your weather" is for: automatic, a listed city, a ZIP, or current location.
struct LocationPicker: View {
    @ObservedObject var store = WeatherStore.shared
    @StateObject private var locator = OneShotLocator()
    @Environment(\.dismiss) private var dismiss
    @State private var search = ""
    @State private var zip = ""
    @State private var locating = false

    var body: some View {
        NavigationStack {
            List {
                Section {
                    Button {
                        Task {
                            locating = true
                            let c = await locator.locate()
                            locating = false
                            if let c { store.set(.coordinate(lat: c.latitude, lon: c.longitude)); dismiss() }
                        }
                    } label: {
                        HStack {
                            Label("Use my current location", systemImage: "location.fill")
                            if locating { Spacer(); ProgressView() }
                        }
                    }
                    .accessibilityIdentifier("weather.useLocation")
                    if locator.denied {
                        Text("Location is off for Haukley. Turn it on in Settings, or pick a city below.")
                            .scaledFont(12).foregroundStyle(.secondary)
                    }
                    Button { store.set(.automatic); dismiss() } label: {
                        row("Automatic", detail: "Approximate, from your internet connection", selected: store.location == .automatic)
                    }
                    .accessibilityIdentifier("weather.automatic")
                }
                Section("ZIP code") {
                    HStack {
                        TextField("e.g. 11201", text: $zip)
                            .keyboardType(.numberPad)
                            .accessibilityIdentifier("weather.zip")
                        Button("Use") {
                            if let z = WeatherLocation.validZip(zip) { store.set(.zip(z)); dismiss() }
                        }
                        .disabled(WeatherLocation.validZip(zip) == nil)
                        .accessibilityIdentifier("weather.zip.use")
                    }
                }
                Section("Cities") {
                    ForEach(filtered) { c in
                        Button { store.set(.city(slug: c.slug, name: c.name)); dismiss() } label: {
                            row(c.name, detail: nil, selected: store.location == .city(slug: c.slug, name: c.name))
                        }
                        .accessibilityIdentifier("weather.city.\(c.slug)")
                    }
                    if store.cities.isEmpty {
                        Text("Cities aren’t available right now.").foregroundStyle(.secondary)
                    }
                }
            }
            .searchable(text: $search, prompt: "Search cities")
            .navigationTitle("Weather location")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Done") { dismiss() } } }
            .task { await store.loadCities() }
        }
        .preferredColorScheme(.dark)
    }

    private var filtered: [WeatherCity] {
        let q = search.trimmingCharacters(in: .whitespaces)
        return q.isEmpty ? store.cities : store.cities.filter { $0.name.localizedCaseInsensitiveContains(q) }
    }

    private func row(_ title: String, detail: String?, selected: Bool) -> some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(title).foregroundStyle(.white)
                if let detail { Text(detail).scaledFont(12).foregroundStyle(.secondary) }
            }
            Spacer()
            if selected { Image(systemName: "checkmark").foregroundStyle(Color.brand) }
        }
        .contentShape(Rectangle())
    }
}

/// Small temperature + place chip shown over the Haukley Weather live player.
struct WeatherChip: View {
    @ObservedObject var store = WeatherStore.shared

    var body: some View {
        Group {
            if let w = store.weather, let t = w.now.temp {
                HStack(spacing: 6) {
                    Image(systemName: "thermometer.medium")
                    Text("\(t)°  \(w.place.name)").lineLimit(1)
                }
                .scaledFont(13, weight: .semibold)
                .foregroundStyle(.white)
                .padding(.horizontal, 10).padding(.vertical, 6)
                .background(.black.opacity(0.7), in: Capsule())
                .accessibilityElement(children: .combine)
                .accessibilityLabel("\(t) degrees in \(w.place.name)")
                .accessibilityIdentifier("player.weatherChip")
            }
        }
        .task { await store.refresh() }
    }
}
