import SwiftUI

@main
struct WhoWasWhenApp: App {
    @State private var app = AppModel()
    @State private var favorites = FavoritesStore()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(app)
                .environment(favorites)
                .task { await app.load() }
        }
    }
}

/// Shows the tabbed UI, or a clear error if the database failed to open.
struct RootView: View {
    @Environment(AppModel.self) private var app

    var body: some View {
        if let error = app.loadError {
            ContentUnavailableView {
                Label("Couldn't open the database", systemImage: "exclamationmark.triangle")
            } description: {
                Text(error)
            }
        } else {
            RootTabView()
        }
    }
}

/// The app's four tabs. Selection lives in `AppModel` so navigation actions
/// invoked from other tabs (travel / lineage) can jump back to Search.
struct RootTabView: View {
    @Environment(AppModel.self) private var app

    var body: some View {
        @Bindable var app = app
        TabView(selection: $app.selectedTab) {
            content
        }
        #if DEBUG
        // Lets automation screenshot a specific screen:
        // `simctl launch` with WWW_TAB=discover|quiz|favorites or
        // WWW_LINEAGE=<title> (pushes that lineage on the Search tab).
        .onAppear {
            switch ProcessInfo.processInfo.environment["WWW_TAB"] {
            case "discover": app.selectedTab = .discover
            case "quiz": app.selectedTab = .quiz
            case "favorites": app.selectedTab = .favorites
            #if ADMIN
            case "admin": app.selectedTab = .admin
            #endif
            default: break
            }
            #if ADMIN
            // WWW_ADMIN_KEY=<path> loads a service-account key file into the
            // Keychain (simulator screenshots of the configured state).
            if let path = ProcessInfo.processInfo.environment["WWW_ADMIN_KEY"],
               let json = FileManager.default.contents(atPath: path) {
                _ = AdminCredentials.save(json: json)
            }
            #endif
            if let title = ProcessInfo.processInfo.environment["WWW_LINEAGE"] {
                app.path.append(.lineage(title: title, rulerID: nil, prog: nil))
            }
        }
        #endif
    }

    @ViewBuilder private var content: some View {
        SearchView()
            .tabItem { Label("Search", systemImage: "magnifyingglass") }
            .tag(AppTab.search)
        DiscoverView()
            .tabItem { Label("Discover", systemImage: "sparkles") }
            .tag(AppTab.discover)
        QuizView()
            .tabItem { Label("Quiz", systemImage: "questionmark.circle") }
            .tag(AppTab.quiz)
        FavoritesView()
            .tabItem { Label("Favorites", systemImage: "star") }
            .tag(AppTab.favorites)
        #if ADMIN
        AdminView()
            .tabItem { Label("Admin", systemImage: "key") }
            .tag(AppTab.admin)
        #endif
    }
}
