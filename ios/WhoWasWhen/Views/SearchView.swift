import SwiftUI

/// Root screen: a search box at the top with live results, mirroring the
/// Alfred workflow. Year jumps and "show all" push onto the navigation stack.
struct SearchView: View {
    @Environment(AppModel.self) private var app
    @State private var query = ""
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
                // An explicit way to drop the keyboard (in addition to scrolling
                // the results), for when a query returns too few rows to scroll.
                .toolbar {
                    ToolbarItemGroup(placement: .keyboard) {
                        Spacer()
                        Button("Done") {
                            UIApplication.shared.sendAction(
                                #selector(UIResponder.resignFirstResponder),
                                to: nil, from: nil, for: nil)
                        }
                    }
                }
                .task(id: SearchKey(query: query, scope: app.scope)) { await runSearch() }
                #if DEBUG
                // Automation hook: pre-fill the search box for screenshots.
                .task {
                    if let q = ProcessInfo.processInfo.environment["WWW_QUERY"], query.isEmpty {
                        query = q
                    }
                }
                #endif
                .navigationDestination(for: Route.self) { route in
                    switch route {
                    case .query(let q):
                        QueryResultsView(query: q)
                    case .lineage(let title, let rulerID, let prog):
                        LineageView(title: title, rulerID: rulerID, prog: prog)
                    }
                }
        }
        .toastOverlay(app.toast)
    }

    /// Debounced live search. Cancels in-flight work when the query/scope changes.
    private func runSearch() async {
        let q = query.trimmingCharacters(in: .whitespaces)
        guard !q.isEmpty else { results = []; return }
        try? await Task.sleep(for: .milliseconds(200))
        if Task.isCancelled { return }
        let t0 = Date()
        print("[WWW] search '\(q)' starting…")
        let r = await app.results(for: q)
        print("[WWW] search '\(q)' -> \(r.count) rows in \(Date().timeIntervalSince(t0))s")
        if Task.isCancelled { return }
        results = r
    }
}

/// Identity for the debounced search task.
private struct SearchKey: Hashable {
    let query: String
    let scope: SearchScope
}

/// A small, self-dismissing confirmation banner shown over the content.
struct ToastBanner: View {
    let text: String

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: "checkmark.circle.fill")
            Text(text).font(.subheadline.weight(.semibold))
        }
        .foregroundStyle(.white)
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .background(Capsule().fill(.black.opacity(0.8)))
        .shadow(radius: 6, y: 2)
        .accessibilityElement(children: .combine)
    }
}

extension View {
    /// Overlays a self-dismissing toast at the bottom. Apply it inside each
    /// presentation layer (root and any sheet) so the banner renders in front
    /// of that layer rather than behind a covering sheet.
    func toastOverlay(_ message: String?) -> some View {
        overlay(alignment: .bottom) {
            if let message {
                ToastBanner(text: message)
                    .padding(.bottom, 32)
                    .transition(.move(edge: .bottom).combined(with: .opacity))
            }
        }
        .animation(.spring(duration: 0.3), value: message)
    }
}
