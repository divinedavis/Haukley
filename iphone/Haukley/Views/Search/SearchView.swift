import SwiftUI

struct SearchView: View {
    @EnvironmentObject private var router: Router
    @State private var query = ""

    private var results: [Title] {
        let all = Catalog.shared.titles
        let q = query.trimmingCharacters(in: .whitespaces)
        guard !q.isEmpty else { return Catalog.shared.featured + all.filter { !Catalog.shared.featured.contains($0) } }
        return all.filter {
            $0.title.localizedCaseInsensitiveContains(q) || $0.genre.localizedCaseInsensitiveContains(q)
                || $0.credits.localizedCaseInsensitiveContains(q)
        }
    }

    var body: some View {
        NavigationStack {
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
            .background(Color.black)
            .navigationTitle("Search")
            .searchable(text: $query, prompt: "Search shows, movies, genres…")
        }
    }
}
