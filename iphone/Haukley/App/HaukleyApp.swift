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
            if splash { SplashView().transition(.opacity) }
        }
        .task {
            try? await Task.sleep(for: .milliseconds(900))
            withAnimation(.easeOut(duration: 0.35)) { splash = false }
        }
    }
}

/// Brief wordmark on cold launch (no prompt, no interaction).
struct SplashView: View {
    @State private var scale = 0.92
    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            Image("Wordmark").resizable().scaledToFit().frame(width: 190)
                .scaleEffect(scale)
        }
        .accessibilityIdentifier("splash")
        .onAppear { withAnimation(.easeOut(duration: 0.8)) { scale = 1.0 } }
    }
}
