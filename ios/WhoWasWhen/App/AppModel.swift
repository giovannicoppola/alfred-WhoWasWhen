import SwiftUI

/// A pushable screen in the navigation stack.
/// `.query` powers "travel to year" (and sub-queries); `.lineage` powers
/// "Show all «title»". Back navigation == the workflow's "go back to main search".
enum Route: Hashable {
    case query(String)
    case lineage(title: String, rulerID: Int?, prog: Int?)
}

/// The app's top-level tabs (`admin` exists only in the admin build).
enum AppTab: Hashable { case search, discover, quiz, favorites, admin }

/// App-wide state: the open database, the navigation path, and the search scope.
@MainActor
@Observable
final class AppModel {
    var selectedTab: AppTab = .search
    var path: [Route] = []
    var scope: SearchScope = .all

    private(set) var db: Database?
    private(set) var loadError: String?

    /// A transient confirmation banner (e.g. "Copied to clipboard"); nil when hidden.
    private(set) var toast: String?
    private var toastTask: Task<Void, Never>?

    private var loadTask: Task<Void, Never>?

    /// Opens the database (bundled, or a newer iCloud copy). Safe to call
    /// repeatedly and concurrently — every tab awaits this before its first
    /// query, and all callers share one underlying open.
    func load() async {
        if loadTask == nil {
            loadTask = Task {
                do {
                    // Resolve the path and open the database off the main thread —
                    // `resolveDatabasePath()` does file I/O that must not block the UI.
                    db = try await Task.detached(priority: .userInitiated) {
                        let t0 = Date()
                        print("[WWW] resolving database path…")
                        let path = DatabaseProvider.resolveDatabasePath()
                        print("[WWW] resolved in \(Date().timeIntervalSince(t0))s: \(path)")
                        let bundled = DatabaseProvider.bundledDatabaseURL().path
                        if let candidate = try? Database(path: path),
                           await candidate.isHealthy() {
                            print("[WWW] opened healthy db in \(Date().timeIntervalSince(t0))s")
                            return candidate
                        }
                        print("[WWW] working copy unhealthy — falling back to bundle")
                        guard path != bundled else {
                            throw DatabaseProvider.LoadFailure.bundledUnreadable
                        }
                        // The working copy opened but isn't usable (or didn't
                        // open) — e.g. a seed copy interrupted by an app kill.
                        // Reset it and serve the read-only bundled database.
                        DatabaseProvider.discardWorkingCopy()
                        return try Database(path: bundled)
                    }.value
                } catch {
                    print("[WWW] database load FAILED: \(error)")
                    loadError = String(describing: error)
                }
            }
        }
        await loadTask?.value
    }

    /// The database, after waiting for the initial open. Every query goes
    /// through this so screens reached early (deep links, cold tab opens)
    /// never race the launch-time load.
    private func database() async -> Database? {
        await load()
        return db
    }

    func results(for query: String) async -> [SearchResult] {
        guard let db = await database() else { return [] }
        return await db.search(query: query, scope: scope)
    }

    func lineageResults(title: String, rulerID: Int?, prog: Int?) async -> [SearchResult] {
        guard let db = await database() else { return [] }
        return await db.lineage(title: title, focusRulerID: rulerID, focusProg: prog)
    }

    // MARK: - Data access for the Discover / Quiz / Favorites tabs

    func randomRuler() async -> SearchResult? { await database()?.randomRuler() }
    func randomEvent() async -> SearchResult? { await database()?.randomEvent() }

    /// Events / rulers matching exactly one year — the Discover
    /// "centuries ago" sections.
    func events(inYear year: Int) async -> [SearchResult] {
        guard let db = await database() else { return [] }
        return await db.searchByYear(yearTerm: String(year), textTerms: [],
                                     includeRulers: false, includeEvents: true)
    }

    func rulers(inYear year: Int) async -> [SearchResult] {
        guard let db = await database() else { return [] }
        return await db.searchByYear(yearTerm: String(year), textTerms: [],
                                     includeRulers: true, includeEvents: false)
    }

    func ruler(byID id: Int) async -> SearchResult? { await database()?.ruler(byID: id) }
    func event(byID id: Int) async -> SearchResult? { await database()?.event(byID: id) }

    /// Events whose exact date matches today — the Search tab's
    /// "On this day" card. Empty when the database has no dated events.
    func eventsOnToday() async -> [SearchResult] {
        let parts = Calendar.current.dateComponents([.month, .day], from: .now)
        guard let month = parts.month, let day = parts.day,
              let db = await database() else { return [] }
        return await db.eventsOn(month: month, day: day)
    }

    /// Raw sheet-addressable fields for the admin build's curation UI.
    func rulerRawFields(byID id: Int) async -> RawRecord? {
        await database()?.rulerRawFields(byID: id)
    }
    func eventRawFields(byID id: Int) async -> RawRecord? {
        await database()?.eventRawFields(byID: id)
    }

    func quizTitles() async -> [TitleInfo] { await database()?.quizTitles() ?? [] }
    func holders(ofTitle title: String) async -> [HolderRow] {
        await database()?.holders(ofTitle: title) ?? []
    }
    func titleSpan(_ title: String) async -> ClosedRange<Int>? {
        await database()?.titleSpan(title)
    }
    func randomQuizEvents(limit: Int) async -> [QuizEventRow] {
        await database()?.randomQuizEvents(limit: limit) ?? []
    }

    // Navigation actions invoked from result rows / detail.
    // Both push onto the Search tab's stack, so jump to that tab first when
    // invoked from Discover / Favorites — otherwise the push is invisible.
    // Use the raw signed year (e.g. "-44") so the parser reads it as a year;
    // `formatYear` ("44 BC") would be misparsed as year 44 + the text "bc".
    func travel(toYear year: Int) {
        selectedTab = .search
        path.append(.query(String(year)))
    }

    func showLineage(for result: SearchResult) {
        guard let title = result.titleName, !title.isEmpty else { return }
        selectedTab = .search
        path.append(.lineage(title: title, rulerID: result.rulerID, prog: result.progrTitle))
    }

    /// Copies a result to the clipboard and confirms with a haptic + brief banner.
    func copyToClipboard(_ result: SearchResult) {
        UIPasteboard.general.string = result.copyText
        UINotificationFeedbackGenerator().notificationOccurred(.success)
        showToast("Copied to clipboard")
    }

    /// Shows a transient banner that auto-dismisses after a short delay.
    func showToast(_ message: String) {
        toast = message
        toastTask?.cancel()
        toastTask = Task { [weak self] in
            try? await Task.sleep(for: .seconds(1.6))
            guard !Task.isCancelled else { return }
            self?.toast = nil
        }
    }
}
