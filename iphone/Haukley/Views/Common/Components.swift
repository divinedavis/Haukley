import SwiftUI
import UIKit

// MARK: Images

/// Bundled JPEGs, decoded once and cached.
enum ImageCache {
    private static let cache = NSCache<NSURL, UIImage>()

    static func image(_ url: URL?) -> UIImage? {
        guard let url else { return nil }
        if let hit = cache.object(forKey: url as NSURL) { return hit }
        guard let img = UIImage(contentsOfFile: url.path) else { return nil }
        cache.setObject(img, forKey: url as NSURL)
        return img
    }
}

struct BundleImage: View {
    let url: URL?
    var body: some View {
        if let img = ImageCache.image(url) {
            Image(uiImage: img).resizable().scaledToFill()
        } else {
            Rectangle().fill(Color(white: 0.12))
        }
    }
}

extension Color {
    init(hex: String) {
        let v = UInt64(hex.trimmingCharacters(in: CharacterSet(charactersIn: "#")), radix: 16) ?? 0
        self.init(red: Double((v >> 16) & 0xFF) / 255, green: Double((v >> 8) & 0xFF) / 255, blue: Double(v & 0xFF) / 255)
    }
    static let brand = Color(red: 0.545, green: 0.424, blue: 1.0)
}

// MARK: Layout

/// Sizes that change between iPhone (compact width) and iPad (regular width), so rows, tiles
/// and margins scale up the way Netflix's iPad app does instead of showing a stretched phone UI.
struct Metrics {
    let wide: Bool
    init(_ sizeClass: UserInterfaceSizeClass?) { wide = sizeClass == .regular }
    var gutter: CGFloat { wide ? 32 : 16 }
    var poster: CGFloat { wide ? 150 : 112 }
    var tallPoster: CGFloat { wide ? 200 : 150 }
    var rankedPoster: CGFloat { wide ? 136 : 104 }
    var rankScale: CGFloat { wide ? 1.3 : 1 }
    var rowTitle: CGFloat { wide ? 24 : 19 }
    var rowSpacing: CGFloat { wide ? 12 : 8 }
}

// MARK: Tiles

/// A 2:3 poster with an optional badge ("New Season", "Recently Added") and Top 10 flag.
struct PosterTile: View {
    let title: Title
    var width: CGFloat = 112
    var top10 = false
    @EnvironmentObject private var router: Router

    var body: some View {
        Button { router.detail = title } label: {
            BundleImage(url: title.poster)
                .frame(width: width, height: width * 1.5)
                .clipShape(RoundedRectangle(cornerRadius: 5, style: .continuous))
                .overlay(alignment: .bottom) {
                    if let badge = title.badge { BadgeLabel(text: badge) }
                }
                .overlay(alignment: .topTrailing) {
                    if top10 { Top10Flag().padding(3) }
                }
        }
        .buttonStyle(.plain)
        .accessibilityLabel(title.title)
        .accessibilityIdentifier("poster.\(title.id)")
    }
}

struct BadgeLabel: View {
    let text: String
    var body: some View {
        Text(text)
            .scaledFont(9, weight: .bold)
            .foregroundStyle(.white)
            .padding(.horizontal, 6).padding(.vertical, 3)
            .background(Color.brand, in: RoundedRectangle(cornerRadius: 2))
            .offset(y: 1)
    }
}

struct Top10Flag: View {
    var body: some View {
        VStack(spacing: -2) {
            Text("TOP").font(.system(size: 6, weight: .heavy))
            Text("10").font(.system(size: 10, weight: .black))
        }
        .foregroundStyle(.white)
        .frame(width: 20, height: 24)
        .background(Color.brand, in: RoundedRectangle(cornerRadius: 2))
        .accessibilityHidden(true)   // fixed-size art; the poster/hero label carries the rank
    }
}

/// The big outlined rank numeral from the Top 10 rows.
struct RankNumeral: View {
    let n: Int
    var body: some View {
        let text = Text("\(n)").font(.system(size: 116, weight: .black, design: .default)).kerning(-8)
        ZStack {
            ForEach(0..<8, id: \.self) { i in
                let a = Double(i) * .pi / 4
                text.foregroundStyle(Color(white: 0.55)).offset(x: cos(a) * 1.6, y: sin(a) * 1.6)
            }
            text.foregroundStyle(.black)
        }
        .fixedSize()
        .accessibilityHidden(true)   // artwork; the poster beside it carries the title
    }
}

// MARK: Rows

struct RowHeader: View {
    let title: String
    @Environment(\.horizontalSizeClass) private var sizeClass
    var body: some View {
        let m = Metrics(sizeClass)
        Text(title)
            .scaledFont(m.rowTitle, weight: .bold)
            .foregroundStyle(.white)
            .padding(.horizontal, m.gutter)
    }
}

struct PosterRow: View {
    let title: String
    let titles: [Title]
    var tall = false
    @Environment(\.horizontalSizeClass) private var sizeClass
    var body: some View {
        let m = Metrics(sizeClass)
        VStack(alignment: .leading, spacing: m.rowSpacing) {
            RowHeader(title: title)
            ScrollView(.horizontal, showsIndicators: false) {
                LazyHStack(spacing: m.rowSpacing) {
                    ForEach(titles) { PosterTile(title: $0, width: tall ? m.tallPoster : m.poster) }
                }
                .padding(.horizontal, m.gutter)
            }
        }
    }
}

struct Top10Row: View {
    let title: String
    let titles: [Title]
    @EnvironmentObject private var router: Router
    @Environment(\.horizontalSizeClass) private var sizeClass
    var body: some View {
        let m = Metrics(sizeClass)
        VStack(alignment: .leading, spacing: m.rowSpacing) {
            RowHeader(title: title)
            ScrollView(.horizontal, showsIndicators: false) {
                LazyHStack(spacing: 4) {
                    ForEach(Array(titles.prefix(10).enumerated()), id: \.element.id) { i, t in
                        HStack(alignment: .bottom, spacing: -22 * m.rankScale) {
                            RankNumeral(n: i + 1).scaleEffect(m.rankScale, anchor: .bottomTrailing)
                                .offset(y: 18 * m.rankScale)
                            PosterTile(title: t, width: m.rankedPoster)
                        }
                        .padding(.trailing, 6 * m.rankScale)
                        .padding(.leading, m.wide ? 20 : 0)
                    }
                }
                .padding(.horizontal, m.gutter)
            }
        }
    }
}

struct ContinueRow: View {
    let title: String
    let items: [Library.Watch]
    @EnvironmentObject private var router: Router
    @Environment(\.horizontalSizeClass) private var sizeClass
    var body: some View {
        let m = Metrics(sizeClass)
        VStack(alignment: .leading, spacing: m.rowSpacing) {
            RowHeader(title: title)
            ScrollView(.horizontal, showsIndicators: false) {
                LazyHStack(spacing: 8) {
                    ForEach(items) { w in
                        if let t = Catalog.shared.title(w.titleId) {
                            VStack(spacing: 0) {
                                Button {
                                    router.play = PlayRequest(title: t, episode: w.episode > 0 ? w.episode : nil)
                                } label: {
                                    BundleImage(url: t.poster)
                                        .frame(width: m.poster, height: m.poster * 1.34)
                                        .clipped()
                                        .overlay {
                                            Image(systemName: "play.fill")
                                                .scaledFont(18)
                                                .foregroundStyle(.white)
                                                .frame(width: 44, height: 44)
                                                .background(.black.opacity(0.55), in: Circle())
                                                .overlay(Circle().stroke(.white, lineWidth: 1.5))
                                        }
                                }
                                .buttonStyle(.plain)
                                .accessibilityIdentifier("continue.\(t.id)")
                                GeometryReader { g in
                                    ZStack(alignment: .leading) {
                                        Rectangle().fill(Color(white: 0.35))
                                        Rectangle().fill(Color.brand).frame(width: g.size.width * w.progress)
                                    }
                                }
                                .frame(height: 3)
                                HStack {
                                    Button { router.detail = t } label: { Image(systemName: "info.circle") }
                                        .accessibilityLabel("Details for \(t.title)")
                                    Spacer()
                                    if w.episode > 0 {
                                        Text("E\(w.episode)").scaledFont(11, weight: .semibold).foregroundStyle(.secondary)
                                    }
                                }
                                .scaledFont(17)
                                .foregroundStyle(.white)
                                .padding(.horizontal, 8).frame(height: 34)
                                .background(Color(white: 0.14))
                            }
                            .frame(width: m.poster)
                            .clipShape(RoundedRectangle(cornerRadius: 5, style: .continuous))
                        }
                    }
                }
                .padding(.horizontal, m.gutter)
            }
        }
    }
}

// MARK: Buttons

struct PillButton: View {
    let title: String
    let systemImage: String
    var primary = true
    let action: () -> Void
    var body: some View {
        Button(action: action) {
            Label(title, systemImage: systemImage)
                .scaledFont(16, weight: .semibold)
                .frame(maxWidth: .infinity, minHeight: 42)
                .foregroundStyle(primary ? .black : .white)
                .background(primary ? Color.white : Color.white.opacity(0.2), in: RoundedRectangle(cornerRadius: 6))
        }
        .buttonStyle(.plain)
    }
}

struct ProfileAvatar: View {
    let profile: Library.Profile
    var size: CGFloat = 28
    var body: some View {
        RoundedRectangle(cornerRadius: size * 0.18)
            .fill(Avatar.colors[profile.color % Avatar.colors.count].gradient)
            .frame(width: size, height: size)
            .overlay(Text(String(profile.name.prefix(1))).font(.system(size: size * 0.5, weight: .heavy)).foregroundStyle(.white))
            .accessibilityHidden(true)   // the profile name is shown (and read) next to it
    }
}

// MARK: Dynamic Type

/// The app's point sizes, scaled with the reader's text size (Dynamic Type). Each size grows
/// relative to the text style it sits closest to, so 13 pt footnotes and 28 pt titles keep
/// their proportions. Use instead of `.font(.system(size:))`, which never scales; only fixed-
/// frame artwork (Top 10 flag, rank numerals, avatar initials) keeps a fixed size, and it is
/// hidden from VoiceOver because a label next to it already says the same thing.
struct ScaledFont: ViewModifier {
    @ScaledMetric private var size: CGFloat
    private let weight: Font.Weight
    private let design: Font.Design

    init(size: CGFloat, weight: Font.Weight, design: Font.Design) {
        _size = ScaledMetric(wrappedValue: size, relativeTo: Self.style(for: size))
        self.weight = weight
        self.design = design
    }

    static func style(for size: CGFloat) -> Font.TextStyle {
        switch size {
        case 30...: .largeTitle
        case 24..<30: .title
        case 20..<24: .title2
        case 17..<20: .body
        case 15..<17: .subheadline
        case 13..<15: .footnote
        case 12..<13: .caption
        default: .caption2
        }
    }

    func body(content: Content) -> some View {
        content.font(.system(size: size, weight: weight, design: design))
    }
}

extension View {
    func scaledFont(_ size: CGFloat, weight: Font.Weight = .regular, design: Font.Design = .default) -> some View {
        modifier(ScaledFont(size: size, weight: weight, design: design))
    }
}
