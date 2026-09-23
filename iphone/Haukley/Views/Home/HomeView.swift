import SwiftUI

enum HomeFilter: String, CaseIterable, Identifiable {
    case shows = "Shows", movies = "Movies", new = "New & Hot"
    var id: String { rawValue }
}

struct HomeView: View {
    @EnvironmentObject private var library: Library
    @EnvironmentObject private var router: Router
    @State private var filter: HomeFilter?

    private let catalog = Catalog.shared

    private func keep(_ t: Title) -> Bool {
        switch filter {
        case .shows: return t.isShow
        case .movies: return !t.isShow
        case .new: return t.badge != nil
        case nil: return true
        }
    }

    private var hero: Title {
        catalog.featured.first(where: keep) ?? catalog.titles.first(where: keep) ?? catalog.titles[0]
    }

    /// "#2 in Movies Today" when the hero is in a Top 10 row.
    private var heroRank: String? {
        for row in catalog.rows where row.type == "ranked" {
            if let i = row.ids.firstIndex(of: hero.id) {
                return "#\(i + 1) in \(hero.isShow ? "Shows" : "Movies") Today"
            }
        }
        return nil
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 26) {
                VStack(alignment: .leading, spacing: 14) {
                    header
                    chips
                }
                HeroCard(title: hero, rank: heroRank)
                    .padding(.horizontal, 16)
                rows
            }
            .padding(.bottom, 40)
        }
        .scrollIndicators(.hidden)
        .background(alignment: .top) {
            LinearGradient(colors: [Color(hex: hero.heroColor), Color(hex: hero.heroColor).opacity(0.55), .black],
                           startPoint: .top, endPoint: UnitPoint(x: 0.5, y: 0.62))
                .frame(height: 900)
                .ignoresSafeArea()
                .animation(.easeInOut(duration: 0.5), value: hero.id)
        }
        .background(Color.black)
    }

    private var header: some View {
        HStack(spacing: 8) {
            Image("LogoMark").resizable().scaledToFit().frame(width: 26, height: 26)
            Text(filter?.rawValue ?? "Home")
                .font(.system(size: 26, weight: .bold))
                .contentTransition(.opacity)
            Spacer()
            Button { router.tab = .mine } label: { ProfileAvatar(profile: library.current, size: 28) }
                .accessibilityLabel("My Haukley")
        }
        .padding(.horizontal, 16)
        .padding(.top, 6)
    }

    private var chips: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                if filter != nil {
                    Button { withAnimation(.snappy) { filter = nil } } label: {
                        Image(systemName: "xmark").font(.system(size: 13, weight: .bold))
                            .frame(width: 34, height: 34)
                            .overlay(Circle().stroke(Color.white.opacity(0.45), lineWidth: 1))
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("Clear filter")
                    .accessibilityIdentifier("chip.clear")
                }
                ForEach(HomeFilter.allCases) { f in
                    if filter == nil || filter == f {
                        Button { withAnimation(.snappy) { filter = f } } label: {
                            Text(f.rawValue)
                                .font(.system(size: 14, weight: .semibold))
                                .padding(.horizontal, 14).frame(height: 34)
                                .background(filter == f ? Color.white.opacity(0.22) : .clear, in: Capsule())
                                .overlay(Capsule().stroke(Color.white.opacity(0.45), lineWidth: 1))
                        }
                        .buttonStyle(.plain)
                        .accessibilityIdentifier("chip.\(String(describing: f))")
                    }
                }
            }
            .padding(.horizontal, 16)
        }
    }

    @ViewBuilder private var rows: some View {
        let continuing = library.continueWatching.filter { catalog.title($0.titleId).map(keep) ?? false }
        if !continuing.isEmpty {
            ContinueRow(title: "Continue Watching for \(library.current.name)", items: continuing)
        }
        ForEach(Array(catalog.rows.enumerated()), id: \.element.key) { i, spec in
            let titles = catalog.titles(spec.ids).filter(keep)
            if !titles.isEmpty {
                if spec.type == "ranked" {
                    Top10Row(title: spec.title.replacingOccurrences(of: "Top 10", with: "Top 10") + " in the U.S. Today", titles: titles)
                } else {
                    PosterRow(title: spec.title, titles: titles)
                }
            }
            // "Only on Haukley" sits after the second row, like Netflix's tall originals row.
            if i == 1 {
                let originals = catalog.featured.filter(keep)
                if !originals.isEmpty { PosterRow(title: "Only on Haukley", titles: originals, tall: true) }
            }
        }
        if !library.myList.filter(keep).isEmpty {
            PosterRow(title: "My List", titles: library.myList.filter(keep))
        }
    }
}

struct HeroCard: View {
    let title: Title
    let rank: String?
    @EnvironmentObject private var library: Library
    @EnvironmentObject private var router: Router

    var body: some View {
        ZStack(alignment: .bottom) {
            Button { router.detail = title } label: {
                BundleImage(url: title.poster)
                    .aspectRatio(2 / 3, contentMode: .fit)
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier("hero.poster")
            // Dark enough at the bottom to hide the poster's billing block behind the buttons.
            LinearGradient(stops: [.init(color: .clear, location: 0.5),
                                   .init(color: .black.opacity(0.75), location: 0.78),
                                   .init(color: .black.opacity(0.97), location: 1)],
                           startPoint: .top, endPoint: .bottom)
                .allowsHitTesting(false)
            VStack(spacing: 12) {
                if let rank {
                    HStack(spacing: 6) {
                        Top10Flag()
                        Text(rank).font(.system(size: 15, weight: .semibold))
                    }
                }
                HStack(spacing: 10) {
                    PillButton(title: "Play", systemImage: "play.fill") {
                        router.play = PlayRequest(title: title, episode: title.isShow ? 1 : nil)
                    }
                    .accessibilityIdentifier("hero.play")
                    PillButton(title: "My List", systemImage: library.isInMyList(title) ? "checkmark" : "plus", primary: false) {
                        withAnimation(.snappy) { library.toggleMyList(title) }
                    }
                    .accessibilityIdentifier("hero.mylist")
                }
            }
            .padding(14)
        }
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 12, style: .continuous).stroke(Color.white.opacity(0.12), lineWidth: 1))
        .shadow(color: .black.opacity(0.5), radius: 20, y: 10)
    }
}
