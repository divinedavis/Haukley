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
/// glint crosses them, then the splash fades into the app.
/// Art: scripts/make_splash.py. No prompt, no interaction.
struct SplashView: View {
    let onFinish: () -> Void

    // SplashMaze/SplashLetters are 1500x420 (scripts/make_splash.py).
    private static let imageAspect: CGFloat = 1500.0 / 420.0
    // Glint path, as bar-width offsets of the band's center from the bar's center: it enters
    // just touching the H (letters span x 70...1330 of 1500) and leaves just clearing the Y.
    // The band is 0.28 wide, so each end sits half a band outside the lettering.
    private static let glintStart: CGFloat = 70.0 / 1500 - 0.5 - 0.14
    private static let glintEnd: CGFloat = 1330.0 / 1500 - 0.5 + 0.14
    private static let background = Color(red: 13 / 255, green: 10 / 255, blue: 20 / 255)

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var mazeOpacity = 0.0
    @State private var lettersOpacity = 0.0
    @State private var push: CGFloat = 1.06
    @State private var glint: CGFloat = 0
    @State private var fade = 1.0

    var body: some View {
        GeometryReader { g in
            let barWidth = min(g.size.width - 60, 360)
            let barHeight = barWidth / Self.imageAspect
            let barCenter = CGPoint(x: g.size.width / 2, y: g.size.height / 2)
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
                                .offset(x: barWidth * (Self.glintStart + glint * (Self.glintEnd - Self.glintStart)))
                                // Lay the band out across the whole bar before masking; masking the
                                // bare band shrank the letters into its middle-of-the-word frame,
                                // so the shine only ever showed over "UKL".
                                .frame(width: barWidth, height: barHeight)
                                .mask(Image("SplashLetters").resizable())
                                .blendMode(.screen)
                        }
                        .opacity(lettersOpacity)
                }
                .frame(width: barWidth, height: barHeight)
                .scaleEffect(push)
                .position(barCenter)
            }
            .opacity(fade)
        }
        .ignoresSafeArea()
        .allowsHitTesting(fade > 0.5)
        .accessibilityIdentifier("splash")
        .task { await run() }
    }

    private func pause(_ ms: Int) async { try? await Task.sleep(for: .milliseconds(ms)) }

    private func run() async {
        if reduceMotion {
            withAnimation(.easeOut(duration: 0.3)) { lettersOpacity = 1; mazeOpacity = 0.22 }
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
        // Same speed as the old off-screen-to-off-screen sweep (1.4 bar widths in 0.55s)
        // over the shorter letter-to-letter path (1.12 bar widths).
        withAnimation(.easeInOut(duration: 0.44)) { glint = 1 }
        // Hold on the finished word, then fade into the app.
        await pause(720)
        withAnimation(.easeOut(duration: 0.35)) { fade = 0 }
        await pause(350)
        onFinish()
    }
}
