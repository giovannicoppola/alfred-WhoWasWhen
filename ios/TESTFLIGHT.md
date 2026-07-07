# Shipping WhoWasWhen to TestFlight (internal testing)

The project is already configured for distribution:

| Setting | Value |
|---------|-------|
| Team (`DEVELOPMENT_TEAM`) | `VDG762YNX9` |
| Bundle ID | `com.giovannicoppola.WhoWasWhen` |
| Signing | Automatic |
| Version / Build | `1.0` / `10` (`MARKETING_VERSION` / `CURRENT_PROJECT_VERSION`) |
| Export compliance | `ITSAppUsesNonExemptEncryption = NO` (HTTPS only) |
| App icon | 1024×1024, present (required by TestFlight) |

You drive the archive + upload from Xcode. Steps:

## 1. Register the App ID (one-time)

App Store Connect's "New App" Bundle ID dropdown only shows IDs that already
exist as an **App ID** in the Developer portal, so register it first:

1. Go to <https://developer.apple.com/account/resources/identifiers/list>.
2. Click **➕** next to "Identifiers".
3. **App IDs** → Continue → **App** → Continue.
4. Fill in:
   - **Description**: `WhoWasWhen` (just a label)
   - **Bundle ID**: **Explicit**, exactly `com.giovannicoppola.WhoWasWhen`
   - **Capabilities**: leave all **unchecked** (this app needs none; iCloud is off)
5. **Continue → Register**.

> Alternative: skip this and run **Product → Archive** in Xcode first — automatic
> signing registers the App ID for you. The bundle ID then appears in step 2.

## 2. Create the app record in App Store Connect (one-time)

1. Go to <https://appstoreconnect.apple.com> → **Apps** → **+** → **New App**.
2. Fill in:
   - **Platform**: iOS
   - **Name**: `WhoWasWhen` — this must be **globally unique** on the App Store.
     If it's taken, use something like `WhoWasWhen — History`.
   - **Primary Language**: your choice
   - **Bundle ID**: select `com.giovannicoppola.WhoWasWhen` (now in the dropdown)
   - **SKU**: any internal string, e.g. `whowaswhen-001`
3. Create. You don't need screenshots/metadata for *internal* TestFlight.

## 3. Generate the project & archive in Xcode

```bash
cd ios
xcodegen generate        # if the .xcodeproj isn't present
open WhoWasWhen.xcodeproj
```

In Xcode:

1. In the destination selector (top bar), choose **Any iOS Device (arm64)**.
   Archiving is disabled when a Simulator is selected.
2. **Product → Archive**.
   - On the first archive, Xcode will create the **Apple Distribution** certificate
     and an **App Store** provisioning profile automatically. Accept the prompts
     (you may be asked to sign in / pass 2FA).

## 4. Upload to TestFlight

When the **Organizer** opens after archiving:

1. Select the new archive → **Distribute App**.
2. Choose **App Store Connect** → **Upload**.
3. Keep the defaults (automatic signing, include symbols) → **Upload**.

## 4b. Command-line archive & upload (no Xcode GUI)

The whole archive + upload runs headless with an **App Store Connect API key**
(role App Manager), so it needs no Xcode App Store Connect session. Store the
`.p8` in `~/.appstoreconnect/private_keys/AuthKey_<KeyID>.p8` (chmod 600); the
Key ID and Issuer ID live in your local notes, **not** in this public repo.

```bash
# 1. bump build, regenerate (avoid `cd` — the shell aliases it)
xcodegen generate --spec ios/project.yml --project ios

# 2. archive (Release)
xcodebuild -project ios/WhoWasWhen.xcodeproj -scheme WhoWasWhen \
  -configuration Release -destination 'generic/platform=iOS' \
  -archivePath ios/build/WhoWasWhenNN.xcarchive archive -allowProvisioningUpdates

# 3. export + upload with the API key (export.plist: method app-store-connect,
#    destination upload, signingStyle automatic, teamID VDG762YNX9)
xcodebuild -exportArchive -archivePath ios/build/WhoWasWhenNN.xcarchive \
  -exportOptionsPlist export.plist -exportPath ios/build/exportNN \
  -allowProvisioningUpdates \
  -authenticationKeyID <KeyID> \
  -authenticationKeyIssuerID <IssuerID> \
  -authenticationKeyPath ~/.appstoreconnect/private_keys/AuthKey_<KeyID>.p8
```

For the admin build, swap the scheme to `WhoWasWhenAdmin` and the archive/app
name accordingly. **Do not** open the archive in the Organizer *and* upload from
the CLI for the same build — the Organizer auto-increments the build number, so
you'd get two builds. Use the latest VALID build when attaching for review.

## 5. Add internal testers

1. In App Store Connect → your app → **TestFlight** tab.
2. Wait for the build to move from **Processing** to ready (usually a few minutes;
   you'll get an email).
3. **Internal Testing** → create or pick an **Internal Group** → add testers.
   - Internal testers must be members of your team under **Users and Access**
     (up to 100). No Beta App Review is required for internal testers.
4. Enable the build for the group. Testers install via the **TestFlight** app on
   their iPhone.

## Subsequent uploads

- **Bump the build number** before each new upload — App Store Connect rejects a
  reused build number. Edit `CURRENT_PROJECT_VERSION` in `ios/project.yml`
  (e.g. `2`, `3`, …), run `xcodegen generate`, then archive again.
- Bump `MARKETING_VERSION` only when you want a new user-facing version (e.g. `0.2`).

## Troubleshooting

- **"No account for team / signing failed"**: open Xcode → Settings → Accounts and
  make sure the Apple ID for team `VDG762YNX9` is signed in.
- **"Missing Compliance" in TestFlight**: shouldn't happen — handled by
  `ITSAppUsesNonExemptEncryption = NO`. If it appears, answer "No" to the
  "uses non-exempt encryption" question.
- **Archive missing from Organizer**: confirm the destination was a device
  (not a Simulator) and the scheme's Archive action uses the **Release** config.
