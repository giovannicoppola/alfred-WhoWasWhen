import SwiftUI

/// Detail sheet shown when a result row is tapped: full text plus every action.
struct ResultDetailView: View {
    let result: SearchResult
    @Environment(\.dismiss) private var dismiss
    @Environment(AppModel.self) private var app
    @Environment(FavoritesStore.self) private var favorites

    /// The full span of the ruler's title, for the mini reign-position bar.
    @State private var eraSpan: ClosedRange<Int>?
    /// First-paragraph summary fetched from Wikipedia (nil offline).
    @State private var extract: String?

    var body: some View {
        NavigationStack {
            List {
                Section {
                    HStack(alignment: .top, spacing: 12) {
                        PortraitView(result: result, size: 64)
                        VStack(alignment: .leading, spacing: 6) {
                            Text(result.title).font(.headline)
                            if !result.subtitle.isEmpty {
                                Text(result.subtitle).font(.subheadline).foregroundStyle(.secondary)
                            }
                        }
                    }
                    .padding(.vertical, 4)

                    // Where this reign sits within the title's whole history.
                    if let eraSpan, let title = result.titleName {
                        ReignSpanBar(eraLabel: "all \(titlePluralOrDefault(result.titlePlural, title: title))",
                                     reignStart: result.startYear,
                                     reignEnd: result.endYear,
                                     era: eraSpan)
                            .padding(.vertical, 4)
                    }
                }
                if let extract {
                    Section("About") {
                        VStack(alignment: .leading, spacing: 6) {
                            Text(extract).font(.subheadline)
                            Text("From Wikipedia")
                                .font(.caption2)
                                .foregroundStyle(.tertiary)
                        }
                        .padding(.vertical, 2)
                    }
                }
                Section("Actions") {
                    // Tapping an action that navigates should dismiss the sheet first.
                    ResultActionsList(result: result, dismiss: { dismiss() })
                }
            }
            .navigationTitle("Details")
            .navigationBarTitleDisplayMode(.inline)
            .task {
                if result.kind == .ruler, let title = result.titleName {
                    eraSpan = await app.titleSpan(title)
                }
                if let url = result.wikipediaURL {
                    extract = await WikipediaClient.shared.summary(for: url)?.extract
                }
            }
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    // The filled/empty star mirrors the saved state directly.
                    Button {
                        guard let saved = favorites.toggle(result) else { return }
                        app.showToast(saved ? "Added to Favorites" : "Removed from Favorites")
                    } label: {
                        Image(systemName: favorites.isFavorite(result) ? "star.fill" : "star")
                            .foregroundStyle(.yellow)
                    }
                    .accessibilityLabel(favorites.isFavorite(result)
                                        ? "Remove from Favorites" : "Add to Favorites")
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") { dismiss() }
                }
            }
        }
        .toastOverlay(app.toast)
    }
}

/// Action rows for the detail sheet (dismisses before pushing navigation).
private struct ResultActionsList: View {
    let result: SearchResult
    let dismiss: () -> Void
    @Environment(AppModel.self) private var app
    @Environment(\.openURL) private var openURL

    var body: some View {
        // The list of rulers (lineage) is the primary action, so it comes first.
        if result.kind == .ruler, let title = result.titleName, !title.isEmpty {
            Button {
                dismiss()
                app.showLineage(for: result)
            } label: {
                Label("Show all \(titlePluralOrDefault(result.titlePlural, title: title))",
                      systemImage: "list.bullet")
            }
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
        Button { app.copyToClipboard(result) } label: {
            Label("Copy to clipboard", systemImage: "doc.on.doc")
        }
        // Wikipedia link last.
        if let url = result.wikipediaURL {
            Button { openURL(url) } label: { Label("Open Wikipedia", systemImage: "safari") }
        }
        ReportMenu(result: result)
    }
}
