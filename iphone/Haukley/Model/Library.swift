import Foundation
import SwiftUI

/// Per-profile state kept on the device: profiles, My List and watch progress.
@MainActor
final class Library: ObservableObject {
    struct Profile: Codable, Hashable, Identifiable {
        let id: UUID
        var name: String
        var color: Int
    }

    struct Watch: Codable, Hashable, Identifiable {
        let titleId: String
        var episode: Int
        var progress: Double
        var date: Date
        var id: String { titleId }
    }

    private struct Store: Codable {
        var profiles: [Profile]
        var currentId: UUID
        var myList: [UUID: [String]]
        var watched: [UUID: [Watch]]
    }

    @Published private var store: Store
    private let key = "haukley.library.v1"

    init() {
        let defaults = UserDefaults.standard
        if ProcessInfo.processInfo.arguments.contains("-uitest-reset") {
            defaults.removeObject(forKey: key)
        }
        if let data = defaults.data(forKey: key), let saved = try? JSONDecoder().decode(Store.self, from: data) {
            store = saved
        } else {
            let you = Profile(id: UUID(), name: "You", color: 0)
            let kids = Profile(id: UUID(), name: "Kids", color: 2)
            // Seed Continue Watching so a fresh install shows the row the way it will look in use.
            let seeded = Catalog.shared.upNext.enumerated().map { i, u in
                Watch(titleId: u.id, episode: u.episode ?? 0, progress: u.progress,
                      date: Date().addingTimeInterval(Double(-i) * 3600))
            }
            store = Store(profiles: [you, kids], currentId: you.id, myList: [:], watched: [you.id: seeded])
        }
    }

    private func save() {
        if let data = try? JSONEncoder().encode(store) {
            UserDefaults.standard.set(data, forKey: key)
        }
    }

    // MARK: Profiles

    var profiles: [Profile] { store.profiles }
    var current: Profile { store.profiles.first { $0.id == store.currentId } ?? store.profiles[0] }

    func select(_ profile: Profile) {
        store.currentId = profile.id
        save()
    }

    func addProfile(named name: String) {
        let trimmed = name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        let profile = Profile(id: UUID(), name: String(trimmed.prefix(20)), color: store.profiles.count % Avatar.colors.count)
        store.profiles.append(profile)
        store.currentId = profile.id
        save()
    }

    // MARK: My List

    var myList: [Title] { Catalog.shared.titles(store.myList[store.currentId] ?? []) }

    func isInMyList(_ t: Title) -> Bool { (store.myList[store.currentId] ?? []).contains(t.id) }

    func toggleMyList(_ t: Title) {
        var list = store.myList[store.currentId] ?? []
        if let i = list.firstIndex(of: t.id) { list.remove(at: i) } else { list.insert(t.id, at: 0) }
        store.myList[store.currentId] = list
        save()
    }

    // MARK: Watching

    /// In progress, most recent first.
    var continueWatching: [Watch] {
        (store.watched[store.currentId] ?? []).filter { $0.progress > 0.01 && $0.progress < 0.95 }
            .sorted { $0.date > $1.date }
    }

    var recentlyWatched: [Title] {
        Catalog.shared.titles((store.watched[store.currentId] ?? []).sorted { $0.date > $1.date }.map(\.titleId))
    }

    func record(_ t: Title, episode: Int, progress: Double) {
        var list = store.watched[store.currentId] ?? []
        list.removeAll { $0.titleId == t.id }
        list.insert(Watch(titleId: t.id, episode: episode, progress: min(max(progress, 0), 1), date: Date()), at: 0)
        store.watched[store.currentId] = Array(list.prefix(30))
        save()
    }
}

enum Avatar {
    static let colors: [Color] = [
        Color(red: 0.55, green: 0.42, blue: 1.0),
        Color(red: 0.95, green: 0.55, blue: 0.2),
        Color(red: 0.2, green: 0.75, blue: 0.55),
        Color(red: 0.9, green: 0.3, blue: 0.45),
    ]
}
