import SwiftUI

/// Detail sheet shown when a result row is tapped: full text plus every action.
struct ResultDetailView: View {
    let result: SearchResult
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            List {
                Section {
                    HStack(alignment: .top, spacing: 12) {
                        Image(systemName: Icon.symbol(for: result))
                            .font(.largeTitle)
                            .foregroundStyle(Icon.tint(for: result))
                        VStack(alignment: .leading, spacing: 6) {
                            Text(result.title).font(.headline)
                            if !result.subtitle.isEmpty {
                                Text(result.subtitle).font(.subheadline).foregroundStyle(.secondary)
                            }
                        }
                    }
                    .padding(.vertical, 4)
                }
                Section("Actions") {
                    // Tapping an action that navigates should dismiss the sheet first.
                    ResultActionsList(result: result, dismiss: { dismiss() })
                }
            }
            .navigationTitle("Details")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }
}

/// Action rows for the detail sheet (dismisses before pushing navigation).
private struct ResultActionsList: View {
    let result: SearchResult
    let dismiss: () -> Void
    @Environment(AppModel.self) private var app
    @Environment(\.openURL) private var openURL

    var body: some View {
        if let url = result.wikipediaURL {
            Button { openURL(url) } label: { Label("Open Wikipedia", systemImage: "safari") }
        }
        Button {
            dismiss()
            app.travel(toYear: result.startYear)
        } label: {
            Label("Travel to \(formatYear(result.startYear))", systemImage: "arrow.backward.to.line")
        }
        if result.endYear != result.startYear {
            Button {
                dismiss()
                app.travel(toYear: result.endYear)
            } label: {
                Label("Travel to \(formatYear(result.endYear))", systemImage: "arrow.forward.to.line")
            }
        }
        if result.kind == .ruler, let title = result.titleName, !title.isEmpty {
            Button {
                dismiss()
                app.showLineage(for: result)
            } label: {
                Label("Show all \(titlePluralOrDefault(result.titlePlural, title: title))",
                      systemImage: "list.bullet")
            }
        }
        Button { UIPasteboard.general.string = result.copyText } label: {
            Label("Copy to clipboard", systemImage: "doc.on.doc")
        }
    }
}
