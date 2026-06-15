import Foundation
import SQLite3

private let SQLITE_TRANSIENT = unsafeBitCast(-1, to: sqlite3_destructor_type.self)

/// Read-only access to the WhoWasWhen SQLite database.
///
/// Ports the query logic from the Alfred workflow (`pkg/ruler-query.go`):
/// search by year, search rulers + events by text, and list a title's lineage.
/// All access is confined to this actor.
actor Database {
    enum DBError: Error { case openFailed(String), prepareFailed(String) }

    // Confined to this actor in practice; `nonisolated(unsafe)` lets `deinit`
    // close the handle under Swift 6 strict concurrency.
    private nonisolated(unsafe) var handle: OpaquePointer?

    init(path: String) throws {
        var db: OpaquePointer?
        // Open read-only; the app never mutates the data.
        let flags = SQLITE_OPEN_READONLY | SQLITE_OPEN_FULLMUTEX
        guard sqlite3_open_v2(path, &db, flags, nil) == SQLITE_OK, let db else {
            let msg = db.map { String(cString: sqlite3_errmsg($0)) } ?? "unknown"
            sqlite3_close(db)
            throw DBError.openFailed(msg)
        }
        self.handle = db
        Database.registerFoldFunction(db)
    }

    deinit { sqlite3_close(handle) }

    /// Registers the accent/case-insensitive `fold()` SQL function used by search,
    /// matching the Go workflow's custom SQLite function.
    private nonisolated static func registerFoldFunction(_ db: OpaquePointer) {
        sqlite3_create_function_v2(
            db, "fold", 1, SQLITE_UTF8 | SQLITE_DETERMINISTIC, nil,
            { ctx, _, argv in
                guard let argv, let c = sqlite3_value_text(argv[0]) else {
                    sqlite3_result_text(ctx, "", -1, SQLITE_TRANSIENT)
                    return
                }
                let folded = foldForSearch(String(cString: c))
                sqlite3_result_text(ctx, folded, -1, SQLITE_TRANSIENT)
            },
            nil, nil, nil)
    }

    // MARK: - Public queries

    /// Search by a year term, optionally narrowed by text terms.
    /// Returns rulers active that year plus matching events, ordered by year.
    func searchByYear(yearTerm: String, textTerms: [String],
                      includeRulers: Bool, includeEvents: Bool) -> [SearchResult] {
        var results: [SearchResult] = []
        if includeRulers { results += rulersByYear(yearTerm: yearTerm, textTerms: textTerms) }
        if includeEvents { results += eventsByYear(yearTerm: yearTerm, textTerms: textTerms) }
        return results
    }

    /// Search rulers and (optionally) events by free text.
    func searchByText(terms: [String], includeRulers: Bool, includeEvents: Bool) -> [SearchResult] {
        var results: [SearchResult] = []
        if includeRulers { results += rulersByText(terms: terms) }
        if includeEvents { results += eventsByText(terms: terms) }
        return results
    }

    /// All holders of a title, ordered by progression, with `focusRulerID`/`focusProg`
    /// marked as current — the "Show all «title»" lineage view.
    func lineage(title: String, focusRulerID: Int?, focusProg: Int?) -> [SearchResult] {
        let sql = """
            SELECT ru.rulerID, ru.name, ru.personal_name, ru.epithet, ru.wikipedia,
                   ru.biography, per.progrTitle, per.period, per.startYear, per.endYear,
                   per.notes, t.title, t.maxCount, t.titlePlural
            FROM rulers ru
            JOIN byPeriod per ON ru.rulerID = per.rulerID
            JOIN titles t ON per.titleID = t.titleID
            WHERE t.title = ?
            ORDER BY per.progrTitle ASC;
            """
        guard let stmt = prepare(sql) else { return [] }
        defer { sqlite3_finalize(stmt) }
        bindText(stmt, 1, title)

        var rows: [SearchResult] = []
        var focusIndex: Int?
        while sqlite3_step(stmt) == SQLITE_ROW {
            let rulerID = col(stmt, 0).int
            let name = col(stmt, 1).string
            let personal = col(stmt, 2).optString
            let wiki = col(stmt, 4).optString
            let biography = col(stmt, 5).optString
            let prog = col(stmt, 6).int
            let period = col(stmt, 7).string
            let startYear = col(stmt, 8).int
            let endYear = col(stmt, 9).int
            let notes = col(stmt, 10).optString ?? ""
            let titleName = col(stmt, 11).string
            let maxCount = col(stmt, 12).int
            let titlePlural = col(stmt, 13).optString

            let isCurrent = focusRulerID == rulerID && focusProg == prog
            if isCurrent { focusIndex = rows.count }

            let star = (focusRulerID == rulerID) ? " 🌟" : ""
            let displayTitle = "\(name) (\(period))\(star)"

            let counter = "\(formatNumber(prog))/\(formatNumber(maxCount))"
            let subtitle: String
            if let bio = biography, !bio.isEmpty {
                subtitle = "\(counter) \(bio)"
            } else {
                let notePart = (notes.isEmpty || notes == ",") ? "" : notes
                if let pn = personal, !pn.isEmpty {
                    subtitle = "\(counter) \(pn), \(titleName) \(notePart)"
                } else {
                    subtitle = "\(counter) \(titleName) \(notePart)"
                }
            }

            rows.append(SearchResult(
                kind: .ruler, title: displayTitle, subtitle: subtitle,
                wikipediaURL: wikipediaLink(wiki, name: name),
                startYear: startYear, endYear: endYear,
                titleName: titleName, titlePlural: titlePlural,
                rulerID: rulerID, progrTitle: prog, isCurrent: isCurrent,
                iconAsset: titleName))
        }

        // Match the workflow: start the window 3 before the focused ruler.
        if let idx = focusIndex {
            let start = max(0, idx - 3)
            return Array(rows[start...])
        }
        return rows
    }

    // MARK: - Ruler / event queries

    private func rulersByYear(yearTerm: String, textTerms: [String]) -> [SearchResult] {
        let yc = QueryParser.yearClause(for: yearTerm)
        let (yearSQL, yearParams) = yearClauseSQL(yc, yearColumn: "y.year")
        let (textSQL, textParams) = foldedTextSQL(columns: ["r.name", "t.title"], terms: textTerms)

        var sql = """
            SELECT r.rulerID, r.name, r.personal_name, r.epithet, r.wikipedia, r.notes,
                   per.progrTitle, per.period, per.startYear, per.endYear, per.notes,
                   t.title, t.maxCount, t.titlePlural, y.year
            FROM byYear rt
            JOIN byPeriod per ON rt.periodID = per.periodID
            JOIN rulers r ON per.rulerID = r.rulerID
            JOIN titles t ON per.titleID = t.titleID
            JOIN years y ON rt.yearID = y.yearID
            WHERE \(yearSQL)
            """
        if !textTerms.isEmpty { sql += " AND \(textSQL)" }
        sql += " GROUP BY per.periodID ORDER BY y.year;"

        guard let stmt = prepare(sql) else { return [] }
        defer { sqlite3_finalize(stmt) }
        var idx: Int32 = 1
        for p in yearParams { bindAny(stmt, idx, p); idx += 1 }
        for p in textParams { bindText(stmt, idx, p); idx += 1 }

        let span = QueryParser.isSpan(yearTerm)
        var rows: [SearchResult] = []
        while sqlite3_step(stmt) == SQLITE_ROW {
            let rulerID = col(stmt, 0).int
            let name = col(stmt, 1).string
            let personal = col(stmt, 2).optString
            let epithet = col(stmt, 3).optString
            let wiki = col(stmt, 4).optString
            let prog = col(stmt, 6).int
            let period = col(stmt, 7).string
            let startYear = col(stmt, 8).int
            let endYear = col(stmt, 9).int
            let notes = col(stmt, 10).optString ?? ""
            let titleName = col(stmt, 11).string
            let maxCount = col(stmt, 12).int
            let titlePlural = col(stmt, 13).optString
            let year = col(stmt, 14).int

            let yearString = span ? yearTerm : formatYear(year)
            let epithetString = (epithet?.isEmpty == false) ? " (\(epithet!))" : ""
            let displayTitle = "\(yearString): \(name)\(epithetString) (\(period))"
            let counter = "\(formatNumber(prog))/\(formatNumber(maxCount))"
            let subtitle = (personal?.isEmpty == false)
                ? "\(personal!), \(titleName) (\(counter)) \(notes)"
                : "\(titleName) (\(counter)) \(notes)"

            rows.append(SearchResult(
                kind: .ruler, title: displayTitle, subtitle: subtitle,
                wikipediaURL: wikipediaLink(wiki, name: name),
                startYear: startYear, endYear: endYear,
                titleName: titleName, titlePlural: titlePlural,
                rulerID: rulerID, progrTitle: prog, iconAsset: titleName))
        }
        return rows
    }

    private func rulersByText(terms: [String]) -> [SearchResult] {
        let (textSQL, textParams) = foldedTextSQL(
            columns: ["ru.name", "ru.personal_name", "ru.epithet", "ru.notes", "t.title"],
            terms: terms)
        let sql = """
            SELECT ru.rulerID, ru.name, ru.personal_name, ru.epithet, ru.wikipedia,
                   ru.biography, per.progrTitle, per.period, per.startYear, per.endYear,
                   per.notes, t.title, t.titlePlural
            FROM rulers ru
            JOIN byPeriod per ON ru.rulerID = per.rulerID
            JOIN titles t ON per.titleID = t.titleID
            WHERE \(textSQL)
            ORDER BY ru.rulerID, per.startYear;
            """
        guard let stmt = prepare(sql) else { return [] }
        defer { sqlite3_finalize(stmt) }
        var idx: Int32 = 1
        for p in textParams { bindText(stmt, idx, p); idx += 1 }

        // Group periods by ruler, preserving first-seen order.
        var order: [Int] = []
        var periodsByRuler: [Int: [PeriodInfo]] = [:]
        struct RulerMeta { var name: String; var personal: String?; var epithet: String?
                           var wiki: String?; var biography: String?; var titlePlural: String?
                           var titleName: String }
        var meta: [Int: RulerMeta] = [:]

        while sqlite3_step(stmt) == SQLITE_ROW {
            let rulerID = col(stmt, 0).int
            if periodsByRuler[rulerID] == nil { order.append(rulerID) }
            meta[rulerID] = RulerMeta(
                name: col(stmt, 1).string, personal: col(stmt, 2).optString,
                epithet: col(stmt, 3).optString, wiki: col(stmt, 4).optString,
                biography: col(stmt, 5).optString, titlePlural: col(stmt, 12).optString,
                titleName: col(stmt, 11).string)
            periodsByRuler[rulerID, default: []].append(PeriodInfo(
                period: col(stmt, 7).string, notes: col(stmt, 10).optString ?? "",
                title: col(stmt, 11).string, startYear: col(stmt, 8).int,
                endYear: col(stmt, 9).int, progrTitle: col(stmt, 6).int))
        }

        var rows: [SearchResult] = []
        for rulerID in order {
            guard let m = meta[rulerID], let periods = periodsByRuler[rulerID] else { continue }
            let epithetString = (m.epithet?.isEmpty == false) ? " (\(m.epithet!))" : ""
            let displayTitle = "\(m.name)\(epithetString)"
            let subtitle = (m.biography?.isEmpty == false)
                ? m.biography!
                : formatRulerSubtitle(periods: periods, personalName: m.personal)

            let earliest = periods.map(\.startYear).min() ?? 0
            let latest = periods.map(\.endYear).max() ?? 0
            // Highest-ranked title represents the ruler for "Show all".
            let topTitle = periods.min { TitleRanking.rank($0.title) < TitleRanking.rank($1.title) }?.title ?? m.titleName

            rows.append(SearchResult(
                kind: .ruler, title: displayTitle, subtitle: subtitle,
                wikipediaURL: wikipediaLink(m.wiki, name: m.name),
                startYear: earliest, endYear: latest,
                titleName: topTitle, titlePlural: m.titlePlural,
                rulerID: rulerID, progrTitle: periods.first?.progrTitle,
                iconAsset: topTitle))
        }
        return rows
    }

    private func eventsByYear(yearTerm: String, textTerms: [String]) -> [SearchResult] {
        let yc = QueryParser.yearClause(for: yearTerm)
        let (yearSQL, yearParams) = yearClauseSQL(yc, yearColumn: "y.year")
        let (textSQL, textParams) = foldedTextSQL(columns: ["e.eventName", "e.notes"], terms: textTerms)

        var sql = """
            SELECT e.eventID, e.eventName, e.startYear, e.endYear, e.notes, e.wikipedia, y.year
            FROM byYear rt
            JOIN byEvents e ON rt.eventID = e.eventID
            JOIN years y ON rt.yearID = y.yearID
            WHERE \(yearSQL)
            """
        if !textTerms.isEmpty { sql += " AND \(textSQL)" }
        sql += " ORDER BY y.year;"

        guard let stmt = prepare(sql) else { return [] }
        defer { sqlite3_finalize(stmt) }
        var idx: Int32 = 1
        for p in yearParams { bindAny(stmt, idx, p); idx += 1 }
        for p in textParams { bindText(stmt, idx, p); idx += 1 }

        let span = QueryParser.isSpan(yearTerm)
        var rows: [SearchResult] = []
        while sqlite3_step(stmt) == SQLITE_ROW {
            let name = col(stmt, 1).string
            let startYear = col(stmt, 2).int
            let endYear = col(stmt, 3).int
            let notes = col(stmt, 4).optString ?? ""
            let wiki = col(stmt, 5).optString
            let year = col(stmt, 6).int

            let yearString = span ? yearTerm : formatYear(year)
            let rangeStr = startYear != endYear ? " (\(formatYear(startYear))-\(formatYear(endYear)))" : ""
            rows.append(SearchResult(
                kind: .event, title: "\(yearString): \(name)\(rangeStr)", subtitle: notes,
                wikipediaURL: wikipediaLink(wiki, name: name),
                startYear: startYear, endYear: endYear, iconAsset: "event"))
        }
        return rows
    }

    private func eventsByText(terms: [String]) -> [SearchResult] {
        let (textSQL, textParams) = foldedTextSQL(columns: ["e.eventName", "e.notes"], terms: terms)
        let sql = """
            SELECT e.eventID, e.eventName, e.startYear, e.endYear, e.notes, e.wikipedia
            FROM byEvents e
            WHERE \(textSQL)
            ORDER BY e.startYear;
            """
        guard let stmt = prepare(sql) else { return [] }
        defer { sqlite3_finalize(stmt) }
        var idx: Int32 = 1
        for p in textParams { bindText(stmt, idx, p); idx += 1 }

        var rows: [SearchResult] = []
        while sqlite3_step(stmt) == SQLITE_ROW {
            let name = col(stmt, 1).string
            let startYear = col(stmt, 2).int
            let endYear = col(stmt, 3).int
            let notes = col(stmt, 4).optString ?? ""
            let wiki = col(stmt, 5).optString

            let yearString = startYear == endYear
                ? formatYear(startYear)
                : "\(formatYear(startYear))-\(formatYear(endYear))"
            rows.append(SearchResult(
                kind: .event, title: "\(yearString): \(name)", subtitle: notes,
                wikipediaURL: wikipediaLink(wiki, name: name),
                startYear: startYear, endYear: endYear, iconAsset: "event"))
        }
        return rows
    }

    // MARK: - SQL helpers

    private func prepare(_ sql: String) -> OpaquePointer? {
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(handle, sql, -1, &stmt, nil) == SQLITE_OK else {
            if let h = handle { print("prepare failed: \(String(cString: sqlite3_errmsg(h)))") }
            return nil
        }
        return stmt
    }

    /// A bound value for parameterized year clauses.
    private enum Param { case int(Int), text(String) }

    private func yearClauseSQL(_ clause: QueryParser.YearClause, yearColumn: String) -> (String, [Param]) {
        switch clause {
        case .range(let lower, let upper):
            return ("(\(yearColumn) BETWEEN ? AND ?)", [.int(lower), .int(upper)])
        case .like(let pattern):
            return ("(CAST(\(yearColumn) AS TEXT) LIKE ?)", [.text(pattern)])
        }
    }

    /// Builds `(fold(col) LIKE ? OR ...) AND (...)` and the folded params.
    private func foldedTextSQL(columns: [String], terms: [String]) -> (String, [String]) {
        guard !terms.isEmpty else { return ("1=1", []) }
        var conditions: [String] = []
        var params: [String] = []
        for term in terms {
            let parts = columns.map { "fold(\($0)) LIKE ?" }
            conditions.append("(" + parts.joined(separator: " OR ") + ")")
            let folded = "%\(foldForSearch(term))%"
            params.append(contentsOf: Array(repeating: folded, count: columns.count))
        }
        return (conditions.joined(separator: " AND "), params)
    }

    private func bindAny(_ stmt: OpaquePointer?, _ idx: Int32, _ p: Param) {
        switch p {
        case .int(let v): sqlite3_bind_int64(stmt, idx, Int64(v))
        case .text(let v): bindText(stmt, idx, v)
        }
    }

    private func bindText(_ stmt: OpaquePointer?, _ idx: Int32, _ value: String) {
        sqlite3_bind_text(stmt, idx, value, -1, SQLITE_TRANSIENT)
    }

    /// Lightweight typed column accessor.
    private struct Column { let stmt: OpaquePointer?; let i: Int32
        var int: Int { Int(sqlite3_column_int64(stmt, i)) }
        var optString: String? {
            sqlite3_column_type(stmt, i) == SQLITE_NULL
                ? nil : sqlite3_column_text(stmt, i).map { String(cString: $0) }
        }
        var string: String { optString ?? "" }
    }
    private func col(_ stmt: OpaquePointer?, _ i: Int32) -> Column { Column(stmt: stmt, i: i) }

    private func wikipediaLink(_ stored: String?, name: String) -> URL? {
        if let s = stored, !s.isEmpty { return URL(string: s) }
        let slug = name.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? name
        return URL(string: "https://en.wikipedia.org/wiki/\(slug)")
    }
}

/// Adds thousands separators, matching the Go `formatNumber`.
func formatNumber(_ n: Int) -> String {
    let f = NumberFormatter()
    f.numberStyle = .decimal
    f.groupingSeparator = ","
    return f.string(from: NSNumber(value: n)) ?? "\(n)"
}
