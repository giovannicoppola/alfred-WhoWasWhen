import SwiftUI

/// Root screen: a search box at the top with live results, mirroring the
/// Alfred workflow. Year jumps and "show all" push onto the navigation stack.
struct SearchView: View {
    @Environment(AppModel.self) private var app
    // Debug hook: WWW_QUERY pre-fills the search box (used for UI verification).
    @State private var query = ProcessInfo.processInfo.environment["WWW_QUERY"] ?? ""
    @State private var results: [SearchResult] = []

    var body: some View {
        @Bindable var app = app
        NavigationStack(path: $app.path) {
            ResultsList(results: results,
                        isIdle: query.trimmingCharacters(in: .whitespaces).isEmpty,
                        yearHeader: QueryParser.displayYear(for: query))
                .navigationTitle("WhoWasWhen")
                .navigationBarTitleDisplayMode(.inline)
                .searchable(text: $query, placement: .navigationBarDrawer(displayMode: .always),
                            prompt: "Year, ruler, or event")
                .searchScopes($app.scope) {
                    ForEach(SearchScope.allCases) { Text($0.rawValue).tag($0) }
                }
                .task(id: SearchKey(query: query, scope: app.scope)) { await runSearch() }
                .navigationDestination(for: Route.self) { route in
                    switch route {
                    case .query(let q):
                        QueryResultsView(query: q)
                    case .lineage(let title, let rulerID, let prog):
                        LineageView(title: title, rulerID: rulerID, prog: prog)
                    }
                }
        }
    }

    /// Debounced live search. Cancels in-flight work when the query/scope changes.
    private func runSearch() async {
        let q = query.trimmingCharacters(in: .whitespaces)
        guard !q.isEmpty else { results = []; return }
        try? await Task.sleep(for: .milliseconds(200))
        if Task.isCancelled { return }
        let r = await app.results(for: q)
        if Task.isCancelled { return }
        results = r
    }
}

/// Identity for the debounced search task.
private struct SearchKey: Hashable {
    let query: String
    let scope: SearchScope
}
