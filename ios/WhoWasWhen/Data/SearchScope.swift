import Foundation

/// Filters the search the way the Alfred workflow's "Show Events?" option and
/// the `--e` flag do: everything, rulers only, or events only.
enum SearchScope: String, CaseIterable, Identifiable, Sendable {
    case all = "All"
    case rulers = "Rulers"
    case events = "Events"

    var id: String { rawValue }
}

extension Database {
    /// Top-level dispatch mirroring the workflow's `main`: decide between a
    /// year search and a text search, honoring the scope filter.
    func search(query: String, scope: SearchScope) -> [SearchResult] {
        let parsed = QueryParser.parse(query)
        guard parsed.yearTerm != nil || !parsed.textTerms.isEmpty else { return [] }

        let includeRulers = scope != .events
        let includeEvents = scope != .rulers

        if let yearTerm = parsed.yearTerm {
            return searchByYear(yearTerm: yearTerm, textTerms: parsed.textTerms,
                                includeRulers: includeRulers, includeEvents: includeEvents)
        }
        return searchByText(terms: parsed.textTerms,
                            includeRulers: includeRulers, includeEvents: includeEvents)
    }
}
