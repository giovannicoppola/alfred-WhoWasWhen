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
                        ResultRow(result: section.result, index: 0, total: 1, showCounter: false)
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

    /// Walks back a century at a time from the current year, keeping the first
    /// centuries that have something to show. Each section surfaces a single
    /// highlight — an event or a person from that year — chosen deterministically
    /// from today's date, so the picks are stable through the day but rotate to
    /// new ones each day rather than showing the same thing year-round.
    private func buildAnniversaries() async {
        let cal = Calendar.current
        let dayOfYear = cal.ordinality(of: .day, in: .year, for: .now) ?? 0
        let currentYear = cal.component(.year, from: .now)
        // Stable within a calendar day, changes daily.
        let daySeed = currentYear &+ dayOfYear

        var sections: [AnniversarySection] = []
        var yearsAgo = 100
        while sections.count < 8 && currentYear - yearsAgo >= -776 {
            let year = currentYear - yearsAgo
            let events = await app.events(inYear: year)
            // Events first (usually the more notable anniversaries); cap the
            // rulers so a year full of Roman consuls doesn't crowd the rotation.
            let rulers = await app.rulers(inYear: year).prefix(6)
            let pool = events + Array(rulers)
            if !pool.isEmpty {
                // Offset per century so the sections don't all land on the same
                // index on a given day.
                let pick = pool[(daySeed &+ yearsAgo) % pool.count]
                sections.append(AnniversarySection(yearsAgo: yearsAgo, year: year, result: pick))
            }
            yearsAgo += 100
        }
        anniversaries = sections
    }
}

private struct AnniversarySection: Identifiable {
    let yearsAgo: Int
    let year: Int
    let result: SearchResult
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
