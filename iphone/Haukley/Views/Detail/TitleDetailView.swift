import SwiftUI

/// Netflix-style title sheet: backdrop, Play, synopsis, actions, episodes, More Like This.
struct TitleDetailView: View {
    let title: Title
    @EnvironmentObject private var library: Library
    @EnvironmentObject private var router: Router
    @Environment(\.dismiss) private var dismiss
    @State private var play: PlayRequest?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                ZStack {
                    BundleImage(url: title.backdrop)
                        .accessibilityHidden(true)   // key art; the title is the next element
                        .aspectRatio(16 / 9, contentMode: .fit)
                }
                .overlay(alignment: .topTrailing) {
                    Button { dismiss() } label: {
                        Image(systemName: "xmark").scaledFont(14, weight: .bold)
                            .frame(width: 32, height: 32).background(.black.opacity(0.6), in: Circle())
                    }
                    .buttonStyle(.plain)
                    .padding(10)
                    .accessibilityLabel("Close")
                    .accessibilityIdentifier("detail.close")
                }

                VStack(alignment: .leading, spacing: 12) {
                    HStack(spacing: 6) {
                        Image("LogoMark").resizable().scaledToFit().frame(width: 14, height: 14)
                        Text(title.isLive ? "LIVE CHANNEL" : title.isShow ? "SERIES" : "FILM")
                            .scaledFont(12, weight: .bold).kerning(2).foregroundStyle(.secondary)
                    }
                    Text(title.title).scaledFont(26, weight: .bold)
                        .accessibilityIdentifier("detail.title")
                    HStack(spacing: 8) {
                        if title.isLive {
                            Text("LIVE").scaledFont(12, weight: .heavy).foregroundStyle(.white)
                                .padding(.horizontal, 6).padding(.vertical, 2)
                                .background(Color.live, in: RoundedRectangle(cornerRadius: 3))
                                .accessibilityIdentifier("detail.live")
                        } else {
                            Text(String(title.year))
                        }
                        Text(title.rating).padding(.horizontal, 4).padding(.vertical, 1)
                            .foregroundStyle(.white)
                            .background(Color(white: 0.3), in: RoundedRectangle(cornerRadius: 2))
                        if !title.isLive { Text(title.length) }
                        Text("HD").scaledFont(10, weight: .bold).padding(.horizontal, 3)
                            .overlay(RoundedRectangle(cornerRadius: 2).stroke(Color.secondary))
                    }
                    .scaledFont(14).foregroundStyle(.secondary)

                    PillButton(title: title.isLive ? "Watch Live" : title.isShow ? "Play S1:E1" : "Play",
                               systemImage: "play.fill") {
                        play = PlayRequest(title: title, episode: title.isShow ? 1 : nil)
                    }
                    .accessibilityIdentifier("detail.play")

                    if title.isLive { WeatherCard() }

                    Text(title.tagline).scaledFont(15, weight: .semibold)
                    Text(title.description).scaledFont(15)
                    if let advisory = title.advisory {
                        Label("Advisory: \(advisory)", systemImage: "exclamationmark.triangle")
                            .scaledFont(13, weight: .semibold)
                            .accessibilityIdentifier("detail.advisory")
                    }
                    Text(title.credits).scaledFont(13).foregroundStyle(.secondary)
                    if let license = title.license {
                        Text(license).scaledFont(12).foregroundStyle(.secondary)
                            .accessibilityIdentifier("detail.license")
                    }

                    HStack(spacing: 34) {
                        ActionButton(label: "My List", systemImage: library.isInMyList(title) ? "checkmark" : "plus") {
                            withAnimation(.snappy) { library.toggleMyList(title) }
                        }
                        .accessibilityIdentifier("detail.mylist")
                        ShareLink(item: URL(string: "https://haukley.com")!, message: Text("Watch \(title.title) free on Haukley")) {
                            VStack(spacing: 6) {
                                Image(systemName: "paperplane").scaledFont(22)
                                Text("Share").scaledFont(11)
                            }
                            .foregroundStyle(.white)
                        }
                    }
                    .padding(.top, 4)
                }
                .padding(.horizontal, 16)

                if title.isShow { episodes } else if !title.isLive { moreLike }
            }
            .padding(.bottom, 30)
        }
        .scrollIndicators(.hidden)
        .background(Color(white: 0.09))
        .presentationDragIndicator(.visible)
        .presentationBackground(Color(white: 0.09))
        .playerCover(item: $play)
    }

    private var episodes: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Episodes").scaledFont(17, weight: .bold).padding(.horizontal, 16)
            ForEach(title.episodes) { ep in
                Button { play = PlayRequest(title: title, episode: ep.number) } label: {
                    VStack(alignment: .leading, spacing: 8) {
                        HStack(spacing: 12) {
                            BundleImage(url: title.still(ep.number))
                                .frame(width: 130, height: 73)
                                .clipShape(RoundedRectangle(cornerRadius: 4))
                                .overlay { Image(systemName: "play.circle").scaledFont(26) }
                            VStack(alignment: .leading, spacing: 3) {
                                Text("\(ep.number). \(ep.name)").scaledFont(15, weight: .semibold)
                                Text("\(ep.minutes)m").scaledFont(13).foregroundStyle(.secondary)
                            }
                            Spacer(minLength: 0)
                        }
                        Text(ep.summary).scaledFont(13).foregroundStyle(.secondary).lineLimit(3)
                    }
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .padding(.horizontal, 16)
                .accessibilityIdentifier("episode.\(ep.number)")
            }
        }
        .padding(.top, 10)
    }

    private var moreLike: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("More Like This").scaledFont(17, weight: .bold)
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 110, maximum: 170), spacing: 8)], spacing: 8) {
                ForEach(Catalog.shared.moreLike(title).filter(library.allows).prefix(9)) { t in
                    Button { router.detail = t } label: {
                        BundleImage(url: t.poster)
                            .aspectRatio(2 / 3, contentMode: .fill)
                            .clipShape(RoundedRectangle(cornerRadius: 4))
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel(t.title)
                }
            }
        }
        .padding(.horizontal, 16)
        .padding(.top, 10)
    }
}

private struct ActionButton: View {
    let label: String
    let systemImage: String
    let action: () -> Void
    var body: some View {
        Button(action: action) {
            VStack(spacing: 6) {
                Image(systemName: systemImage).scaledFont(22).frame(height: 24)
                Text(label).scaledFont(11)
            }
            .foregroundStyle(.white)
        }
        .buttonStyle(.plain)
    }
}
