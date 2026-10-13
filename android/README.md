# WhoWasWhen — Android 👑🤖

A native Android port of the [WhoWasWhen iPhone app](../ios/README.md), built
with **Kotlin + Jetpack Compose**. Same data, same answers, fully offline.

## Status

- ✅ Builds: `./gradlew :app:assembleDebug` (and a minified, signed `assembleRelease`).
- ✅ Data layer verified against the bundled database (search, lineage, quiz, works).
- ✅ Verified on a Pixel 8a emulator (debug and release), screen by screen
  against the iOS App Store screenshots.

## What's here

Feature *and appearance* parity with the iOS app (minus the curator-only Admin
build). The UI deliberately reproduces the iOS design rather than stock
Material: same layouts, colors, type scale, and interactions.

- **Search** — year / decade (`177*`) / span (`1500-1600`) / BC (`-44`), year+topic,
  ruler, and event, with an All / People / Events scope filter.
- **Detail sheet** — Wikipedia summary + portrait, reign-position bar, lifespan,
  and every action (travel, show-all lineage, copy, favorite, Wikipedia, report).
- **Lineage** — full title lineage as a list or a visual timeline with century markers.
- **Discover** — shuffleable featured ruler + event and "N years ago" anniversaries.
- **Quiz** — the full `QuizEngine` (rulers, events, notable people, works, mixed,
  and by-title rounds) with best-score tracking.
- **Favorites** — saved rulers/events, rehydrated from stable DB IDs.
- **On this day** — today's-date event on the idle home screen.
- **Swipe actions** on every result row (right: travel to start/end year;
  left: favorite / Wikipedia / show all), plus the long-press context menu
  with the Report submenu — the same action set as iOS.

## Appearance (the iOS design kit)

`ui/Theme.kt`, `ui/IosComponents.kt`, `ui/SwipeActions.kt`, and `ui/Icons.kt`
rebuild the iOS look in Compose; screens use `Ios.colors` / `Ios.type`, not
Material's palette.

- **Colors** — Apple's system colors (light + dark), the asset-catalog
  `AccentColor` (#4B588B, no dark variant), system indigo/orange/yellow.
  Wallpaper-based dynamic color is intentionally off.
- **Type** — the Dynamic Type scale (body 17, subheadline 15, footnote 13, …)
  set in **Inter** (`res/font/`, SIL OFL — license in `assets/licenses/`),
  the closest freely licensed match for SF Pro.
- **Chrome** — inline centered navigation bar with "‹ Previous" back button,
  iOS tab bar, navigation-bar search field (Cancel + scope bar while
  searching), segmented controls, inset-grouped lists, `.borderedProminent` /
  `.bordered` buttons, the activity-indicator spinner, toast capsule, and an
  iOS-style context menu.
- **Icons** — Material equivalents of the SF Symbols, plus hand-drawn vectors
  where none exists (crown, cross, laurel, star-slash, travel arrows).

## Navigation model

As on iOS, each tab keeps its state while you switch tabs (a quiz round in
progress, the Discover picks, the search query), and the Search tab has its
own push stack (`WwwViewModel.path`) — "Travel to year" and "Show all" push
onto it with the tab bar still visible, re-tapping Search pops to the root,
and Android Back pops one level.

## Architecture

| iOS (SwiftUI) | Android |
|---|---|
| `Database.swift` (SQLite C API) | `data/Database.kt` (framework `SQLiteDatabase`) |
| custom `fold()` SQL function | precomputed `*_fold` shadow columns (`DatabaseProvider.kt`) |
| `QueryParser`, `QuizEngine`, models | ported ~1:1 to Kotlin |
| `WikipediaClient` (URLSession) | `WikipediaClient.kt` (OkHttp) |
| `PortraitLoader` (Vision face crop) | `FaceCropTransformation.kt` (Coil + ML Kit) |
| `FavoritesStore` / `QuizStats` (UserDefaults) | JSON file / SharedPreferences |
| `AppModel` + SwiftUI views | `WwwViewModel` (incl. tab/stack/screen state) + Compose screens in `ui/` |
| SwiftUI system styling | iOS design kit (`Theme.kt`, `IosComponents.kt`, `SwipeActions.kt`) |
| `WWW_*` launch env vars (DEBUG) | `WWW_*` intent extras (debug builds, `DebugHooks.kt`) |

The database (`app/src/main/assets/whoWasWhen.db`) is copied verbatim from the iOS
bundle. On first launch it is copied to internal storage and the `*_fold` columns
are built once (accent/case-insensitive search, matching the iOS `foldForSearch`).

## Building

Requires JDK 17 and the Android SDK (compileSdk 35, minSdk 26).

```bash
./gradlew :app:assembleDebug
```

`local.properties` points `sdk.dir` at the SDK. Open the `android/` folder directly
in Android Studio to build and run from the IDE.

## Running

```bash
# boot an emulator (or plug in a device with USB debugging), then:
./gradlew :app:installDebug
adb shell am start -n com.giovannicoppola.whowaswhen/.MainActivity
```

Debug builds accept the same automation hooks as the iOS `WWW_*` env vars,
as intent extras, to jump straight to a screen for screenshots:

```bash
adb shell am start -S -n com.giovannicoppola.whowaswhen/.MainActivity \
    --es WWW_QUERY 1789 --es WWW_DETAIL Washington
```

`WWW_TAB=discover|quiz|favorites`, `WWW_QUERY`, `WWW_DETAIL`, `WWW_LINEAGE=<title>`
(+ `WWW_TIMELINE=1`), `WWW_QUIZ=1|events|rulers|people|works` (+ `WWW_ANSWER=1`,
`WWW_SCORE=1` for the new-best/confetti screen, `WWW_CONFETTI=<seconds>` to
freeze the confetti for a still), `WWW_DARK=1|0`. Release builds
ignore them. A debug and a release build are signed with different keys, so
switching between them on one device needs an `adb uninstall` first.

## Updating the data

Replace `app/src/main/assets/whoWasWhen.db` with a newer build and bump
`ASSET_VERSION` in `DatabaseProvider.kt` so the working copy (and its fold columns)
are re-seeded on the next launch.
