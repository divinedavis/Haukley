import AVKit
import GoogleInteractiveMediaAds
import SwiftUI
import UIKit

extension View {
    /// Full-screen player for a PlayRequest. Each presenting surface (root, detail sheet)
    /// owns its own cover, since a cover can't be presented from under a sheet.
    func playerCover(item: Binding<PlayRequest?>) -> some View {
        fullScreenCover(item: item) { req in PlayerScreen(request: req) }
    }
}

struct PlayerScreen: View {
    let request: PlayRequest
    @EnvironmentObject private var library: Library
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        PlayerContainer(request: request) { progress in
            if !request.trailer, !request.title.isLive {
                library.record(request.title, episode: request.episode ?? 0, progress: progress)
            }
        }
        .ignoresSafeArea()
        .background(Color.black)
        .overlay(alignment: .topLeading) {
            Button { dismiss() } label: {
                Image(systemName: "xmark").scaledFont(16, weight: .bold)
                    .frame(width: 40, height: 40)
                    .background(.black.opacity(0.45), in: Circle())
            }
            .buttonStyle(.plain)
            .padding(.leading, 16).padding(.top, 8)
            .accessibilityLabel("Close player")
            .accessibilityIdentifier("player.close")
        }
        .overlay(alignment: .bottomLeading) {
            // The weather channel is one national stream; the viewer's own temperature rides on top.
            if request.title.isLive {
                WeatherChip().padding(.leading, 16).padding(.bottom, 64)
            }
        }
        .statusBarHidden()
        .onAppear { Orientation.set(.allButUpsideDown, prefer: .landscapeRight) }
        .onDisappear { Orientation.set(.portrait, prefer: .portrait) }
    }
}

enum Orientation {
    static func set(_ mask: UIInterfaceOrientationMask, prefer: UIInterfaceOrientationMask) {
        AppDelegate.orientationMask = mask
        // iPad rotates freely; don't force the player into landscape or back to portrait.
        if UIDevice.current.userInterfaceIdiom == .pad { return }
        guard let scene = UIApplication.shared.connectedScenes.first as? UIWindowScene else { return }
        scene.requestGeometryUpdate(.iOS(interfaceOrientations: prefer)) { _ in }
        scene.keyWindow?.rootViewController?.setNeedsUpdateOfSupportedInterfaceOrientations()
    }
}

private struct PlayerContainer: UIViewControllerRepresentable {
    let request: PlayRequest
    let onFinish: (Double) -> Void

    func makeUIViewController(context: Context) -> PlayerViewController {
        PlayerViewController(request: request, onFinish: onFinish)
    }

    func updateUIViewController(_ vc: PlayerViewController, context: Context) {}
}

/// AVPlayer content with Google IMA client-side ads. Trailers play without ads.
final class PlayerViewController: UIViewController, IMAAdsLoaderDelegate, IMAAdsManagerDelegate {
    private let request: PlayRequest
    private let onFinish: (Double) -> Void
    private let player: AVPlayer
    private let playerVC = AVPlayerViewController()
    private let adContainer = UIView()
    private lazy var tracker = Ads.Tracker(title: request.title, episode: request.episode ?? 0)

    private var adsLoader: IMAAdsLoader?
    private var adsManager: IMAAdsManager?
    private var contentPlayhead: IMAAVPlayerContentPlayhead?
    private var started = false
    private var endObserver: NSObjectProtocol?

    init(request: PlayRequest, onFinish: @escaping (Double) -> Void) {
        self.request = request
        self.onFinish = onFinish
        let stream = request.episode.flatMap { n in request.title.episodes.first { $0.number == n }?.stream }
            ?? request.title.stream
        player = AVPlayer(url: URL(string: stream) ?? URL(fileURLWithPath: "/"))
        super.init(nibName: nil, bundle: nil)
    }

    required init?(coder: NSCoder) { fatalError("init(coder:) is not used") }

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .black
        playerVC.player = player
        playerVC.allowsPictureInPicturePlayback = false
        if request.title.isLive {
            // AVKit shows live HLS without a scrubber or duration; also forbid seeking and tag it.
            playerVC.requiresLinearPlayback = true
        }
        addChild(playerVC)
        playerVC.view.frame = view.bounds
        playerVC.view.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        view.addSubview(playerVC.view)
        playerVC.didMove(toParent: self)

        adContainer.frame = view.bounds
        adContainer.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        adContainer.isUserInteractionEnabled = true
        view.addSubview(adContainer)

        endObserver = NotificationCenter.default.addObserver(
            forName: .AVPlayerItemDidPlayToEndTime, object: player.currentItem, queue: .main
        ) { [weak self] _ in
            // Lets IMA play the post-roll.
            self?.adsLoader?.contentComplete()
        }
    }

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        guard !started else { return }
        started = true
        // Live channels play without IMA ads (no VMAP schedule against an endless stream).
        if !request.trailer, !request.title.isLive, let tag = Ads.tag(for: request.title) {
            let tracker = tracker
            Task { await tracker.start() }
            requestAds(tag)
        } else {
            playContent()
        }
    }

    override func viewWillDisappear(_ animated: Bool) {
        super.viewWillDisappear(animated)
        let duration = player.currentItem?.duration.seconds ?? 0
        let position = player.currentTime().seconds
        if !request.title.isLive, duration.isFinite, duration > 0 { onFinish(position / duration) }
        player.pause()
        adsManager?.destroy()
        if let endObserver { NotificationCenter.default.removeObserver(endObserver) }
    }

    private func requestAds(_ tag: String) {
        let playhead = IMAAVPlayerContentPlayhead(avPlayer: player)
        contentPlayhead = playhead
        let display = IMAAdDisplayContainer(adContainer: adContainer, viewController: self, companionSlots: nil)
        let loader = IMAAdsLoader(settings: nil)
        loader.delegate = self
        adsLoader = loader
        loader.requestAds(with: IMAAdsRequest(adTagUrl: tag, adDisplayContainer: display,
                                              contentPlayhead: playhead, userContext: nil))
    }

    // MARK: IMAAdsLoaderDelegate

    func adsLoader(_ loader: IMAAdsLoader, adsLoadedWith adsLoadedData: IMAAdsLoadedData) {
        guard let manager = adsLoadedData.adsManager else { return playContent() }
        adsManager = manager
        manager.delegate = self
        let settings = IMAAdsRenderingSettings()
        settings.linkOpenerPresentingController = self
        manager.initialize(with: settings)
    }

    func adsLoader(_ loader: IMAAdsLoader, failedWith adErrorData: IMAAdLoadingErrorData) {
        playContent()
    }

    // MARK: IMAAdsManagerDelegate

    func adsManager(_ adsManager: IMAAdsManager, didReceive event: IMAAdEvent) {
        switch event.type {
        case .LOADED:
            adsManager.start()
        case .STARTED:
            let tracker = tracker
            Task { await tracker.log(.started) }
        case .COMPLETE:
            let tracker = tracker
            Task { await tracker.log(.completed) }
        default:
            break
        }
    }

    func adsManager(_ adsManager: IMAAdsManager, didReceive error: IMAAdError) {
        playContent()
    }

    func adsManagerDidRequestContentPause(_ adsManager: IMAAdsManager) {
        player.pause()
        playerVC.showsPlaybackControls = false
        adContainer.isHidden = false
    }

    func adsManagerDidRequestContentResume(_ adsManager: IMAAdsManager) {
        playContent()
    }

    private func playContent() {
        adContainer.isHidden = true
        playerVC.showsPlaybackControls = true
        player.play()
        showAdvisoryOnce()
        showLiveTag()
    }

    private var liveTagShown = false

    /// A red LIVE tag in the top-right corner for the whole time a live channel plays.
    private func showLiveTag() {
        guard request.title.isLive, !liveTagShown, let overlay = playerVC.contentOverlayView else { return }
        liveTagShown = true
        let tag = UILabel()
        tag.text = "  LIVE  "
        tag.font = UIFont.systemFont(ofSize: 13, weight: .heavy)
        tag.textColor = .white
        tag.backgroundColor = UIColor(red: 0.902, green: 0.224, blue: 0.275, alpha: 1)
        tag.layer.cornerRadius = 4
        tag.layer.masksToBounds = true
        tag.translatesAutoresizingMaskIntoConstraints = false
        tag.isAccessibilityElement = true
        tag.accessibilityLabel = "Live"
        tag.accessibilityIdentifier = "player.live"
        overlay.addSubview(tag)
        NSLayoutConstraint.activate([
            tag.trailingAnchor.constraint(equalTo: overlay.safeAreaLayoutGuide.trailingAnchor, constant: -16),
            tag.topAnchor.constraint(equalTo: overlay.safeAreaLayoutGuide.topAnchor, constant: 14),
            tag.heightAnchor.constraint(equalToConstant: 24),
        ])
    }

    private var advisoryShown = false

    /// The title's content advisory, over the film for 8 s when it first starts (not over ads).
    private func showAdvisoryOnce() {
        guard !advisoryShown, !request.trailer, let text = request.title.advisory,
              let overlay = playerVC.contentOverlayView else { return }
        advisoryShown = true
        let label = UILabel()
        label.numberOfLines = 0
        label.attributedText = {
            let s = NSMutableAttributedString(string: "ADVISORY\n", attributes: [
                .font: UIFont.systemFont(ofSize: 20, weight: .heavy), .foregroundColor: UIColor.white])
            s.append(NSAttributedString(string: text, attributes: [
                .font: UIFont.systemFont(ofSize: 15), .foregroundColor: UIColor(white: 0.85, alpha: 1)]))
            return s
        }()
        let card = UIView()
        card.backgroundColor = UIColor(white: 0, alpha: 0.55)
        let bar = UIView()
        bar.backgroundColor = UIColor(red: 0.55, green: 0.42, blue: 1.0, alpha: 1)
        [card, bar, label].forEach { $0.translatesAutoresizingMaskIntoConstraints = false }
        card.addSubview(bar)
        card.addSubview(label)
        overlay.addSubview(card)
        NSLayoutConstraint.activate([
            card.leadingAnchor.constraint(equalTo: overlay.safeAreaLayoutGuide.leadingAnchor),
            card.topAnchor.constraint(equalTo: overlay.topAnchor, constant: overlay.bounds.height * 0.18 + 20),
            card.widthAnchor.constraint(lessThanOrEqualTo: overlay.widthAnchor, multiplier: 0.7),
            bar.leadingAnchor.constraint(equalTo: card.leadingAnchor),
            bar.topAnchor.constraint(equalTo: card.topAnchor),
            bar.bottomAnchor.constraint(equalTo: card.bottomAnchor),
            bar.widthAnchor.constraint(equalToConstant: 4),
            label.leadingAnchor.constraint(equalTo: bar.trailingAnchor, constant: 14),
            label.trailingAnchor.constraint(equalTo: card.trailingAnchor, constant: -18),
            label.topAnchor.constraint(equalTo: card.topAnchor, constant: 8),
            label.bottomAnchor.constraint(equalTo: card.bottomAnchor, constant: -8),
        ])
        card.accessibilityIdentifier = "player.advisory"
        DispatchQueue.main.asyncAfter(deadline: .now() + 8) {
            UIView.animate(withDuration: 0.4, animations: { card.alpha = 0 }) { _ in card.removeFromSuperview() }
        }
    }
}
