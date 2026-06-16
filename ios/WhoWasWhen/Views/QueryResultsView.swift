import SwiftUI

/// A fixed-query screen reached by "travel to year" (always a year).
/// Runs the query under a pinned year header, with a scope selector so the
/// All / Rulers / Events filter is available here too. The back button
/// returns to the previous screen, like the workflow's "go back to main search".
struct QueryResultsView: View {
    let query: String
    @Environment(AppModel.self) private var app
    @State private var results: [SearchResult] = []
    @State private var loaded = false

    var body: some View {
        @Bindable var app = app
        ResultsList(results: results, isIdle: false,
                    yearHeader: QueryParser.displayYear(for: query) ?? query)
            .navigationBarTitleDisplayMode(.inline)
            .overlay { if !loaded { ProgressView() } }
            .toolbar {
                ToolbarItem(placement: .principal) {
                    Picker("Scope", selection: $app.scope) {
                        ForEach(SearchScope.allCases) { Text($0.rawValue).tag($0) }
                    }
                    .pickerStyle(.segmented)
                    .frame(maxWidth: 260)
                }
            }
            // Re-runs on first appearance and whenever the scope changes.
            .task(id: app.scope) {
                results = await app.results(for: query)
                loaded = true
            }
    }
}
