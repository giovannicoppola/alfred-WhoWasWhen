import SwiftUI

/// One result row with the workflow's full action set exposed via swipe
/// gestures, a long-press context menu, and (on tap) a detail sheet.
struct ResultRow: View {
    let result: SearchResult
    let index: Int
    let total: Int

    @Environment(AppModel.self) private var app
    @Environment(\.openURL) private var openURL
    @State private var showDetail = false

    var body: some View {
        Button { showDetail = true } label: { content }
            .buttonStyle(.plain)
            .swipeActions(edge: .leading, allowsFullSwipe: false) {
                Button { app.travel(toYear: result.startYear) } label: {
                    Label("Start \(formatYear(result.startYear))", systemImage: "arrow.backward.to.line")
                }.tint(.blue)
                Button { app.travel(toYear: result.endYear) } label: {
                    Label("End \(formatYear(result.endYear))", systemImage: "arrow.forward.to.line")
                }.tint(.teal)
            }
            .swipeActions(edge: .trailing, allowsFullSwipe: false) {
                if result.wikipediaURL != nil {
                    Button { openWikipedia() } label: { Label("Wikipedia", systemImage: "safari") }
                        .tint(.indigo)
                }
                if canShowLineage {
                    Button { app.showLineage(for: result) } label: {
                        Label("All", systemImage: "list.bullet")
                    }.tint(.purple)
                }
            }
            .contextMenu { ResultActions(result: result) }
            .sheet(isPresented: $showDetail) {
                ResultDetailView(result: result).presentationDetents([.medium, .large])
            }
    }

    private var content: some View {
        HStack(spacing: 12) {
            Image(systemName: Icon.symbol(for: result))
                .font(.title3)
                .foregroundStyle(Icon.tint(for: result))
                .frame(width: 30)
            VStack(alignment: .leading, spacing: 2) {
                Text(result.title)
                    .font(.body.weight(result.isCurrent ? .bold : .regular))
                    .lineLimit(2)
                if !result.subtitle.isEmpty {
                    Text("\(formatNumber(index + 1))/\(formatNumber(total))  \(result.subtitle)")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(2)
                }
            }
            Spacer(minLength: 0)
        }
        .contentShape(Rectangle())
    }

    private var canShowLineage: Bool {
        result.kind == .ruler && (result.titleName?.isEmpty == false)
    }

    private func openWikipedia() {
        if let url = result.wikipediaURL { openURL(url) }
    }
}

/// The shared action buttons used in the context menu and the detail sheet.
struct ResultActions: View {
    let result: SearchResult
    @Environment(AppModel.self) private var app
    @Environment(\.openURL) private var openURL

    var body: some View {
        if let url = result.wikipediaURL {
            Button { openURL(url) } label: { Label("Open Wikipedia", systemImage: "safari") }
        }
        Button { app.travel(toYear: result.startYear) } label: {
            Label("Travel to \(formatYear(result.startYear))", systemImage: "arrow.backward.to.line")
        }
        if result.endYear != result.startYear {
            Button { app.travel(toYear: result.endYear) } label: {
                Label("Travel to \(formatYear(result.endYear))", systemImage: "arrow.forward.to.line")
            }
        }
        if result.kind == .ruler, let title = result.titleName, !title.isEmpty {
            Button { app.showLineage(for: result) } label: {
                Label("Show all \(titlePluralOrDefault(result.titlePlural, title: title))",
                      systemImage: "list.bullet")
            }
        }
        Button { UIPasteboard.general.string = result.copyText } label: {
            Label("Copy", systemImage: "doc.on.doc")
        }
    }
}
