import Foundation

/// Parses the search box into the same three modes as the Alfred workflow:
/// a year/wildcard/range term, free-text terms, or a mix of both.
enum QueryParser {

    /// A parsed query, ready to hand to the database layer.
    struct Parsed {
        /// The year-like term, if the query contained one (e.g. "1789", "177*", "1500-1600", "-44").
        var yearTerm: String?
        /// Remaining free-text terms (e.g. ["france"]).
        var textTerms: [String]
    }

    /// Matches a year, a BC year, a wildcard year, or a range. Mirrors the Go
    /// `isNumberLike` regex: `^-?\d*\**$|^-?\d*\**--?\d*\**$`
    private static let numberLike = try! NSRegularExpression(
        pattern: #"^-?\d*\**$|^-?\d*\**--?\d*\**$"#)

    static func isNumberLike(_ term: String) -> Bool {
        guard !term.isEmpty else { return false }
        // A bare "-" or "*" alone is not a useful year term.
        if term == "-" || term.allSatisfy({ $0 == "*" }) { return false }
        let range = NSRange(term.startIndex..<term.endIndex, in: term)
        return numberLike.firstMatch(in: term, range: range) != nil
    }

    static func parse(_ raw: String) -> Parsed {
        let normalized = normalizeSearchInput(raw)
        let terms = normalized.split(whereSeparator: { $0 == " " }).map(String.init)

        var yearTerm: String?
        var textTerms: [String] = []
        for term in terms {
            if yearTerm == nil && isNumberLike(term) {
                yearTerm = term
            } else {
                textTerms.append(term)
            }
        }
        return Parsed(yearTerm: yearTerm, textTerms: textTerms)
    }

    /// Resolved bounds for a year term, used to build the SQL `WHERE` clause.
    enum YearClause {
        /// `y.year BETWEEN lower AND upper`
        case range(lower: Int, upper: Int)
        /// `CAST(y.year AS TEXT) LIKE 'prefix____'` for wildcard searches like "177*".
        case like(pattern: String)
    }

    /// Translates a year term into a SQL clause, mirroring the Go `byYear` logic.
    static func yearClause(for term: String) -> YearClause {
        let asteriskCount = term.reversed().prefix(while: { $0 == "*" }).count

        // Range: a single internal dash, not a leading minus (e.g. "1500-1600").
        if asteriskCount == 0 {
            if let r = parseRange(term) {
                return .range(lower: r.0, upper: r.1)
            }
        }

        // Wildcard or plain year -> LIKE on the textual year.
        let prefix = String(term.dropLast(asteriskCount))
        let pattern = prefix + String(repeating: "_", count: asteriskCount)
        return .like(pattern: pattern)
    }

    /// Parses "1500-1600" or "-100--50" style ranges. Returns nil for single years.
    private static func parseRange(_ term: String) -> (Int, Int)? {
        // Single internal dash, no leading minus: "1500-1600"
        if !term.hasPrefix("-"), term.filter({ $0 == "-" }).count == 1 {
            let parts = term.split(separator: "-", maxSplits: 1).map(String.init)
            if parts.count == 2, let a = Int(parts[0]), let b = Int(parts[1]) {
                return (min(a, b), max(a, b))
            }
        }
        // Ranges that include a negative bound: "-100--50", "-44-100"
        if term.filter({ $0 == "-" }).count > 1 {
            if let r = matchSignedRange(term) {
                return (min(r.0, r.1), max(r.0, r.1))
            }
        }
        return nil
    }

    private static let signedRange = try! NSRegularExpression(
        pattern: #"^(-?\d+)-(-?\d+)$"#)

    private static func matchSignedRange(_ term: String) -> (Int, Int)? {
        let range = NSRange(term.startIndex..<term.endIndex, in: term)
        guard let m = signedRange.firstMatch(in: term, range: range),
              let r1 = Range(m.range(at: 1), in: term),
              let r2 = Range(m.range(at: 2), in: term),
              let a = Int(term[r1]), let b = Int(term[r2]) else { return nil }
        return (a, b)
    }

    /// Whether a year term denotes a span (range or wildcard) rather than a single year.
    static func isSpan(_ term: String) -> Bool {
        if term.contains("*") { return true }
        return parseRange(term) != nil
    }

    /// The year label to show once at the top of year-search results
    /// (e.g. "1789", "44 BC", "177*", "1500-1600"), or nil for a text-only query.
    static func displayYear(for query: String) -> String? {
        guard let term = parse(query).yearTerm else { return nil }
        if term.contains("*") { return term }                 // wildcard, e.g. "177*"
        if let r = parseRange(term) {                         // range — show sorted, formatted bounds
            return "\(formatYear(r.0))–\(formatYear(r.1))"
        }
        if let y = Int(term) { return formatYear(y) }
        return term
    }
}

/// Formats a year with BC/AD, matching the Go `formatYear`.
func formatYear(_ year: Int) -> String {
    year < 0 ? "\(-year) BC" : "\(year)"
}
