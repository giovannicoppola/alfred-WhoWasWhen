import SwiftUI

/// Renders a list of results, or an appropriate empty state.
struct ResultsList: View {
    let results: [SearchResult]
    let isIdle: Bool   // true when there is no active query yet

    var body: some View {
        if results.isEmpty {
            if isIdle {
                ContentUnavailableView {
                    Label("WhoWasWhen", systemImage: "crown")
                } description: {
                    Text("Search a year (e.g. 1789, 177*, -44), a ruler, or an event.")
                }
            } else {
                ContentUnavailableView.search
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
}
