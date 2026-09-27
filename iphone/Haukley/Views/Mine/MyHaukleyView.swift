import SwiftUI

/// Profile switcher (Netflix's "Divine ▾"), My List, Continue Watching and Recently Watched.
struct MyHaukleyView: View {
    @EnvironmentObject private var library: Library
    @State private var addingProfile = false
    @Environment(\.horizontalSizeClass) private var sizeClass
    @State private var newName = ""

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 26) {
                header

                VStack(alignment: .leading, spacing: 8) {
                    Text("My List").font(.system(size: 19, weight: .bold)).padding(.horizontal, 16)
                    if library.myList.isEmpty {
                        Text("Tap + My List on anything you want to watch later and it shows up here.")
                            .font(.system(size: 14)).foregroundStyle(.secondary)
                            .padding(.horizontal, 16)
                            .accessibilityIdentifier("mine.mylist.empty")
                    } else {
                        ScrollView(.horizontal, showsIndicators: false) {
                            LazyHStack(spacing: 8) {
                                ForEach(library.myList) { PosterTile(title: $0, width: Metrics(sizeClass).poster) }
                            }
                            .padding(.horizontal, 16)
                        }
                        .accessibilityIdentifier("mine.mylist")
                    }
                }

                if !library.continueWatching.isEmpty {
                    ContinueRow(title: "Continue Watching", items: library.continueWatching)
                }
                if !library.recentlyWatched.isEmpty {
                    PosterRow(title: "Recently Watched", titles: library.recentlyWatched)
                }
            }
            .padding(.top, 8)
            .padding(.bottom, 40)
        }
        .background(Color.black)
        .alert("Add Profile", isPresented: $addingProfile) {
            TextField("Name", text: $newName)
            Button("Add") { library.addProfile(named: newName); newName = "" }
            Button("Cancel", role: .cancel) { newName = "" }
        }
    }

    private var header: some View {
        HStack(spacing: 10) {
            ProfileAvatar(profile: library.current, size: 34)
            Menu {
                ForEach(library.profiles) { p in
                    Button { library.select(p) } label: {
                        if p.id == library.current.id { Label(p.name, systemImage: "checkmark") } else { Text(p.name) }
                    }
                }
                Divider()
                Button { addingProfile = true } label: { Label("Add Profile", systemImage: "plus") }
            } label: {
                HStack(spacing: 6) {
                    Text(library.current.name).font(.system(size: 28, weight: .bold))
                    Image(systemName: "chevron.down").font(.system(size: 15, weight: .bold))
                }
                .foregroundStyle(.white)
            }
            .accessibilityIdentifier("mine.profile")
            Spacer()
        }
        .padding(.horizontal, 16)
    }
}
