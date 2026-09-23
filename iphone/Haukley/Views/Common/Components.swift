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
            .font(.system(size: 9, weight: .bold))
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
    }
}

// MARK: Rows

struct RowHeader: View {
    let title: String
    var body: some View {
        Text(title)
            .font(.system(size: 19, weight: .bold))
            .foregroundStyle(.white)
            .padding(.horizontal, 16)
    }
}

struct PosterRow: View {
    let title: String
    let titles: [Title]
    var tall = false
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            RowHeader(title: title)
            ScrollView(.horizontal, showsIndicators: false) {
                LazyHStack(spacing: 8) {
                    ForEach(titles) { PosterTile(title: $0, width: tall ? 150 : 112) }
                }
                .padding(.horizontal, 16)
            }
        }
    }
}

struct Top10Row: View {
    let title: String
    let titles: [Title]
    @EnvironmentObject private var router: Router
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            RowHeader(title: title)
            ScrollView(.horizontal, showsIndicators: false) {
                LazyHStack(spacing: 4) {
                    ForEach(Array(titles.prefix(10).enumerated()), id: \.element.id) { i, t in
                        HStack(alignment: .bottom, spacing: -22) {
                            RankNumeral(n: i + 1).offset(y: 18)
                            PosterTile(title: t, width: 104)
                        }
                        .padding(.trailing, 6)
                    }
                }
                .padding(.horizontal, 16)
            }
        }
    }
}

struct ContinueRow: View {
    let title: String
    let items: [Library.Watch]
    @EnvironmentObject private var router: Router
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
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
                                        .frame(width: 112, height: 150)
                                        .clipped()
                                        .overlay {
                                            Image(systemName: "play.fill")
                                                .font(.system(size: 18))
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
                                        Text("E\(w.episode)").font(.system(size: 11, weight: .semibold)).foregroundStyle(.secondary)
                                    }
                                }
                                .font(.system(size: 17))
                                .foregroundStyle(.white)
                                .padding(.horizontal, 8).frame(height: 34)
                                .background(Color(white: 0.14))
                            }
                            .frame(width: 112)
                            .clipShape(RoundedRectangle(cornerRadius: 5, style: .continuous))
                        }
                    }
                }
                .padding(.horizontal, 16)
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
                .font(.system(size: 16, weight: .semibold))
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
    }
}
