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
            if !request.trailer {
                library.record(request.title, episode: request.episode ?? 0, progress: progress)
            }
        }
        .ignoresSafeArea()
        .background(Color.black)
        .overlay(alignment: .topLeading) {
            Button { dismiss() } label: {
                Image(systemName: "xmark").font(.system(size: 16, weight: .bold))
                    .frame(width: 40, height: 40)
                    .background(.black.opacity(0.45), in: Circle())
            }
            .buttonStyle(.plain)
            .padding(.leading, 16).padding(.top, 8)
            .accessibilityLabel("Close player")
            .accessibilityIdentifier("player.close")
        }
        .statusBarHidden()
        .onAppear { Orientation.set(.allButUpsideDown, prefer: .landscapeRight) }
        .onDisappear { Orientation.set(.portrait, prefer: .portrait) }
    }
}

enum Orientation {
    static func set(_ mask: UIInterfaceOrientationMask, prefer: UIInterfaceOrientationMask) {
        AppDelegate.orientationMask = mask
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
    private let session = UUID()

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
        if !request.trailer, let tag = Ads.tag(for: request.title) {
            requestAds(tag)
        } else {
            adContainer.isHidden = true
            player.play()
        }
    }

    override func viewWillDisappear(_ animated: Bool) {
        super.viewWillDisappear(animated)
        let duration = player.currentItem?.duration.seconds ?? 0
        let position = player.currentTime().seconds
        if duration.isFinite, duration > 0 { onFinish(position / duration) }
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
            Ads.log(.started, title: request.title, episode: request.episode ?? 0, session: session)
        case .COMPLETE:
            Ads.log(.completed, title: request.title, episode: request.episode ?? 0, session: session)
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
    }
}
