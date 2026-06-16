import SwiftUI

@main
struct WhoWasWhenApp: App {
    @State private var app = AppModel()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(app)
                .task { await app.load() }
        }
    }
}

/// Shows the search UI, or a clear error if the database failed to open.
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
            SearchView()
        }
    }
}
