import SwiftUI

/// The Discover tab: a shuffleable featured ruler + event, followed by
/// "centuries ago" anniversary sections (the closest thing to "this day in
/// history" the year-granular database supports).
struct DiscoverView: View {
    @Environment(AppModel.self) private var app
    @State private var featuredRuler: SearchResult?
    @State private var featuredEvent: SearchResult?
    @State private var anniversaries: [AnniversarySection] = []
    @State private var loaded = false

    var body: some View {
        NavigationStack {
            List {
                Section {
                    if let featuredRuler {
                        FeaturedCard(result: featuredRuler, kindLabel: "Featured ruler")
                    }
                    if let featuredEvent {
                        FeaturedCard(result: featuredEvent, kindLabel: "Featured event")
                    }
                } header: {
                    HStack {
                        Text("Featured")
                        Spacer()
                        Button {
                            Task { await shuffle() }
                        } label: {
                            Label("Surprise me", systemImage: "shuffle")
                                .font(.caption.weight(.semibold))
                        }
                    }
                }

                ForEach(anniversaries) { section in
                    Section {
                        ForEach(Array(section.results.enumerated()), id: \.element.id) { idx, result in
                            ResultRow(result: result, index: idx, total: section.results.count)
                        }
                    } header: {
                        HStack(spacing: 6) {
                            Image(systemName: "clock.arrow.circlepath")
                            Text("\(formatNumber(section.yearsAgo)) years ago — \(formatYear(section.year))")
                        }
                        .font(.subheadline.weight(.bold))
                        .foregroundStyle(.indigo)
                        .textCase(nil)
                    }
                }
            }
            .listStyle(.insetGrouped)
            .navigationTitle("Discover")
            .navigationBarTitleDisplayMode(.inline)
            .overlay { if !loaded { ProgressView() } }
            .refreshable { await shuffle() }
            .task { await loadIfNeeded() }
        }
        .toastOverlay(app.toast)
    }

    private func loadIfNeeded() async {
        guard !loaded else { return }
        await app.load()   // wait for the database before the first queries
        await shuffle()
        await buildAnniversaries()
        loaded = true
    }

    private func shuffle() async {
        featuredRuler = await app.randomRuler()
        featuredEvent = await app.randomEvent()
    }

    /// Walks back a century at a time from the current year, keeping the
    /// first centuries that have something to show: up to 3 events plus a
    /// couple of rulers in office that year. Events with an exact date are
    /// preferred, closest to today's date first, so anniversaries land near
    /// their actual day.
    private func buildAnniversaries() async {
        let today = Calendar.current.dateComponents([.month, .day], from: .now)
        let todayKey = (today.month ?? 1) * 31 + (today.day ?? 1)
        func distanceFromToday(_ r: SearchResult) -> Int {
            guard let m = r.startMonth, let d = r.startDay else { return .max }
            let delta = abs(m * 31 + d - todayKey)
            return min(delta, 12 * 31 - delta)   // wrap around new year
        }

        let currentYear = Calendar.current.component(.year, from: .now)
        var sections: [AnniversarySection] = []
        var yearsAgo = 100
        while sections.count < 8 && currentYear - yearsAgo >= -776 {
            let year = currentYear - yearsAgo
            let events = await app.events(inYear: year)
                .sorted { distanceFromToday($0) < distanceFromToday($1) }
                .prefix(3)
            let rulers = await app.rulers(inYear: year).prefix(2)
            let results = Array(events) + Array(rulers)
            if !results.isEmpty {
                sections.append(AnniversarySection(yearsAgo: yearsAgo, year: year,
                                                   results: results))
            }
            yearsAgo += 100
        }
        anniversaries = sections
    }
}

private struct AnniversarySection: Identifiable {
    let yearsAgo: Int
    let year: Int
    let results: [SearchResult]
    var id: Int { year }
}

/// A larger card for the featured ruler/event; tap opens the detail sheet.
struct FeaturedCard: View {
    let result: SearchResult
    let kindLabel: String
    @State private var showDetail = false

    var body: some View {
        Button { showDetail = true } label: {
            VStack(alignment: .leading, spacing: 8) {
                Text(kindLabel.uppercased())
                    .font(.caption2.weight(.bold))
                    .foregroundStyle(Icon.tint(for: result))
                HStack(alignment: .top, spacing: 12) {
                    PortraitView(result: result, size: 56)
                    VStack(alignment: .leading, spacing: 4) {
                        Text(result.title)
                            .font(.headline)
                            .multilineTextAlignment(.leading)
                        if !result.subtitle.isEmpty {
                            Text(result.subtitle)
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                                .lineLimit(3)
                                .multilineTextAlignment(.leading)
                        }
                    }
                }
            }
            .padding(.vertical, 6)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .resultRowActions(for: result)
        .sheet(isPresented: $showDetail) {
            ResultDetailView(result: result).presentationDetents([.medium, .large])
        }
    }
}
