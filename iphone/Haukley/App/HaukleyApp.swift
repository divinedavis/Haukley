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

/// Cold-launch splash, after the owner's reference clip: HAUKLEY sits hidden in a maze of
/// silver lines inside a framed bar; the maze recedes as the engraved letters surface, a
/// glint crosses them, then the purple period appears and opens into a circular window that
/// grows until the app fills the screen (the letters are swallowed, never faded).
/// Art: scripts/make_splash.py. No prompt, no interaction.
struct SplashView: View {
    let onFinish: () -> Void

    // SplashMaze/SplashLetters are 1500x420; the period's center and radius are fractions of
    // that image, printed by scripts/make_splash.py. Keep in sync if the art is regenerated.
    private static let imageAspect: CGFloat = 1500.0 / 420.0
    private static let dotX: CGFloat = 0.9107
    private static let dotY: CGFloat = 0.7571
    private static let dotR: CGFloat = 0.0160
    private static let background = Color(red: 13 / 255, green: 10 / 255, blue: 20 / 255)

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var mazeOpacity = 0.0
    @State private var lettersOpacity = 0.0
    @State private var push: CGFloat = 1.06
    @State private var glint: CGFloat = -1
    @State private var dotScale: CGFloat = 0
    @State private var hole: CGFloat = 0
    @State private var fade = 1.0

    var body: some View {
        GeometryReader { g in
            let barWidth = min(g.size.width - 60, 360)
            let barHeight = barWidth / Self.imageAspect
            let barCenter = CGPoint(x: g.size.width / 2, y: g.size.height / 2)
            let center = CGPoint(x: barCenter.x - barWidth / 2 + barWidth * Self.dotX,
                                 y: barCenter.y - barHeight / 2 + barHeight * Self.dotY)
            let dotDiameter = barWidth * Self.dotR * 2
            // Far enough to clear the farthest corner from the period.
            let cover = 2.2 * hypot(max(center.x, g.size.width - center.x), max(center.y, g.size.height - center.y))

            ZStack {
                // Curtain + art, with a circular hole punched at the period so the opening
                // window cuts through the letters and maze instead of fading them.
                ZStack {
                    Self.background
                    ZStack {
                        Image("SplashMaze").resizable().opacity(mazeOpacity)
                        Image("SplashLetters").resizable()
                            .overlay {
                                // A band of light sliding across the silver, clipped to the letters.
                                LinearGradient(colors: [.clear, .white.opacity(0.75), .clear],
                                               startPoint: .leading, endPoint: .trailing)
                                    .frame(width: barWidth * 0.28)
                                    .offset(x: glint * barWidth * 0.7)
                                    .mask(Image("SplashLetters").resizable())
                                    .blendMode(.screen)
                            }
                            .opacity(lettersOpacity)
                    }
                    .frame(width: barWidth, height: barHeight)
                    .scaleEffect(push)
                    .position(barCenter)
                }
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
                Circle()
                    .fill(Color.brand)
                    .frame(width: dotDiameter, height: dotDiameter)
                    .scaleEffect(dotScale)
                    .position(center)
            }
            .opacity(fade)
        }
        .ignoresSafeArea()
        .allowsHitTesting(hole < 0.3)
        .accessibilityIdentifier("splash")
        .task { await run() }
    }

    private func pause(_ ms: Int) async { try? await Task.sleep(for: .milliseconds(ms)) }

    private func run() async {
        if reduceMotion {
            withAnimation(.easeOut(duration: 0.3)) { lettersOpacity = 1; mazeOpacity = 0.22; dotScale = 1 }
            await pause(900)
            withAnimation(.easeOut(duration: 0.3)) { fade = 0 }
            await pause(300)
            return onFinish()
        }
        // The maze fades up while the camera settles in.
        withAnimation(.easeOut(duration: 0.55)) { mazeOpacity = 1 }
        withAnimation(.easeOut(duration: 1.6)) { push = 1 }
        await pause(450)
        // The word surfaces out of the maze; the maze recedes behind it.
        withAnimation(.easeInOut(duration: 0.6)) {
            lettersOpacity = 1
            mazeOpacity = 0.22
        }
        await pause(500)
        withAnimation(.easeInOut(duration: 0.55)) { glint = 1 }
        await pause(420)
        // The period arrives, pulls in, then opens into the app.
        withAnimation(.spring(duration: 0.22, bounce: 0.35)) { dotScale = 1 }
        await pause(260)
        withAnimation(.easeInOut(duration: 0.14)) { dotScale = 0.72 }
        await pause(140)
        withAnimation(.timingCurve(0.6, 0, 0.9, 0.6, duration: 0.55)) {
            hole = 1
            dotScale = 0
        }
        await pause(560)
        onFinish()
    }
}
