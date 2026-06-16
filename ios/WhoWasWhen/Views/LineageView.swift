import SwiftUI

/// "Show all «title»" — the lineage of every holder of a title, with the
/// focused ruler highlighted, starting a few entries before them.
struct LineageView: View {
    let title: String
    let rulerID: Int?
    let prog: Int?

    @Environment(AppModel.self) private var app
    @State private var results: [SearchResult] = []
    @State private var loaded = false

    var body: some View {
        ResultsList(results: results, isIdle: false)
            .navigationTitle(title)
            .navigationBarTitleDisplayMode(.inline)
            .overlay { if !loaded { ProgressView() } }
            .task {
                results = await app.lineageResults(title: title, rulerID: rulerID, prog: prog)
                loaded = true
            }
    }
}
