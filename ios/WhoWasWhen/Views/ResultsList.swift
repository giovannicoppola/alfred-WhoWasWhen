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

/// The home/empty state: the app logo, a search hint, and — when the
/// database knows an event dated today — an "On this day" card.
private struct IdleHome: View {
    @Environment(AppModel.self) private var app
    @State private var onThisDay: SearchResult?

    var body: some View {
        VStack(spacing: 0) {
            Spacer()
            VStack(spacing: 18) {
                Image("AppLogo")
                    .resizable()
                    .scaledToFit()
                    .frame(width: 104, height: 104)
                Text("WhoWasWhen")
                    .font(.title2.weight(.bold))
                VStack(alignment: .leading, spacing: 6) {
                    Text("Search:")
                    VStack(alignment: .leading, spacing: 6) {
                        Text("a year (e.g. 1789, 177*, -44)")
                        Text("a ruler")
                        Text("or an event")
                    }
                    .padding(.leading, 20)
                }
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .padding(.horizontal, 44)
            }
            if let onThisDay {
                OnThisDayCard(result: onThisDay)
                    .padding(.top, 28)
            }
            Spacer()
            ReportMenu(label: "Report an issue or suggest data", systemImage: "plus.bubble")
                .font(.footnote)
                .padding(.bottom, 8)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .task { await loadOnThisDay() }
    }

    private func loadOnThisDay() async {
        let matches = await app.eventsOnToday()
        guard !matches.isEmpty else { return }
        // Several events can share today's date; rotate deterministically so
        // the card is stable within a day but varies across years.
        let cal = Calendar.current
        let n = (cal.component(.year, from: .now))
            &+ (cal.ordinality(of: .day, in: .year, for: .now) ?? 0)
        onThisDay = matches[n % matches.count]
    }
}

/// A tappable card highlighting an event that happened on today's date.
private struct OnThisDayCard: View {
    let result: SearchResult
    @State private var showDetail = false

    var body: some View {
        Button { showDetail = true } label: {
            VStack(alignment: .leading, spacing: 8) {
                HStack(spacing: 6) {
                    Image(systemName: "calendar.badge.clock")
                    Text("On this day — \(Date.now.formatted(.dateTime.month(.wide).day()))")
                        .textCase(.uppercase)
                }
                .font(.caption2.weight(.bold))
                .foregroundStyle(.indigo)
                HStack(alignment: .top, spacing: 12) {
                    PortraitView(result: result, size: 44)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(result.title)
                            .font(.subheadline.weight(.semibold))
                            .lineLimit(2)
                            .multilineTextAlignment(.leading)
                        if !result.subtitle.isEmpty {
                            Text(result.subtitle)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                                .lineLimit(2)
                                .multilineTextAlignment(.leading)
                        }
                    }
                    Spacer(minLength: 0)
                }
            }
            .padding(14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(RoundedRectangle(cornerRadius: 14)
                .fill(Color(.secondarySystemBackground)))
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .padding(.horizontal, 24)
        .sheet(isPresented: $showDetail) {
            ResultDetailView(result: result).presentationDetents([.medium, .large])
        }
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
