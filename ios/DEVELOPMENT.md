# WhoWasWhen iOS — Development

Technical notes for building, maintaining, and shipping the iPhone companion app.
For a user-facing overview of what the app does, see [README.md](README.md).

The app is a faithful port of the Alfred workflow's search logic
(`pkg/ruler-query.go`) over the same SQLite database.

## Architecture

- **SwiftUI**, iOS 17+, Swift 6 (strict concurrency).
- **No third-party dependencies** — talks to the system `libsqlite3` directly and
  registers the same custom `fold()` SQL function the workflow uses for
  accent-insensitive search.
- **Database delivery**: the `whoWasWhen.db` (~2.3 MB) is **bundled** in the app
  so it works instantly and offline. On launch the app optionally checks the
  app's **iCloud Drive** container for a *newer* copy and uses it if present.
  The iCloud step is a graceful no-op when the entitlement/account isn't
  configured (so Simulator and unsigned builds just use the bundled DB).

| File | Role |
|------|------|
| `Data/Fold.swift` | Accent/case folding (ports `search_fold.go`) |
| `Data/QueryParser.swift` | Year vs text detection, wildcards, ranges, BC |
| `Data/Database.swift` | SQLite actor: by-year, by-text, lineage queries |
| `Data/DatabaseProvider.swift` | Resolves bundled vs iCloud DB |
| `Models/SearchResult.swift` | Result model + subtitle/title-rank formatting |
| `App/AppModel.swift` | Navigation path + scope + DB access |
| `Views/*` | Search, results list, row, detail, lineage screens |

## Build & run

The Xcode project is **generated** from `project.yml` with
[XcodeGen](https://github.com/yonyz/XcodeGen) so it stays diff-friendly and is
not committed.

```bash
brew install xcodegen          # if not already installed
cd ios
xcodegen generate              # creates WhoWasWhen.xcodeproj
open WhoWasWhen.xcodeproj       # then ⌘R in Xcode
```

Or from the command line:

```bash
xcodebuild -project ios/WhoWasWhen.xcodeproj -scheme WhoWasWhen \
  -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' build
```

## Updating the bundled database

Copy the latest DB into the app resources and rebuild:

```bash
cp releases/whoWasWhen.db ios/WhoWasWhen/Resources/whoWasWhen.db
```

## Enabling the iCloud Drive refresh (for signed/release builds)

The optional "use a newer DB from iCloud" feature needs the iCloud capability:

1. In `project.yml`, uncomment the `entitlements` block under the `WhoWasWhen`
   target (and adjust the container identifier / your team).
2. In your Apple Developer account, enable **iCloud → CloudKit/Documents** with a
   ubiquity container matching that identifier.
3. Place an updated `whoWasWhen.db` in the app's iCloud Drive `Documents` folder;
   the app will pick it up on next launch if it is newer than the bundled copy.

## App icon

The app icon reuses the Alfred workflow's crowned globe; the accent color is in
`Assets.xcassets`.

## Distribution

Targeted at TestFlight / App Store, which favors the bundled-DB approach. The
project is configured to sign with team `VDG762YNX9` and bundle id
`com.giovannicoppola.WhoWasWhen` (automatic signing).

- **[TESTFLIGHT.md](TESTFLIGHT.md)** — creating the App Store Connect app record,
  archiving in Xcode, uploading, and adding internal testers.
- **[APPSTORE.md](APPSTORE.md)** — taking a tested build through App Review to a
  public listing, plus monetization options.
