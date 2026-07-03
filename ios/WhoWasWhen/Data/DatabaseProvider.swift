import Foundation

/// Resolves which `whoWasWhen.db` file to open.
///
/// Strategy (decided with the app owner): always ship a bundled copy so the app
/// works instantly and offline, but if a *newer* copy exists in the app's iCloud
/// Drive container, prefer it. The iCloud step degrades gracefully to a no-op
/// when the entitlement/account isn't configured, so Simulator and unsigned
/// builds still work.
enum DatabaseProvider {
    static let dbName = "whoWasWhen.db"

    enum LoadFailure: Error { case bundledUnreadable }

    /// The iCloud refresh stays off while the app ships without the iCloud
    /// entitlement (commented out in project.yml). The lookup can't find
    /// anything without it, but `url(forUbiquityContainerIdentifier:)` can
    /// still block for a long time on a real device while iCloud state is
    /// resolved — with every tab awaiting the first open, that reads as
    /// "search stuck, nothing loads". Flip this only together with the
    /// entitlement.
    static let iCloudRefreshEnabled = false

    /// The bundled read-only database — the fallback that must always work.
    static func bundledDatabaseURL() -> URL {
        guard let bundled = Bundle.main.url(forResource: "whoWasWhen", withExtension: "db") else {
            fatalError("Bundled \(dbName) is missing from the app bundle")
        }
        return bundled
    }

    /// Returns a filesystem path to the best available database, copying the
    /// bundled DB into Application Support on first run so it is writable-adjacent
    /// and stable across launches.
    static func resolveDatabasePath() -> String {
        let fm = FileManager.default
        let bundled = bundledDatabaseURL()

        // Working copy lives in Application Support.
        let support = (try? fm.url(for: .applicationSupportDirectory, in: .userDomainMask,
                                   appropriateFor: nil, create: true))
        let working = support?.appendingPathComponent(dbName)

        if let working {
            // Seed the working copy from the bundle if absent or older than the bundle.
            if shouldReplace(destination: working, with: bundled, fm: fm) {
                try? fm.removeItem(at: working)
                try? fm.copyItem(at: bundled, to: working)
            }
            // If iCloud has a newer DB, copy it over the working copy.
            if iCloudRefreshEnabled,
               let cloud = newerICloudDatabase(thanWorking: working, fm: fm) {
                try? fm.removeItem(at: working)
                try? fm.copyItem(at: cloud, to: working)
            }
            if fm.fileExists(atPath: working.path) { return working.path }
        }

        // Fallback: open the bundled DB directly.
        return bundled.path
    }

    /// Deletes a working copy that failed to open or validate (e.g. a copy
    /// interrupted by an app kill), so the next resolve re-seeds it.
    static func discardWorkingCopy() {
        let fm = FileManager.default
        guard let support = try? fm.url(for: .applicationSupportDirectory, in: .userDomainMask,
                                        appropriateFor: nil, create: false) else { return }
        try? fm.removeItem(at: support.appendingPathComponent(dbName))
    }

    private static func shouldReplace(destination: URL, with source: URL, fm: FileManager) -> Bool {
        guard fm.fileExists(atPath: destination.path) else { return true }
        let dDate = modified(destination, fm)
        let sDate = modified(source, fm)
        return sDate > dDate
    }

    /// Looks for a newer DB in the iCloud ubiquity container's Documents folder.
    /// Returns nil (no-op) when iCloud isn't available — e.g. no entitlement.
    private static func newerICloudDatabase(thanWorking working: URL, fm: FileManager) -> URL? {
        guard let container = fm.url(forUbiquityContainerIdentifier: nil) else { return nil }
        let cloudDB = container.appendingPathComponent("Documents/\(dbName)")

        // Ensure the file is downloaded if it's only a placeholder.
        if !fm.fileExists(atPath: cloudDB.path) {
            try? fm.startDownloadingUbiquitousItem(at: cloudDB)
            return nil
        }
        return modified(cloudDB, fm) > modified(working, fm) ? cloudDB : nil
    }

    private static func modified(_ url: URL, _ fm: FileManager) -> Date {
        (try? fm.attributesOfItem(atPath: url.path)[.modificationDate] as? Date) ?? Date.distantPast
    }
}
