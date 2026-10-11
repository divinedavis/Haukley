import SwiftUI

enum HomeFilter: String, CaseIterable, Identifiable {
    case shows = "Shows", movies = "Movies", new = "New & Hot"
    var id: String { rawValue }
}

struct HomeView: View {
    @EnvironmentObject private var library: Library
    @EnvironmentObject private var router: Router
    @State private var filter: HomeFilter?
    @Environment(\.horizontalSizeClass) private var sizeClass

    private let catalog = Catalog.shared

    private func keep(_ t: Title) -> Bool {
        guard library.allows(t) else { return false }
        switch filter {
        case .shows: return t.isShow
        case .movies: return t.isMovie
        case .new: return t.badge != nil && !t.isLive
        case nil: return true
        }
    }

    private var hero: Title {
        catalog.featured.first(where: keep) ?? catalog.titles.first(where: keep) ?? catalog.titles.first(where: library.allows) ?? catalog.titles[0]
    }

    /// "#2 in Haukley's Top 10 Picks" when the hero is in a ranked (curated) row.
    private var heroRank: String? {
        for row in catalog.rows where row.type == "ranked" {
            if let i = row.ids.firstIndex(of: hero.id) {
                return "#\(i + 1) in \(row.title)"
            }
        }
        return nil
    }

    /// Only offer filters that match something (no Shows chip until the catalog has series).
    private var filters: [HomeFilter] {
        HomeFilter.allCases.filter { f in
            switch f {
            case .shows: return !catalog.shows.isEmpty
            case .movies: return !catalog.movies.isEmpty
            case .new: return catalog.titles.contains { $0.badge != nil && !$0.isLive }
            }
        }
    }

    var body: some View {
        ScrollViewReader { proxy in
        ScrollView {
            VStack(alignment: .leading, spacing: 26) {
                VStack(alignment: .leading, spacing: 14) {
                    header
                    chips
                }
                HeroCard(title: hero, rank: heroRank)
                    .padding(.horizontal, Metrics(sizeClass).gutter)
                rows
            }
            .padding(.bottom, 40)
        }
        .scrollIndicators(.hidden)
        .onAppear { scrollToLinkedRow(proxy) }
        .onChange(of: router.scrollToRow) { scrollToLinkedRow(proxy) }
        .onChange(of: router.homeReady) { scrollToLinkedRow(proxy) }
        .background(alignment: .top) {
            LinearGradient(colors: [Color(hex: hero.heroColor), Color(hex: hero.heroColor).opacity(0.55), .black],
                           startPoint: .top, endPoint: UnitPoint(x: 0.5, y: 0.62))
                .frame(height: 900)
                .ignoresSafeArea()
                .animation(.easeInOut(duration: 0.5), value: hero.id)
        }
        .background(Color.black)
        }
    }

    /// A haukley://row/<key> link: clear any filter so the row is there, then bring it to the top.
    private func scrollToLinkedRow(_ proxy: ScrollViewProxy) {
        // A cold-launch link arrives while the splash is up; wait for it to finish.
        guard let key = router.scrollToRow, router.homeReady else { return }
        filter = nil
        // Let the filter change lay the rows out before scrolling.
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.35) {
            withAnimation(.snappy) { proxy.scrollTo("row.\(key)", anchor: .top) }
            router.scrollToRow = nil
        }
    }

    private var header: some View {
        HStack(spacing: 8) {
            Image("LogoMark").resizable().scaledToFit().frame(width: 26, height: 26)
            Text(filter?.rawValue ?? "Home")
                .scaledFont(26, weight: .bold)
                .contentTransition(.opacity)
            Spacer()
            Button { router.tab = .mine } label: { ProfileAvatar(profile: library.current, size: 28) }
                // One element: the fixed-size initial inside is artwork, not text to scale.
                .accessibilityElement(children: .ignore)
                .accessibilityLabel("My Haukley")
                .accessibilityAddTraits(.isButton)
        }
        .padding(.horizontal, Metrics(sizeClass).gutter)
        .padding(.top, 6)
    }

    private var chips: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                if filter != nil {
                    Button { withAnimation(.snappy) { filter = nil } } label: {
                        Image(systemName: "xmark").scaledFont(13, weight: .bold)
                            .frame(width: 34, height: 34)
                            .overlay(Circle().stroke(Color.white.opacity(0.45), lineWidth: 1))
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("Clear filter")
                    .accessibilityIdentifier("chip.clear")
                }
                ForEach(filters) { f in
                    if filter == nil || filter == f {
                        Button { withAnimation(.snappy) { filter = f } } label: {
                            Text(f.rawValue)
                                .scaledFont(14, weight: .semibold)
                                .padding(.horizontal, 14).frame(height: 34)
                                // Unselected chips sit over the hero art: a dark fill keeps the label readable.
                                .background(filter == f ? Color.white.opacity(0.22) : Color(white: 0.1), in: Capsule())
                                .overlay(Capsule().stroke(Color.white.opacity(0.45), lineWidth: 1))
                        }
                        .buttonStyle(.plain)
                        .accessibilityIdentifier("chip.\(String(describing: f))")
                    }
                }
            }
            .padding(.horizontal, Metrics(sizeClass).gutter)
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
                Group {
                    if spec.type == "ranked" {
                        Top10Row(title: spec.title, titles: titles)
                    } else {
                        PosterRow(title: spec.title, titles: titles)
                    }
                }
                .id("row.\(spec.key)")
            }
            // A tall "Haukley Picks" row sits after the second row (these films aren't exclusive,
            // so no "Only on Haukley").
            if i == 1 {
                let originals = catalog.featured.filter(keep)
                if !originals.isEmpty { PosterRow(title: "Haukley Picks", titles: originals, tall: true) }
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
    @Environment(\.horizontalSizeClass) private var sizeClass

    var body: some View {
        if sizeClass == .regular { billboard } else { card }
    }

    /// iPad: Netflix's wide billboard — the film's backdrop, title, details and actions on the left.
    private var billboard: some View {
        ZStack(alignment: .bottomLeading) {
            Button { router.detail = title } label: {
                // Fill the card without letting the image's own width widen the page.
                Color.clear
                    .frame(maxWidth: .infinity)
                    .frame(height: 460)
                    .overlay { BundleImage(url: title.backdrop) }
                    .clipped()
            }
            .buttonStyle(.plain)
            .accessibilityLabel("\(title.title), more info")
            .accessibilityIdentifier("hero.poster")
            // Dark enough behind the left-hand text for it to pass contrast over any backdrop.
            LinearGradient(stops: [.init(color: .black.opacity(0.92), location: 0),
                                   .init(color: .black.opacity(0.85), location: 0.55),
                                   .init(color: .black.opacity(0.3), location: 0.8),
                                   .init(color: .clear, location: 1)],
                           startPoint: .leading, endPoint: .trailing)
                .allowsHitTesting(false)
            LinearGradient(colors: [.clear, .black.opacity(0.7)], startPoint: UnitPoint(x: 0.5, y: 0.55), endPoint: .bottom)
                .allowsHitTesting(false)
            VStack(alignment: .leading, spacing: 12) {
                if let rank {
                    HStack(spacing: 6) {
                        Top10Flag()
                        Text(rank).scaledFont(15, weight: .semibold)
                    }
                }
                Text(title.title).scaledFont(44, weight: .heavy).lineLimit(2).minimumScaleFactor(0.7)
                Text("\(title.genre) • \(String(title.year)) • \(title.length)")
                    .scaledFont(15, weight: .semibold).foregroundStyle(.white)
                Text(title.description).scaledFont(16).foregroundStyle(.white).lineLimit(3)
                    .frame(maxWidth: 440, alignment: .leading)
                    // A solid backing: the synopsis spans the bright middle of the backdrop.
                    .padding(.horizontal, 10).padding(.vertical, 8)
                    .background(.black, in: RoundedRectangle(cornerRadius: 8))
                    .padding(.horizontal, -10)
                HStack(spacing: 12) {
                    PillButton(title: "Play", systemImage: "play.fill") {
                        router.play = PlayRequest(title: title, episode: title.isShow ? 1 : nil)
                    }
                    .frame(width: 170)
                    .accessibilityIdentifier("hero.play")
                    PillButton(title: "My List", systemImage: library.isInMyList(title) ? "checkmark" : "plus", primary: false) {
                        withAnimation(.snappy) { library.toggleMyList(title) }
                    }
                    .frame(width: 170)
                    .accessibilityIdentifier("hero.mylist")
                }
                .padding(.top, 4)
            }
            .frame(maxWidth: 520, alignment: .leading)
            .padding(32)
        }
        .frame(height: 460)
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).stroke(Color.white.opacity(0.12), lineWidth: 1))
        .shadow(color: .black.opacity(0.5), radius: 24, y: 12)
    }

    /// iPhone: the tall poster card.
    private var card: some View {
        ZStack(alignment: .bottom) {
            Button { router.detail = title } label: {
                BundleImage(url: title.poster)
                    .aspectRatio(2 / 3, contentMode: .fit)
            }
            .buttonStyle(.plain)
            .accessibilityLabel("\(title.title), more info")
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
                        Text(rank).scaledFont(15, weight: .semibold)
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
