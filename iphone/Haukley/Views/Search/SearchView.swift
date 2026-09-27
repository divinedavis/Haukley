import SwiftUI

struct SearchView: View {
    @EnvironmentObject private var router: Router
    @EnvironmentObject private var library: Library
    @State private var query = ""
    @Environment(\.horizontalSizeClass) private var sizeClass

    private var results: [Title] {
        let all = Catalog.shared.titles.filter(library.allows)
        let q = query.trimmingCharacters(in: .whitespaces)
        guard !q.isEmpty else {
            let lead = Catalog.shared.featured.filter(library.allows)
            return lead + all.filter { !lead.contains($0) }
        }
        return all.filter {
            $0.title.localizedCaseInsensitiveContains(q) || $0.genre.localizedCaseInsensitiveContains(q)
                || $0.credits.localizedCaseInsensitiveContains(q)
        }
    }

    var body: some View {
        NavigationStack {
            Group {
                if sizeClass == .regular { grid } else { list }
            }
            .background(Color.black)
            .navigationTitle("Search")
            // Always show the field (iPad otherwise collapses it into a toolbar button).
            .searchable(text: $query, placement: .navigationBarDrawer(displayMode: .always),
                        prompt: "Search shows, movies, genres…")
        }
    }

    /// iPad: a grid of wide cards, like Netflix's iPad search.
    private var grid: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                Text(query.isEmpty ? "Recommended TV Shows & Movies" : "Top Results")
                    .font(.system(size: 22, weight: .bold))
                LazyVGrid(columns: [GridItem(.adaptive(minimum: 240), spacing: 12)], spacing: 16) {
                    ForEach(results) { t in
                        Button { router.detail = t } label: {
                            VStack(alignment: .leading, spacing: 6) {
                                BundleImage(url: t.card)
                                    .aspectRatio(16 / 9, contentMode: .fill)
                                    .clipShape(RoundedRectangle(cornerRadius: 6))
                                Text(t.title).font(.system(size: 15, weight: .semibold)).lineLimit(1)
                            }
                            .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                        .accessibilityIdentifier("search.result.\(t.id)")
                    }
                }
                if results.isEmpty {
                    Text("No matches for “\(query)”. Try a title, genre or actor.").foregroundStyle(.secondary)
                }
            }
            .padding(.horizontal, 32)
            .padding(.bottom, 40)
        }
    }

    private var list: some View {
            List {
                Section {
                    ForEach(results) { t in
                        Button { router.detail = t } label: {
                            HStack(spacing: 12) {
                                BundleImage(url: t.card)
                                    .frame(width: 136, height: 76)
                                    .clipShape(RoundedRectangle(cornerRadius: 4))
                                Text(t.title).font(.system(size: 15, weight: .semibold)).lineLimit(2)
                                Spacer(minLength: 0)
                                Image(systemName: "play.circle").font(.system(size: 28, weight: .light))
                            }
                            .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                        .listRowInsets(EdgeInsets(top: 3, leading: 0, bottom: 3, trailing: 16))
                        .listRowBackground(Color(white: 0.1))
                        .accessibilityIdentifier("search.result.\(t.id)")
                    }
                } header: {
                    Text(query.isEmpty ? "Recommended TV Shows & Movies" : "Top Results")
                        .font(.system(size: 19, weight: .bold)).foregroundStyle(.white).textCase(nil)
                }
                if results.isEmpty {
                    Text("No matches for “\(query)”. Try a title, genre or actor.")
                        .foregroundStyle(.secondary).listRowBackground(Color.black)
                }
            }
            .listStyle(.plain)
            .scrollContentBackground(.hidden)
    }
}
