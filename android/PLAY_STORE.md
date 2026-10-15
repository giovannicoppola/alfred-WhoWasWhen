# Publishing WhoWasWhen to Google Play

This is the checklist for getting the Android app onto the Play Store. The
**technical prep is done** (see "What's ready" below); the remaining work is the
Play Console account, the store listing, and the compliance forms — the parts
only you can do.

---

## What's ready (already built)

| Asset | Path |
|---|---|
| Signed release bundle (upload this) | `app/build/outputs/bundle/release/app-release.aab` (6.4 MB, versionCode 2 / 1.1) |
| Signed release APK (sideload/testing) | `app/build/outputs/apk/release/app-release.apk` (5.6 MB) |
| Hi-res store icon (512×512) | `play/play-store-icon-512.png` |
| Feature graphic (1024×500) | `play/feature-graphic-1024x500.png` |
| Phone screenshots | `play/screenshots/01-home … 07-newbest` (iOS-style redesign, 2026-10-13) |
| Upload keystore (KEEP SAFE, gitignored) | `keystore/upload-keystore.jks` |
| Keystore credentials (gitignored) | `keystore.properties` |

### ⚠️ Back up the keystore first
`keystore/upload-keystore.jks` + its password (in `keystore.properties`) are your
**upload key**. If you lose it you can reset it via Google, but it's painful —
copy both somewhere safe (password manager / encrypted backup) before anything
else. They are gitignored, so they are **not** in the repo and won't be pushed.

### Rebuilding the bundle later
```bash
cd android
JAVA_HOME=/usr/local/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home \
  ./gradlew :app:bundleRelease
```
Bump `versionCode` (and usually `versionName`) in `app/build.gradle.kts` for every
new upload — Play rejects a reused `versionCode`.

---

## Step 1 — Google Play Developer account  *(you)*
1. Go to https://play.google.com/console and register. **One-time $25 fee.**
2. Complete **identity verification** (government ID; for an organization account,
   also D-U-N-S). This can take a few days — start it early.
3. **Heads-up on the testing requirement:** personal developer accounts created
   recently must run a **closed test with ≥12 testers for 14 continuous days**
   before Google will let you promote to production. That 14-day clock is usually
   the longest part of launching — so create the account and start a closed test
   as soon as you can.

## Step 2 — Create the app  *(you)*
In the Console: **Create app** → name "WhoWasWhen", language, "App", "Free". The
package name **`studio.cimento.whowaswhen`** (Cimento Studio account) is set by the bundle and is
permanent once uploaded.

## Step 3 — Upload the bundle & enable Play App Signing  *(you)*
1. **Release → Testing → Internal testing → Create new release.**
2. Upload `app-release.aab`.
3. Accept **Play App Signing** (recommended) — Google holds the real signing key;
   your `upload-keystore.jks` is just the upload key.
4. Add yourself as an internal tester and verify the install works, then move to
   **Closed testing** to start the 14-day clock (Step 1).

## Step 4 — Store listing  *(you, assets ready)*
- **App name:** WhoWasWhen
- **Short description** (≤80 chars): e.g. *"Who ruled in any year of history? Search, timelines, and a trivia quiz."*
- **Full description:** reuse/adapt the copy in `../ios/APPSTORE.md`.
- **App icon:** upload `play/play-store-icon-512.png`.
- **Feature graphic:** upload `play/feature-graphic-1024x500.png`.
- **Phone screenshots:** upload `play/screenshots/01-home` … `07-newbest` in
  order (seven; Play allows 2–8). They mirror the iOS App Store set: home with
  On this day, 1789, a quiz question, Discover, the Louis XVI detail sheet, the
  English Monarch timeline, and the new-best confetti. `00-launcher` is the
  home-screen icon, not needed for the listing. To retake them, use the debug
  build's `WWW_*` launch hooks (see `README.md`) — e.g. `WWW_CONFETTI=1.3`
  freezes the confetti for the new-best shot.
- **Category:** Education (or Books & Reference).

## Step 5 — Compliance forms  *(you)*
- **Privacy policy URL:** you already host one — use
  `https://giovannicoppola.github.io/alfred-WhoWasWhen/privacy.html`
  (from `docs/privacy.html`). Required.
- **Data safety form:** the app **collects and shares no user data**. It only
  makes outbound HTTPS calls to Wikipedia for portraits/summaries (no accounts,
  no analytics, no ads). Declare: no data collected.
- **Content rating:** fill the questionnaire — it will rate as *Everyone*.
- **Target audience:** not directed at children (choose 13+ or all ages as you
  prefer); no ads.
- **Permissions:** the app requests only `INTERNET`; no sensitive permissions to
  justify.
- **Government/financial/health:** none apply.

## Step 6 — Roll out  *(you)*
Internal testing → **Closed testing** (14 days, ≥12 testers) → **Production**.
Submit for review; first review typically takes a few days.

---

## Optional polish before launch
- **Real store copy** — write a punchy short + full description (the iOS
  `APPSTORE.md` is a good base).
- **Tablet screenshots** — optional; only if you want the app featured well on
  tablets.
- **Localized listings** — optional.

## Notes / decisions baked into the build
- `minSdk 26` (Android 8.0+), `targetSdk 35` — meets Play's current target-API
  requirement.
- ML Kit face detection uses the **unbundled** (Play services) model, which is why
  the download is ~5 MB instead of ~55 MB. It downloads the model on first use;
  on a device without Google Play services, portraits simply fall back to icons.
- R8 minification + resource shrinking are on for release.
