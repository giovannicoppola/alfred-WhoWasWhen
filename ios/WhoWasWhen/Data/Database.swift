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

    /// Whether byEvents carries startMonth/startDay. Older databases (e.g. a
    /// stale iCloud copy) predate the columns; queries must not assume them.
    private let hasEventDates: Bool

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
        self.hasEventDates = Database.columnExists(db, table: "byEvents", column: "startMonth")
        Database.registerFoldFunction(db)
    }

    private nonisolated static func columnExists(_ db: OpaquePointer, table: String,
                                                 column: String) -> Bool {
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, "PRAGMA table_info(\(table));", -1, &stmt, nil) == SQLITE_OK
        else { return false }
        defer { sqlite3_finalize(stmt) }
        while sqlite3_step(stmt) == SQLITE_ROW {
            if let c = sqlite3_column_text(stmt, 1), String(cString: c) == column {
                return true
            }
        }
        return false
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

        // Unlike the Alfred workflow (which starts a few before the focused
        // ruler), the app returns the whole lineage so the user can scroll the
        // full list; the focused ruler is highlighted and scrolled into view.
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

        // The matched year is shown once as a header by the UI, not per row.
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

            let epithetString = (epithet?.isEmpty == false) ? " (\(epithet!))" : ""
            let displayTitle = "\(name)\(epithetString) (\(period))"
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
        return collectRulerRows(stmt)
    }

    /// Steps a rulers+periods statement (the 13-column SELECT used by
    /// `rulersByText` and `ruler(byID:)`) into one row per ruler, grouping
    /// multiple reign periods into a single subtitle.
    private func collectRulerRows(_ stmt: OpaquePointer?) -> [SearchResult] {
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

    /// The SELECT list every event query shares; positions are fixed so
    /// `eventRow` can read them (month/day only exist on newer databases).
    private var eventColumns: String {
        var cols = "e.eventID, e.eventName, e.startYear, e.endYear, e.notes, e.wikipedia"
        if hasEventDates { cols += ", e.startMonth, e.startDay" }
        return cols
    }

    private func eventsByYear(yearTerm: String, textTerms: [String]) -> [SearchResult] {
        let yc = QueryParser.yearClause(for: yearTerm)
        let (yearSQL, yearParams) = yearClauseSQL(yc, yearColumn: "y.year")
        let (textSQL, textParams) = foldedTextSQL(columns: ["e.eventName", "e.notes"], terms: textTerms)

        var sql = """
            SELECT \(eventColumns)
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

        // The matched year is shown once as a header by the UI, not per row,
        // so this row style leads with the name, not the year.
        var rows: [SearchResult] = []
        while sqlite3_step(stmt) == SQLITE_ROW {
            let name = col(stmt, 1).string
            let startYear = col(stmt, 2).int
            let endYear = col(stmt, 3).int
            let rangeStr = startYear != endYear
                ? " (\(formatYear(startYear))-\(formatYear(endYear)))" : ""
            var row = eventRow(stmt)
            row.title = "\(name)\(rangeStr)"
            rows.append(row)
        }
        return rows
    }

    private func eventsByText(terms: [String]) -> [SearchResult] {
        let (textSQL, textParams) = foldedTextSQL(columns: ["e.eventName", "e.notes"], terms: terms)
        let sql = """
            SELECT \(eventColumns)
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
            rows.append(eventRow(stmt))
        }
        return rows
    }

    /// Builds the "«years»: «name»" event row shared by every event query
    /// (they all SELECT `eventColumns`, so the positions line up).
    private func eventRow(_ stmt: OpaquePointer?) -> SearchResult {
        let eventID = col(stmt, 0).int
        let name = col(stmt, 1).string
        let startYear = col(stmt, 2).int
        let endYear = col(stmt, 3).int
        let notes = col(stmt, 4).optString ?? ""
        let wiki = col(stmt, 5).optString
        let month = hasEventDates ? col(stmt, 6).optInt : nil
        let day = hasEventDates ? col(stmt, 7).optInt : nil

        let yearString = startYear == endYear
            ? formatYear(startYear)
            : "\(formatYear(startYear))-\(formatYear(endYear))"
        return SearchResult(
            kind: .event, title: "\(yearString): \(name)", subtitle: notes,
            wikipediaURL: wikipediaLink(wiki, name: name),
            startYear: startYear, endYear: endYear, eventID: eventID,
            startMonth: month, startDay: day,
            iconAsset: "event")
    }

    /// Events whose exact start date matches a calendar day — "On this day".
    func eventsOn(month: Int, day: Int) -> [SearchResult] {
        guard hasEventDates else { return [] }
        let sql = """
            SELECT \(eventColumns)
            FROM byEvents e
            WHERE e.startMonth = ? AND e.startDay = ?
            ORDER BY e.startYear;
            """
        guard let stmt = prepare(sql) else { return [] }
        defer { sqlite3_finalize(stmt) }
        sqlite3_bind_int64(stmt, 1, Int64(month))
        sqlite3_bind_int64(stmt, 2, Int64(day))

        var rows: [SearchResult] = []
        while sqlite3_step(stmt) == SQLITE_ROW {
            rows.append(eventRow(stmt))
        }
        return rows
    }

    // MARK: - Discovery / favorites / quiz queries

    /// One ruler by database ID, in the same shape as a text-search row
    /// (used to rehydrate Favorites and the Discover card).
    func ruler(byID id: Int) -> SearchResult? {
        let sql = """
            SELECT ru.rulerID, ru.name, ru.personal_name, ru.epithet, ru.wikipedia,
                   ru.biography, per.progrTitle, per.period, per.startYear, per.endYear,
                   per.notes, t.title, t.titlePlural
            FROM rulers ru
            JOIN byPeriod per ON ru.rulerID = per.rulerID
            JOIN titles t ON per.titleID = t.titleID
            WHERE ru.rulerID = ?
            ORDER BY ru.rulerID, per.startYear;
            """
        guard let stmt = prepare(sql) else { return nil }
        defer { sqlite3_finalize(stmt) }
        sqlite3_bind_int64(stmt, 1, Int64(id))
        return collectRulerRows(stmt).first
    }

    /// One event by database ID (used to rehydrate Favorites).
    func event(byID id: Int) -> SearchResult? {
        let sql = """
            SELECT \(eventColumns)
            FROM byEvents e WHERE e.eventID = ?;
            """
        guard let stmt = prepare(sql) else { return nil }
        defer { sqlite3_finalize(stmt) }
        sqlite3_bind_int64(stmt, 1, Int64(id))
        guard sqlite3_step(stmt) == SQLITE_ROW else { return nil }
        return eventRow(stmt)
    }

    /// A random ruler for the Discover screen. Excludes plain consuls and
    /// tribunes (~85% of the table, mostly bare names) so the featured card
    /// usually has a story to tell; emperors who were also consuls still
    /// qualify through their other title.
    func randomRuler() -> SearchResult? {
        let sql = """
            SELECT DISTINCT ru.rulerID
            FROM rulers ru
            JOIN byPeriod per ON ru.rulerID = per.rulerID
            JOIN titles t ON per.titleID = t.titleID
            WHERE t.title NOT LIKE '%Consul%' AND t.title NOT LIKE '%Tribune%'
            ORDER BY RANDOM() LIMIT 1;
            """
        guard let stmt = prepare(sql) else { return nil }
        defer { sqlite3_finalize(stmt) }
        guard sqlite3_step(stmt) == SQLITE_ROW else { return nil }
        return ruler(byID: col(stmt, 0).int)
    }

    /// A random event for the Discover screen.
    func randomEvent() -> SearchResult? {
        let sql = """
            SELECT \(eventColumns)
            FROM byEvents e ORDER BY RANDOM() LIMIT 1;
            """
        guard let stmt = prepare(sql) else { return nil }
        defer { sqlite3_finalize(stmt) }
        guard sqlite3_step(stmt) == SQLITE_ROW else { return nil }
        return eventRow(stmt)
    }

    /// Titles with enough holders to make a quiz category with plausible
    /// wrong answers.
    func quizTitles(minHolders: Int = 15) -> [TitleInfo] {
        let sql = """
            SELECT titleID, title, titlePlural, maxCount FROM titles
            WHERE maxCount >= ? ORDER BY title;
            """
        guard let stmt = prepare(sql) else { return [] }
        defer { sqlite3_finalize(stmt) }
        sqlite3_bind_int64(stmt, 1, Int64(minHolders))

        var rows: [TitleInfo] = []
        while sqlite3_step(stmt) == SQLITE_ROW {
            rows.append(TitleInfo(
                titleID: col(stmt, 0).int, title: col(stmt, 1).string,
                titlePlural: col(stmt, 2).optString, maxCount: col(stmt, 3).int))
        }
        return rows
    }

    /// Every reign of a title, in progression order (quiz question material
    /// and the detail view's mini-timeline).
    func holders(ofTitle title: String) -> [HolderRow] {
        let sql = """
            SELECT ru.rulerID, ru.name, per.period, per.startYear, per.endYear, per.progrTitle
            FROM rulers ru
            JOIN byPeriod per ON ru.rulerID = per.rulerID
            JOIN titles t ON per.titleID = t.titleID
            WHERE t.title = ?
            ORDER BY per.progrTitle ASC;
            """
        guard let stmt = prepare(sql) else { return [] }
        defer { sqlite3_finalize(stmt) }
        bindText(stmt, 1, title)

        var rows: [HolderRow] = []
        while sqlite3_step(stmt) == SQLITE_ROW {
            rows.append(HolderRow(
                rulerID: col(stmt, 0).int, name: col(stmt, 1).string,
                period: col(stmt, 2).string, startYear: col(stmt, 3).int,
                endYear: col(stmt, 4).int, progrTitle: col(stmt, 5).int))
        }
        return rows
    }

    /// The first and last year any holder of `title` reigned.
    func titleSpan(_ title: String) -> ClosedRange<Int>? {
        let sql = """
            SELECT MIN(per.startYear), MAX(per.endYear)
            FROM byPeriod per JOIN titles t ON per.titleID = t.titleID
            WHERE t.title = ?;
            """
        guard let stmt = prepare(sql) else { return nil }
        defer { sqlite3_finalize(stmt) }
        bindText(stmt, 1, title)
        guard sqlite3_step(stmt) == SQLITE_ROW,
              sqlite3_column_type(stmt, 0) != SQLITE_NULL else { return nil }
        let lo = col(stmt, 0).int, hi = col(stmt, 1).int
        return lo <= hi ? lo...hi : nil
    }

    /// Random events reduced to what a quiz question needs (no formatted
    /// title, which would leak the answer year).
    func randomQuizEvents(limit: Int) -> [QuizEventRow] {
        let sql = "SELECT eventID, eventName, startYear, endYear FROM byEvents ORDER BY RANDOM() LIMIT ?;"
        guard let stmt = prepare(sql) else { return [] }
        defer { sqlite3_finalize(stmt) }
        sqlite3_bind_int64(stmt, 1, Int64(limit))

        var rows: [QuizEventRow] = []
        while sqlite3_step(stmt) == SQLITE_ROW {
            rows.append(QuizEventRow(
                eventID: col(stmt, 0).int, name: col(stmt, 1).string,
                startYear: col(stmt, 2).int, endYear: col(stmt, 3).int))
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
        var optInt: Int? {
            sqlite3_column_type(stmt, i) == SQLITE_NULL
                ? nil : Int(sqlite3_column_int64(stmt, i))
        }
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

/// A quiz-eligible title, doubling as a quiz category.
struct TitleInfo: Sendable, Identifiable, Hashable {
    let titleID: Int
    let title: String
    let titlePlural: String?
    let maxCount: Int
    var id: Int { titleID }
}

/// One reign of one holder of a title (quiz distractors + timelines).
struct HolderRow: Sendable, Hashable {
    let rulerID: Int
    let name: String
    let period: String
    let startYear: Int
    let endYear: Int
    let progrTitle: Int
}

/// An event stripped to what a quiz question needs.
struct QuizEventRow: Sendable, Hashable {
    let eventID: Int
    let name: String
    let startYear: Int
    let endYear: Int
}

/// Adds thousands separators, matching the Go `formatNumber`.
func formatNumber(_ n: Int) -> String {
    let f = NumberFormatter()
    f.numberStyle = .decimal
    f.groupingSeparator = ","
    return f.string(from: NSNumber(value: n)) ?? "\(n)"
}
