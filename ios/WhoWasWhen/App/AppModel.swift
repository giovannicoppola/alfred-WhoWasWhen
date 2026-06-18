import SwiftUI

/// A pushable screen in the navigation stack.
/// `.query` powers "travel to year" (and sub-queries); `.lineage` powers
/// "Show all «title»". Back navigation == the workflow's "go back to main search".
enum Route: Hashable {
    case query(String)
    case lineage(title: String, rulerID: Int?, prog: Int?)
}

/// App-wide state: the open database, the navigation path, and the search scope.
@MainActor
@Observable
final class AppModel {
    var path: [Route] = []
    var scope: SearchScope = .all

    private(set) var db: Database?
    private(set) var loadError: String?

    /// A transient confirmation banner (e.g. "Copied to clipboard"); nil when hidden.
    private(set) var toast: String?
    private var toastTask: Task<Void, Never>?

    /// Opens the database (bundled, or a newer iCloud copy). Safe to call repeatedly.
    func load() async {
        guard db == nil, loadError == nil else { return }
        let path = DatabaseProvider.resolveDatabasePath()
        do {
            db = try Database(path: path)
        } catch {
            loadError = String(describing: error)
        }
    }

    func results(for query: String) async -> [SearchResult] {
        guard let db else { return [] }
        return await db.search(query: query, scope: scope)
    }

    func lineageResults(title: String, rulerID: Int?, prog: Int?) async -> [SearchResult] {
        guard let db else { return [] }
        return await db.lineage(title: title, focusRulerID: rulerID, focusProg: prog)
    }

    // Navigation actions invoked from result rows / detail.
    // Use the raw signed year (e.g. "-44") so the parser reads it as a year;
    // `formatYear` ("44 BC") would be misparsed as year 44 + the text "bc".
    func travel(toYear year: Int) { path.append(.query(String(year))) }

    func showLineage(for result: SearchResult) {
        guard let title = result.titleName, !title.isEmpty else { return }
        path.append(.lineage(title: title, rulerID: result.rulerID, prog: result.progrTitle))
    }

    /// Copies a result to the clipboard and confirms with a haptic + brief banner.
    func copyToClipboard(_ result: SearchResult) {
        UIPasteboard.general.string = result.copyText
        UINotificationFeedbackGenerator().notificationOccurred(.success)
        showToast("Copied to clipboard")
    }

    /// Shows a transient banner that auto-dismisses after a short delay.
    private func showToast(_ message: String) {
        toast = message
        toastTask?.cancel()
        toastTask = Task { [weak self] in
            try? await Task.sleep(for: .seconds(1.6))
            guard !Task.isCancelled else { return }
            self?.toast = nil
        }
    }
}
