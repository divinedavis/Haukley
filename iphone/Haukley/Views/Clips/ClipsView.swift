import AVFoundation
import SwiftUI
import UIKit

/// Full-screen vertical feed of muted previews, one title per page (Netflix Clips).
struct ClipsView: View {
    let active: Bool
    @State private var current: String?
    @State private var muted = true

    @EnvironmentObject private var library: Library

    private var clips: [Title] {
        let c = Catalog.shared
        let lead = c.featured.filter(library.allows)
        return lead + c.titles.filter { t in library.allows(t) && !lead.contains(t) }
    }

    var body: some View {
        ScrollView(.vertical) {
            LazyVStack(spacing: 0) {
                ForEach(clips) { t in
                    ClipPage(title: t, isActive: active && current == t.id, muted: $muted)
                        .containerRelativeFrame([.horizontal, .vertical]) { length, axis in
                            length  // full page; the ClipPage itself caps its width on iPad
                        }
                        .id(t.id)
                }
            }
            .scrollTargetLayout()
        }
        .scrollTargetBehavior(.paging)
        .scrollPosition(id: $current)
        .scrollIndicators(.hidden)
        .ignoresSafeArea(edges: .top)
        .background(Color.black)
        .onAppear { if current == nil { current = clips.first?.id } }
        .accessibilityIdentifier("clips.feed")
    }
}

private struct ClipPage: View {
    let title: Title
    let isActive: Bool
    @Binding var muted: Bool
    @EnvironmentObject private var library: Library
    @EnvironmentObject private var router: Router

    @Environment(\.horizontalSizeClass) private var sizeClass

    var body: some View {
        if sizeClass == .regular {
            // iPad: a centred vertical column, like a phone-shaped reel, on black.
            GeometryReader { g in
                page.frame(width: min(g.size.width, g.size.height * 9 / 16)).frame(maxWidth: .infinity)
            }
            .background(Color.black)
        } else {
            page
        }
    }

    private var page: some View {
        ZStack(alignment: .bottom) {
            GeometryReader { g in
                // Backdrop (no baked-in title text) under the full-bleed video, like Netflix Clips.
                BundleImage(url: title.backdrop)
                    .frame(width: g.size.width, height: g.size.height)
                    .blur(radius: 18)
                    .overlay(Color.black.opacity(0.35))
                    .clipped()
                    .overlay {
                        if isActive {
                            LoopingVideo(url: URL(string: title.stream), muted: muted)
                                .frame(width: g.size.width, height: g.size.height)
                        }
                    }
            }
            LinearGradient(colors: [.clear, .black.opacity(0.92)], startPoint: UnitPoint(x: 0.5, y: 0.45), endPoint: .bottom)
                .allowsHitTesting(false)

            HStack(alignment: .bottom, spacing: 14) {
                VStack(alignment: .leading, spacing: 8) {
                    Text(title.title).font(.system(size: 24, weight: .bold)).lineLimit(2)
                    Text("\(title.genre) • \(String(title.year)) • \(title.rating)")
                        .font(.system(size: 13, weight: .semibold)).foregroundStyle(.white.opacity(0.85))
                    Text(title.description).font(.system(size: 14)).foregroundStyle(.white.opacity(0.85)).lineLimit(3)
                }
                Spacer(minLength: 0)
                VStack(spacing: 20) {
                    SideButton(systemImage: muted ? "speaker.slash.fill" : "speaker.wave.2.fill",
                               label: muted ? "Unmute" : "Mute") { muted.toggle() }
                    SideButton(systemImage: library.isInMyList(title) ? "checkmark" : "plus", label: "My List") {
                        withAnimation(.snappy) { library.toggleMyList(title) }
                    }
                    ShareLink(item: URL(string: "https://haukley.com")!, message: Text("Watch \(title.title) free on Haukley")) {
                        Image(systemName: "paperplane.fill").font(.system(size: 20))
                            .frame(width: 46, height: 46).background(.white.opacity(0.18), in: Circle())
                    }
                    .accessibilityLabel("Share")
                    Button { router.detail = title } label: {
                        BundleImage(url: title.poster).frame(width: 46, height: 46).clipShape(Circle())
                            .overlay(Circle().stroke(.white, lineWidth: 1.5))
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("Details for \(title.title)")
                    .accessibilityIdentifier("clip.details.\(title.id)")
                }
                .foregroundStyle(.white)
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 110)
        }
        .background(Color.black)
    }
}

private struct SideButton: View {
    let systemImage: String
    let label: String
    let action: () -> Void
    var body: some View {
        Button(action: action) {
            Image(systemName: systemImage).font(.system(size: 20))
                .frame(width: 46, height: 46).background(.white.opacity(0.18), in: Circle())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(label)
    }
}

/// The part of a title the Clips feed loops: under a minute, taken from inside the film so the
/// feed shows a scene instead of the opening credits.
enum ClipWindow {
    static let length: Double = 45
    /// Fraction of the runtime where a long title's clip starts (past the titles and credits).
    static let startFraction: Double = 0.2

    /// `end` is nil when the duration is unknown (live or not loaded): play from the top.
    static func range(duration: Double) -> (start: Double, end: Double?) {
        guard duration.isFinite, duration > 0 else { return (0, nil) }
        guard duration > 60 else { return (0, duration) }
        let start = min(duration * startFraction, duration - length)
        return (start, start + length)
    }
}

/// A looping AVPlayerLayer for one clip. Created only for the visible page and torn down after.
/// The whole frame is shown (aspect fit) over the page's blurred backdrop: films are 4:3 or
/// 16:9, so filling a portrait phone used to crop away most of the picture.
private struct LoopingVideo: UIViewRepresentable {
    let url: URL?
    let muted: Bool

    final class PlayerView: UIView {
        override static var layerClass: AnyClass { AVPlayerLayer.self }
        var playerLayer: AVPlayerLayer { layer as! AVPlayerLayer }
        var looper: NSObjectProtocol?
        var loopStart: CMTime = .zero
    }

    func makeUIView(context: Context) -> PlayerView {
        let v = PlayerView()
        v.isAccessibilityElement = true
        v.accessibilityIdentifier = "clip.video"
        v.accessibilityLabel = "Clip"
        v.accessibilityValue = "fit"
        guard let url else { return v }
        let item = AVPlayerItem(url: url)
        let player = AVPlayer(playerItem: item)
        player.isMuted = muted
        v.playerLayer.player = player
        v.playerLayer.videoGravity = .resizeAspect
        v.looper = NotificationCenter.default.addObserver(
            forName: .AVPlayerItemDidPlayToEndTime, object: item, queue: .main
        ) { [weak v] _ in
            player.seek(to: v?.loopStart ?? .zero)
            player.play()
        }
        Task { @MainActor [weak v] in
            let duration = (try? await item.asset.load(.duration))?.seconds ?? 0
            let window = ClipWindow.range(duration: duration)
            let start = CMTime(seconds: window.start, preferredTimescale: 600)
            if let end = window.end { item.forwardPlaybackEndTime = CMTime(seconds: end, preferredTimescale: 600) }
            _ = await player.seek(to: start)
            // The page may have scrolled away while the duration loaded.
            guard let v, v.playerLayer.player === player else { return }
            v.loopStart = start
            player.play()
        }
        return v
    }
    func updateUIView(_ v: PlayerView, context: Context) {
        v.playerLayer.player?.isMuted = muted
    }

    static func dismantleUIView(_ v: PlayerView, coordinator: ()) {
        v.playerLayer.player?.pause()
        v.playerLayer.player = nil
        if let looper = v.looper { NotificationCenter.default.removeObserver(looper) }
    }
}
