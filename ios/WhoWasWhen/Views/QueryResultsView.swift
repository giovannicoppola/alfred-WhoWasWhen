import SwiftUI

/// A fixed-query screen reached by "travel to year" (or a sub-query).
/// Runs the query once and shows the results; the back button returns
/// to the previous screen, like the workflow's "go back to main search".
struct QueryResultsView: View {
    let query: String
    @Environment(AppModel.self) private var app
    @State private var results: [SearchResult] = []
    @State private var loaded = false

    /// Show "44 BC" rather than the raw "-44" used for searching.
    private var titleText: String {
        if let year = Int(query) { return formatYear(year) }
        return query
    }

    var body: some View {
        ResultsList(results: results, isIdle: false)
            .navigationTitle(titleText)
            .navigationBarTitleDisplayMode(.inline)
            .overlay { if !loaded { ProgressView() } }
            .task {
                results = await app.results(for: query)
                loaded = true
            }
    }
}
