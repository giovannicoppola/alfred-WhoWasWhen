import SwiftUI

/// "Show all «title»" — the lineage of every holder of a title, with the
/// focused ruler highlighted. Offers two renderings of the same rows:
/// the classic list and a visual timeline.
struct LineageView: View {
    let title: String
    let rulerID: Int?
    let prog: Int?

    private enum Mode: String, CaseIterable, Identifiable {
        case list = "List"
        case timeline = "Timeline"
        var id: String { rawValue }
    }

    @Environment(AppModel.self) private var app
    @State private var results: [SearchResult] = []
    @State private var loaded = false
    @State private var mode: Mode = {
        #if DEBUG
        // Automation hook: open directly in timeline mode for screenshots.
        if ProcessInfo.processInfo.environment["WWW_TIMELINE"] != nil { return .timeline }
        #endif
        return .list
    }()

    var body: some View {
        Group {
            switch mode {
            case .list:
                ResultsList(results: results, isIdle: false,
                            scrollToID: focusedID)
            case .timeline:
                LineageTimelineView(results: results, scrollToID: focusedID)
            }
        }
        .navigationTitle(title)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Picker("View", selection: $mode) {
                    Image(systemName: "list.bullet").tag(Mode.list)
                    Image(systemName: "chart.bar.doc.horizontal").tag(Mode.timeline)
                }
                .pickerStyle(.segmented)
                .frame(width: 100)
            }
        }
        .overlay { if !loaded { ProgressView() } }
        .task {
            results = await app.lineageResults(title: title, rulerID: rulerID, prog: prog)
            loaded = true
        }
    }

    private var focusedID: SearchResult.ID? {
        results.first(where: \.isCurrent)?.id
    }
}
