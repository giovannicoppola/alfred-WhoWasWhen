# Publishing WhoWasWhen to Google Play

**Live on Google Play** since 2026-10-16:
https://play.google.com/store/apps/details?id=studio.cimento.whowaswhen
(Cimento Studio organization account, app ID 4972748922919226354).

Steps 1–6 below are the record of the first launch; for later versions follow
"Shipping an update".

---

## What's ready (already built)

| Asset | Path |
|---|---|
| Signed release bundle (upload this) | `app/build/outputs/bundle/release/app-release.aab` (5.8 MB, versionCode 4 / 1.1) |
| Signed release APK (sideload/testing) | `app/build/outputs/apk/release/app-release.apk` (5.6 MB) |
| Hi-res store icon (512×512) | `play/play-store-icon-512.png` |
| Feature graphic (1024×500) | `play/feature-graphic-1024x500.png` |
| Phone screenshots | `play/screenshots-9x16/01-home … 07-newbest` (framed from the raw `play/screenshots/` captures) |
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
3. **Done:** the app lives on the **Cimento Studio organization account**. The
   "closed test with ≥12 testers for 14 days" rule only applies to new *personal*
   accounts, so it doesn't apply here — production is open once the store listing
   and app-content forms are complete.

## Step 2 — Create the app  *(you)*
In the Console: **Create app** → name "WhoWasWhen", language, "App", "Free". The
package name **`studio.cimento.whowaswhen`** (Cimento Studio account) is set by the bundle and is
permanent once uploaded.

## Step 3 — Upload the bundle & enable Play App Signing  *(you)*
1. **Release → Testing → Internal testing → Create new release.**
2. Upload `app-release.aab`.
3. Accept **Play App Signing** (recommended) — Google holds the real signing key;
   your `upload-keystore.jks` is just the upload key.
4. Add yourself as an internal tester and verify the install works. No closed
   test is required on the organization account (Step 1).

## Step 4 — Store listing  *(you, assets ready)*
- **App name:** WhoWasWhen
- **Short description** (≤80 chars): e.g. *"Who ruled in any year of history? Search, timelines, and a trivia quiz."*
- **Full description:** reuse/adapt the copy in `../ios/APPSTORE.md`.
- **App icon:** upload `play/play-store-icon-512.png`.
- **Feature graphic:** upload `play/feature-graphic-1024x500.png`.
- **Phone screenshots:** upload `play/screenshots-9x16/01-home` … `07-newbest` in
  order. Play only takes 16:9/9:16, so the raw 1080×2400 captures in
  `play/screenshots/` are framed to 1080×1920 by
  `python3 play/frame_screenshots.py play/screenshots play/screenshots-9x16`
  (seven; Play allows 2–8). They mirror the iOS App Store set: home with
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
  no analytics, no ads, no Google SDKs — see the ML Kit note below). Declare:
  no data collected.
- **Content rating:** fill the questionnaire — it will rate as *Everyone*.
- **Target audience:** not directed at children (choose 13+ or all ages as you
  prefer); no ads.
- **Permissions:** the app requests only `INTERNET`; no sensitive permissions to
  justify.
- **Government/financial/health:** none apply.

## Step 6 — Roll out  *(you)*
**Test and release → Production → Create new release** → add the bundle → Next →
Save → **Publishing overview → Send changes for review**. No closed test is
needed on the organization account. Managed publishing is off, so the release
goes live as soon as Google approves it (the first production review took under a week).

⚠️ Use the **web** Play Console. The first submission, made from the Play Console
phone app, landed on **Closed testing – Alpha** instead of Production: Google
approved it, but the app stayed invisible (Production "Inactive") until a real
Production release was created. After submitting, check **Latest releases and
bundles** — the *Track* column must say Production.

---

## Shipping an update
1. Bump `versionCode` (last used: **4**, so the next is ≥5 — codes 2–4 are all
   taken) and `versionName` in `app/build.gradle.kts`.
2. Rebuild the bundle (see "Rebuilding the bundle later").
3. **Production → Create new release** → Upload the `.aab` → release notes →
   Next → Save → **Publishing overview → Send changes for review**.
4. Release notes: each language tag on its own line, or the Console rejects
   them with "tag not closed":
   ```
   <en-US>
   What changed in this version.
   </en-US>
   ```
5. The "native code without debug symbols" warning is expected and doesn't
   block the release.

---

## Optional polish before launch
- **Real store copy** — write a punchy short + full description (the iOS
  `APPSTORE.md` is a good base).
- **Tablet screenshots** — optional; only if you want the app featured well on
  tablets.
- **Localized listings** — optional.

## Notes / decisions baked into the build
- `minSdk 26` (Android 8.0+), `targetSdk 36` — Play requires 36 for new apps (a 35 upload was rejected); meets the target-API
  requirement.
- Portrait face-centering uses the framework's on-device `android.media.FaceDetector`,
  **not ML Kit**: ML Kit reports usage metrics (device/app info, install IDs) to
  Google, which would break the "no data collected" Data safety answer and the
  privacy policy. Don't add Google SDKs (ML Kit, Firebase, Play services) without
  revisiting both.
- R8 minification + resource shrinking are on for release.
