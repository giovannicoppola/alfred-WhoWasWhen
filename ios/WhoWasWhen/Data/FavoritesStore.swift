import Foundation
import Observation

/// A saved ruler or event, keyed by its stable database ID so favorites
/// survive both relaunches and database updates.
struct FavoriteEntry: Codable, Hashable, Identifiable {
    enum Kind: String, Codable { case ruler, event }
    var kind: Kind
    var dbID: Int          // rulerID or eventID
    var dateAdded: Date

    var id: String { "\(kind.rawValue)-\(dbID)" }
}

/// The user's favorites, persisted as a small JSON file in Application
/// Support (a handful of IDs — no need for a database).
@MainActor
@Observable
final class FavoritesStore {
    /// Newest first.
    private(set) var entries: [FavoriteEntry] = []

    private let fileURL: URL

    init() {
        let dir = FileManager.default.urls(for: .applicationSupportDirectory,
                                           in: .userDomainMask)[0]
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        fileURL = dir.appendingPathComponent("favorites.json")
        load()
    }

    /// The favorite identity of a result, or nil if it can't be favorited
    /// (an event row missing its database ID).
    static func identity(of result: SearchResult) -> (kind: FavoriteEntry.Kind, dbID: Int)? {
        switch result.kind {
        case .ruler: return result.rulerID.map { (.ruler, $0) }
        case .event: return result.eventID.map { (.event, $0) }
        }
    }

    func isFavorite(_ result: SearchResult) -> Bool {
        guard let (kind, dbID) = Self.identity(of: result) else { return false }
        return entries.contains { $0.kind == kind && $0.dbID == dbID }
    }

    /// Adds or removes a favorite. Returns the new state (true = now saved),
    /// or nil if the result has no stable identity.
    @discardableResult
    func toggle(_ result: SearchResult) -> Bool? {
        guard let (kind, dbID) = Self.identity(of: result) else { return nil }
        if let idx = entries.firstIndex(where: { $0.kind == kind && $0.dbID == dbID }) {
            entries.remove(at: idx)
            save()
            return false
        }
        entries.insert(FavoriteEntry(kind: kind, dbID: dbID, dateAdded: .now), at: 0)
        save()
        return true
    }

    func remove(_ entry: FavoriteEntry) {
        entries.removeAll { $0 == entry }
        save()
    }

    // MARK: - Persistence

    private func load() {
        guard let data = try? Data(contentsOf: fileURL),
              let decoded = try? JSONDecoder().decode([FavoriteEntry].self, from: data)
        else { return }
        entries = decoded
    }

    private func save() {
        if let data = try? JSONEncoder().encode(entries) {
            try? data.write(to: fileURL, options: .atomic)
        }
    }
}
