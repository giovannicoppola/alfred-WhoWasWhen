import SwiftUI

/// One result row with the workflow's full action set exposed via swipe
/// gestures, a long-press context menu, and (on tap) a detail sheet.
struct ResultRow: View {
    let result: SearchResult
    let index: Int
    let total: Int

    @State private var showDetail = false

    var body: some View {
        Button { showDetail = true } label: { content }
            .buttonStyle(.plain)
            .resultRowActions(for: result)
            .sheet(isPresented: $showDetail) {
                ResultDetailView(result: result).presentationDetents([.medium, .large])
            }
    }

    private var content: some View {
        HStack(alignment: .top, spacing: 12) {
            // Icon + result-position counter. The counter is a distinct,
            // monospaced badge so it reads as "where you are in the results"
            // rather than data about the ruler (whose own reign progression
            // may also appear, as "27/28", inside the subtitle).
            VStack(spacing: 4) {
                PortraitView(result: result, size: 36)
                Text("\(formatNumber(index + 1))/\(formatNumber(total))")
                    .font(.caption2.weight(.semibold))
                    .monospacedDigit()
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                    .minimumScaleFactor(0.6)
                    // The badge is a fixed-meaning chip; cap its growth so large
                    // accessibility text sizes don't truncate "1/11" to "1/…".
                    .dynamicTypeSize(...DynamicTypeSize.xLarge)
                    .padding(.horizontal, 5)
                    .padding(.vertical, 1)
                    .background(Capsule().fill(Color.secondary.opacity(0.14)))
            }
            .frame(width: 52)
            VStack(alignment: .leading, spacing: 2) {
                Text(result.title)
                    .font(.body.weight(result.isCurrent ? .bold : .regular))
                    .lineLimit(2)
                if !result.subtitle.isEmpty {
                    Text(result.subtitle)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(2)
                }
            }
            Spacer(minLength: 0)
        }
        .contentShape(Rectangle())
    }

}

/// The swipe gestures + long-press context menu every result-style row
/// shares — used by ResultRow and the Discover tab's featured cards.
private struct ResultRowActionsModifier: ViewModifier {
    let result: SearchResult
    @Environment(AppModel.self) private var app
    @Environment(\.openURL) private var openURL

    func body(content: Content) -> some View {
        content
            .swipeActions(edge: .leading, allowsFullSwipe: false) {
                // Single-year results get one travel button, not a
                // duplicated Start/End pair pointing at the same year.
                if result.startYear == result.endYear {
                    Button { app.travel(toYear: result.startYear) } label: {
                        Label(formatYear(result.startYear), systemImage: "arrow.right.to.line")
                    }.tint(.blue)
                } else {
                    Button { app.travel(toYear: result.startYear) } label: {
                        Label("Start \(formatYear(result.startYear))", systemImage: "arrow.backward.to.line")
                    }.tint(.blue)
                    Button { app.travel(toYear: result.endYear) } label: {
                        Label("End \(formatYear(result.endYear))", systemImage: "arrow.forward.to.line")
                    }.tint(.teal)
                }
            }
            .swipeActions(edge: .trailing, allowsFullSwipe: false) {
                FavoriteButton(result: result)
                    .tint(.yellow)
                if let url = result.wikipediaURL {
                    Button { openURL(url) } label: { Label("Wikipedia", systemImage: "safari") }
                        .tint(.indigo)
                }
                if result.kind == .ruler, result.titleName?.isEmpty == false {
                    Button { app.showLineage(for: result) } label: {
                        Label("All", systemImage: "list.bullet")
                    }.tint(.purple)
                }
            }
            .contextMenu { ResultActions(result: result) }
    }
}

extension View {
    func resultRowActions(for result: SearchResult) -> some View {
        modifier(ResultRowActionsModifier(result: result))
    }
}

/// The shared action buttons used in the context menu and the detail sheet.
struct ResultActions: View {
    let result: SearchResult
    @Environment(AppModel.self) private var app
    @Environment(\.openURL) private var openURL

    var body: some View {
        if result.kind == .ruler, let title = result.titleName, !title.isEmpty {
            Button { app.showLineage(for: result) } label: {
                Label("Show all \(titlePluralOrDefault(result.titlePlural, title: title))",
                      systemImage: "list.bullet")
            }
        }
        Button { app.travel(toYear: result.startYear) } label: {
            Label("Travel to \(formatYear(result.startYear))", systemImage: "arrow.backward.to.line")
        }
        if result.endYear != result.startYear {
            Button { app.travel(toYear: result.endYear) } label: {
                Label("Travel to \(formatYear(result.endYear))", systemImage: "arrow.forward.to.line")
            }
        }
        Button { app.copyToClipboard(result) } label: {
            Label("Copy", systemImage: "doc.on.doc")
        }
        FavoriteButton(result: result)
        if let url = result.wikipediaURL {
            Button { openURL(url) } label: { Label("Open Wikipedia", systemImage: "safari") }
        }
        ReportMenu(result: result)
    }
}

/// Add/remove-favorite button shared by swipe actions, context menus, and the
/// detail sheet. Confirms with the standard toast.
struct FavoriteButton: View {
    let result: SearchResult
    @Environment(AppModel.self) private var app
    @Environment(FavoritesStore.self) private var favorites

    var body: some View {
        let saved = favorites.isFavorite(result)
        Button {
            guard let nowSaved = favorites.toggle(result) else { return }
            app.showToast(nowSaved ? "Added to Favorites" : "Removed from Favorites")
        } label: {
            Label(saved ? "Remove Favorite" : "Add to Favorites",
                  systemImage: saved ? "star.slash" : "star")
        }
    }
}
