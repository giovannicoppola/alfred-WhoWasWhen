import SwiftUI

/// The Favorites tab: saved rulers and events, newest first, rehydrated from
/// their database IDs so rows stay correct across database updates.
struct FavoritesView: View {
    @Environment(AppModel.self) private var app
    @Environment(FavoritesStore.self) private var favorites
    @State private var results: [SearchResult] = []
    @State private var loaded = false

    var body: some View {
        NavigationStack {
            Group {
                if results.isEmpty {
                    if loaded {
                        ContentUnavailableView {
                            Label("No favorites yet", systemImage: "star")
                        } description: {
                            Text("Swipe a result — or tap the star in its details — to save rulers and events here.")
                        }
                    } else {
                        ProgressView()
                    }
                } else {
                    List {
                        ForEach(Array(results.enumerated()), id: \.element.id) { idx, result in
                            ResultRow(result: result, index: idx, total: results.count)
                        }
                    }
                    .listStyle(.plain)
                }
            }
            .navigationTitle("Favorites")
            .navigationBarTitleDisplayMode(.inline)
            .task(id: favorites.entries) { await rehydrate() }
        }
        .toastOverlay(app.toast)
    }

    /// Looks each saved ID back up in the database, dropping entries that no
    /// longer resolve (e.g. removed in a data update).
    private func rehydrate() async {
        await app.load()   // wait for the database on a cold tab open
        var out: [SearchResult] = []
        for entry in favorites.entries {
            let result: SearchResult? = switch entry.kind {
            case .ruler: await app.ruler(byID: entry.dbID)
            case .event: await app.event(byID: entry.dbID)
            }
            if let result { out.append(result) }
        }
        results = out
        loaded = true
    }
}
