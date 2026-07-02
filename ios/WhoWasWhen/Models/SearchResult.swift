import Foundation

/// A single row of search output, covering both rulers and events.
/// Mirrors the fields an Alfred item carries so the same actions are possible.
struct SearchResult: Identifiable, Sendable, Hashable {
    enum Kind: Sendable { case ruler, event }

    let id = UUID()
    var kind: Kind
    var title: String
    var subtitle: String

    /// Wikipedia (or fallback) link opened on tap / "Open Wikipedia".
    var wikipediaURL: URL?

    /// Years used by the "travel to start/end year" actions.
    var startYear: Int
    var endYear: Int

    /// For rulers: the title and its plural, used by "Show all «title»".
    var titleName: String?
    var titlePlural: String?
    var rulerID: Int?
    var progrTitle: Int?

    /// For events: the stable database key (used by Favorites).
    var eventID: Int? = nil

    /// For events with an exact date: the calendar month/day of the start
    /// ("On this day", date-aware anniversaries). Nil for undated events.
    var startMonth: Int? = nil
    var startDay: Int? = nil

    /// Marks the focused ruler in a lineage list (the 🌟 in the workflow).
    var isCurrent: Bool = false

    /// Asset name (bundled PNG) or SF Symbol fallback resolved in the view.
    var iconAsset: String?

    /// Plain-text rendering for the "Copy" action.
    var copyText: String { "\(title): \(subtitle)" }
}

/// Information about one reign period, used to build ruler subtitles.
struct PeriodInfo: Sendable {
    var period: String
    var notes: String
    var title: String
    var startYear: Int
    var endYear: Int
    var progrTitle: Int
}

enum TitleRanking {
    /// Lower number = higher priority. Ported from the Go `getTitleRank`.
    static func rank(_ title: String) -> Int {
        let t = title.lowercased()
        if t.contains("roman emperor") { return 1 }
        if t.contains("byzantine emperor") { return 2 }
        if t.contains("holy roman emperor") { return 3 }
        if t.contains("king") || t.contains("queen") { return 10 }
        if t.contains("emperor") { return 15 }
        if t.contains("tsar") || t.contains("czar") { return 20 }
        if t.contains("president") { return 30 }
        if t.contains("prime minister") || t.contains("premier") { return 35 }
        if t.contains("chancellor") { return 40 }
        if t.contains("duke") || t.contains("duchess") { return 50 }
        if t.contains("pope") { return 55 }
        if t.contains("patriarch") { return 60 }
        if t.contains("consul") { return 100 }
        if t.contains("tribune") { return 110 }
        if t.contains("dictator") { return 120 }
        return 1000
    }
}

/// Builds the multi-period ruler subtitle, e.g.
/// "Personal Name, Title (1500-1510; 1512, note); Other Title (1520)".
/// Ported from the Go `formatSubtitle`.
func formatRulerSubtitle(periods: [PeriodInfo], personalName: String?) -> String {
    var groups: [String: [PeriodInfo]] = [:]
    for p in periods { groups[p.title, default: []].append(p) }

    let sortedGroups = groups.sorted { TitleRanking.rank($0.key) < TitleRanking.rank($1.key) }

    var titleParts: [String] = []
    for (title, groupPeriods) in sortedGroups {
        var periodParts: [String] = []
        for p in groupPeriods {
            var periodStr = p.startYear == p.endYear
                ? formatYear(p.startYear)
                : "\(formatYear(p.startYear))-\(formatYear(p.endYear))"
            if !p.notes.isEmpty && p.notes != "," {
                periodStr += ", \(p.notes)"
            }
            periodParts.append(periodStr)
        }
        titleParts.append("\(title) (\(periodParts.joined(separator: "; ")))")
    }

    let titlesString = titleParts.joined(separator: "; ")
    if let name = personalName, !name.isEmpty {
        return "\(name), \(titlesString)"
    }
    return titlesString
}

/// Plural title with the same fallback as the Go `getTitlePlural`.
func titlePluralOrDefault(_ plural: String?, title: String) -> String {
    if let p = plural, !p.isEmpty { return p }
    return title + "s"
}
