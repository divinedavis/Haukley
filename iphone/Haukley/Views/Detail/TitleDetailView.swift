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
                        .aspectRatio(16 / 9, contentMode: .fit)
                }
                .overlay(alignment: .topTrailing) {
                    Button { dismiss() } label: {
                        Image(systemName: "xmark").font(.system(size: 14, weight: .bold))
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
                        Text(title.isShow ? "SERIES" : "FILM")
                            .font(.system(size: 12, weight: .bold)).kerning(2).foregroundStyle(.secondary)
                    }
                    Text(title.title).font(.system(size: 26, weight: .bold))
                        .accessibilityIdentifier("detail.title")
                    HStack(spacing: 8) {
                        Text(String(title.year))
                        Text(title.rating).padding(.horizontal, 4).padding(.vertical, 1)
                            .background(Color(white: 0.3), in: RoundedRectangle(cornerRadius: 2))
                        Text(title.length)
                        Text("HD").font(.system(size: 10, weight: .bold)).padding(.horizontal, 3)
                            .overlay(RoundedRectangle(cornerRadius: 2).stroke(Color.secondary))
                    }
                    .font(.system(size: 14)).foregroundStyle(.secondary)

                    PillButton(title: title.isShow ? "Play S1:E1" : "Play", systemImage: "play.fill") {
                        play = PlayRequest(title: title, episode: title.isShow ? 1 : nil)
                    }
                    .accessibilityIdentifier("detail.play")

                    Text(title.tagline).font(.system(size: 15, weight: .semibold))
                    Text(title.description).font(.system(size: 15))
                    Text(title.credits).font(.system(size: 13)).foregroundStyle(.secondary)

                    HStack(spacing: 34) {
                        ActionButton(label: "My List", systemImage: library.isInMyList(title) ? "checkmark" : "plus") {
                            withAnimation(.snappy) { library.toggleMyList(title) }
                        }
                        .accessibilityIdentifier("detail.mylist")
                        ShareLink(item: URL(string: "https://haukley.com")!, message: Text("Watch \(title.title) free on Haukley")) {
                            VStack(spacing: 6) {
                                Image(systemName: "paperplane").font(.system(size: 22))
                                Text("Share").font(.system(size: 11))
                            }
                            .foregroundStyle(.white)
                        }
                    }
                    .padding(.top, 4)
                }
                .padding(.horizontal, 16)

                if title.isShow { episodes } else { moreLike }
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
            Text("Season 1").font(.system(size: 17, weight: .bold)).padding(.horizontal, 16)
            ForEach(title.episodes) { ep in
                Button { play = PlayRequest(title: title, episode: ep.number) } label: {
                    VStack(alignment: .leading, spacing: 8) {
                        HStack(spacing: 12) {
                            BundleImage(url: title.still(ep.number))
                                .frame(width: 130, height: 73)
                                .clipShape(RoundedRectangle(cornerRadius: 4))
                                .overlay { Image(systemName: "play.circle").font(.system(size: 26)) }
                            VStack(alignment: .leading, spacing: 3) {
                                Text("\(ep.number). \(ep.name)").font(.system(size: 15, weight: .semibold))
                                Text("\(ep.minutes)m").font(.system(size: 13)).foregroundStyle(.secondary)
                            }
                            Spacer(minLength: 0)
                        }
                        Text(ep.summary).font(.system(size: 13)).foregroundStyle(.secondary).lineLimit(3)
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
            Text("More Like This").font(.system(size: 17, weight: .bold))
            LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 8), count: 3), spacing: 8) {
                ForEach(Catalog.shared.moreLike(title).prefix(9)) { t in
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
                Image(systemName: systemImage).font(.system(size: 22)).frame(height: 24)
                Text(label).font(.system(size: 11))
            }
            .foregroundStyle(.white)
        }
        .buttonStyle(.plain)
    }
}
