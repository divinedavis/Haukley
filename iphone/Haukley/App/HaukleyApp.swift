import SwiftUI
import UIKit

@main
struct HaukleyApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @StateObject private var library = Library()
    @StateObject private var router = Router()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(library)
                .environmentObject(router)
                .preferredColorScheme(.dark)
                .tint(.white)
        }
    }
}

/// Portrait everywhere except the player, which unlocks landscape while it's up.
final class AppDelegate: NSObject, UIApplicationDelegate {
    static var orientationMask: UIInterfaceOrientationMask = .portrait

    func application(_ application: UIApplication,
                     supportedInterfaceOrientationsFor window: UIWindow?) -> UIInterfaceOrientationMask {
        AppDelegate.orientationMask
    }
}

struct PlayRequest: Identifiable {
    let id = UUID()
    let title: Title
    var episode: Int? = nil
    var trailer = false
}

@MainActor
final class Router: ObservableObject {
    @Published var detail: Title?
    @Published var play: PlayRequest?
    @Published var tab: AppTab = .home
}

enum AppTab: Hashable { case home, clips, search, mine }

struct RootView: View {
    @EnvironmentObject private var router: Router
    @State private var splash = true

    var body: some View {
        TabView(selection: $router.tab) {
            Tab("Home", systemImage: "house.fill", value: AppTab.home) {
                HomeView()
            }
            Tab("Clips", systemImage: "play.rectangle.on.rectangle.fill", value: AppTab.clips) {
                ClipsView(active: router.tab == .clips && router.detail == nil && router.play == nil)
            }
            Tab("My Haukley", systemImage: "person.crop.circle.fill", value: AppTab.mine) {
                MyHaukleyView()
            }
            Tab(value: AppTab.search, role: .search) {
                SearchView()
            }
        }
        .sheet(item: $router.detail) { t in
            TitleDetailView(title: t)
        }
        .playerCover(item: $router.play)
        .overlay {
            if splash { SplashView { splash = false } }
        }
    }
}

/// Cold-launch wordmark in the style of X's launch: "Haukley." sits on black, the letters
/// fade as the purple period pulls in, then the period opens into a circular window that
/// grows until the app underneath fills the screen. No prompt, no interaction.
struct SplashView: View {
    let onFinish: () -> Void

    // Where the period sits inside WordmarkText.png (from scripts: dot center / radius as
    // fractions of the 461x130 image). Keep in sync if the wordmark is regenerated.
    private static let imageAspect: CGFloat = 461.0 / 130.0
    private static let dotX: CGFloat = 0.9451
    private static let dotY: CGFloat = 0.6260
    private static let dotR: CGFloat = 0.0229

    private let wordmarkWidth: CGFloat = 200

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var textOpacity = 0.0
    @State private var dotScale: CGFloat = 1
    @State private var dotOpacity = 1.0
    @State private var hole: CGFloat = 0
    @State private var fade = 1.0

    var body: some View {
        GeometryReader { g in
            let dotDiameter = wordmarkWidth * Self.dotR * 2
            let wordHeight = wordmarkWidth / Self.imageAspect
            let origin = CGPoint(x: (g.size.width - wordmarkWidth) / 2, y: (g.size.height - wordHeight) / 2)
            let center = CGPoint(x: origin.x + wordmarkWidth * Self.dotX, y: origin.y + wordHeight * Self.dotY)
            // Far enough to clear the farthest corner from the dot.
            let cover = 2.2 * hypot(max(center.x, g.size.width - center.x), max(center.y, g.size.height - center.y))

            ZStack {
                // Black curtain with a circular hole punched where the period is.
                Color.black
                    .mask {
                        Rectangle()
                            .overlay {
                                Circle()
                                    .frame(width: hole * cover, height: hole * cover)
                                    .position(center)
                                    .blendMode(.destinationOut)
                            }
                            .compositingGroup()
                    }
                Image("WordmarkText")
                    .resizable()
                    .frame(width: wordmarkWidth, height: wordHeight)
                    .position(x: g.size.width / 2, y: g.size.height / 2)
                    .opacity(textOpacity)
                Circle()
                    .fill(Color.brand)
                    .frame(width: dotDiameter, height: dotDiameter)
                    .scaleEffect(dotScale)
                    .opacity(dotOpacity)
                    .position(center)
            }
            .opacity(fade)
        }
        .ignoresSafeArea()
        .allowsHitTesting(hole < 0.3)
        .accessibilityIdentifier("splash")
        .task { await run() }
    }

    private func run() async {
        withAnimation(.easeOut(duration: 0.35)) { textOpacity = 1 }
        if reduceMotion {
            try? await Task.sleep(for: .milliseconds(700))
            withAnimation(.easeOut(duration: 0.3)) { fade = 0 }
            try? await Task.sleep(for: .milliseconds(300))
            return onFinish()
        }
        try? await Task.sleep(for: .milliseconds(650))
        // Anticipation: letters go, the period pulls in.
        withAnimation(.easeInOut(duration: 0.18)) {
            textOpacity = 0
            dotScale = 0.72
        }
        try? await Task.sleep(for: .milliseconds(180))
        // The period becomes a window and rushes outward.
        withAnimation(.easeIn(duration: 0.12)) { dotOpacity = 0 }
        withAnimation(.timingCurve(0.6, 0, 0.9, 0.6, duration: 0.55)) {
            hole = 1
            dotScale = 3
        }
        try? await Task.sleep(for: .milliseconds(560))
        onFinish()
    }
}
