import SwiftUI

/// Renders a list of results, or an appropriate empty state.
/// When `yearHeader` is set (a year search), the year is shown once as a
/// pinned header instead of being repeated on every row.
struct ResultsList: View {
    let results: [SearchResult]
    let isIdle: Bool             // true when there is no active query yet
    var yearHeader: String? = nil
    /// When set, the list scrolls this row into view once on appear (used by
    /// the lineage view to focus the currently selected ruler).
    var scrollToID: SearchResult.ID? = nil

    var body: some View {
        if results.isEmpty {
            if isIdle {
                IdleHome()
            } else {
                ContentUnavailableView.search
            }
        } else {
            ScrollViewReader { proxy in
                List {
                    if let yearHeader {
                        Section {
                            rows
                        } header: {
                            YearHeader(text: yearHeader)
                        }
                    } else {
                        rows
                    }
                }
                .listStyle(.plain)
                .onAppear {
                    if let scrollToID {
                        proxy.scrollTo(scrollToID, anchor: .center)
                    }
                }
            }
        }
    }

    @ViewBuilder private var rows: some View {
        ForEach(Array(results.enumerated()), id: \.element.id) { idx, result in
            ResultRow(result: result, index: idx, total: results.count)
        }
    }
}

/// The home/empty state, showing the app logo and a hint.
private struct IdleHome: View {
    var body: some View {
        VStack(spacing: 18) {
            Image("AppLogo")
                .resizable()
                .scaledToFit()
                .frame(width: 104, height: 104)
            Text("WhoWasWhen")
                .font(.title2.weight(.bold))
            VStack(spacing: 6) {
                Text("Search")
                Text("a year (e.g. 1789, 177*, -44)")
                Text("a ruler")
                Text("or an event")
            }
            .font(.subheadline)
            .foregroundStyle(.secondary)
            .multilineTextAlignment(.center)
            .padding(.horizontal, 44)
            ReportMenu(label: "Report an issue or suggest data", systemImage: "plus.bubble")
                .font(.footnote)
                .padding(.top, 8)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

/// The pinned year banner at the top of year-search results.
private struct YearHeader: View {
    let text: String

    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: "clock.arrow.circlepath")
            Text(text)
        }
        .font(.title3.weight(.bold))
        .foregroundStyle(.indigo)
        .textCase(nil)
        .padding(.vertical, 4)
    }
}
