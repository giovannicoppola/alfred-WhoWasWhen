# Submitting WhoWasWhen to the App Store (public release)

This picks up where **[TESTFLIGHT.md](TESTFLIGHT.md)** leaves off. TestFlight gets a
build to internal testers; the steps below take that same build through **App
Review** to a public listing.

Reuse the project config already documented in TESTFLIGHT.md (team `VDG762YNX9`,
bundle id `com.giovannicoppola.WhoWasWhen`, automatic signing, build/version in
`ios/project.yml`).

## 0. Decide how the app makes money (or not)

Pick this **before** you fill in pricing, because it changes which agreements and
build work you need. See [Monetization options](#monetization-options) below for the
full comparison.

| If you choose… | Extra setup before submitting |
|----------------|-------------------------------|
| **Free** | Nothing — no banking/tax agreement needed. |
| **Paid up front** | Sign the **Paid Apps agreement** + add banking & tax (step 1). |
| **In-App Purchase / subscription** | Paid Apps agreement + create the IAP products + **StoreKit** code in the app. |

WhoWasWhen ships today as a **free, offline, no-account, no-tracking** app. The
recommendation at the bottom keeps it that way.

## 1. One-time account setup for paid offerings

Only needed if you charge anything (up-front price **or** in-app purchases). Skip
entirely for a free app.

1. App Store Connect → **Business** → sign the **Paid Applications Agreement**.
2. Add **Bank account** (where payouts go) and **Tax** forms (e.g. US W-9 / W-8BEN,
   plus any regional tax info Apple requests).
3. Wait for all of these to show **Active**. Until then, paid pricing and IAPs are
   greyed out.

## 2. Complete the App Store listing (metadata)

In App Store Connect → your app → the **iOS App** version page. Required fields for
a public release (internal TestFlight didn't need these):

- **Name** (≤30 chars) and **Subtitle** (≤30 chars)
- **Promotional text** (optional, editable without a new build)
- **Description** — what the app does; reuse the language in
  [README.md](README.md)
- **Keywords** (100 chars, comma-separated) — e.g.
  `history,timeline,rulers,popes,consuls,presidents,kings,year`
- **Support URL** and **Marketing URL** — point at the
  [landing page](../docs/index.html)
- **Category** — Primary: **Reference** (Secondary: **Education**)
- **Copyright** — e.g. `2026 Giovanni Coppola`

## 3. Screenshots

Required for public release. Upload at least one set; Apple displays the 6.7"/6.9"
set scaled down for smaller devices.

- **6.9" (iPhone 16 Pro Max)** — 1320×2868 (or its set) — **required**
- **6.5"/6.7"** set if you want pixel-perfect on older Pro Max sizes
- Capture them from the Simulator (**File → New Screen Recording / ⌘S** on a frame)
  or a device. The repo's existing marketing shots live in `../docs/screenshots/`.
- Optional **App Preview** video (15–30s).

## 4. App privacy & ratings

- **App Privacy ("nutrition label")** — App Store Connect → your app → **App
  Privacy**. WhoWasWhen collects **no data**: choose **"Data Not Collected."** This
  matches the [privacy policy](../docs/privacy.html) and the
  `ITSAppUsesNonExemptEncryption = NO` compliance flag.
- **Age Rating** — fill the questionnaire; with only historical reference content
  this lands at **4+**.
- **Content Rights** — confirm whether it contains third-party content. Data is
  factual/historical; Wikipedia links open in the browser, not embedded.

## 5. Pricing & availability

- App Store Connect → your app → **Pricing and Availability**.
- Set the **price tier** (Free, or a paid tier if you completed step 1).
- Choose **country/region availability** (default: all).
- Optionally set a release **pre-order** or schedule.

## 6. Attach the build & submit for review

1. Confirm the build you tested on TestFlight is the one you want (or upload a new
   one — **bump `CURRENT_PROJECT_VERSION`** first, per TESTFLIGHT.md "Subsequent
   uploads").
2. On the version page, under **Build**, click **+** and select that build.
3. Set **Release option**:
   - **Automatically** release after approval, or
   - **Manually** release (you press the button), or
   - **Phased release** over 7 days for existing users on updates.
4. Click **Add for Review → Submit**.
5. **Beta App Review** is *not* required for internal TestFlight, but **App Review**
   *is* required for public release. Typical turnaround is ~24–48h.

## 7. After approval

- If you chose manual release, press **Release this version**.
- Watch **App Analytics** and the **Ratings & Reviews** tab.
- Future updates: bump version/build, archive, upload, attach, resubmit.

---

## Monetization options

Practical choices for a reference app like this, with what each one costs you to
build and run.

### 1. Free — *recommended*

- **What:** no price, no in-app purchases.
- **Setup:** none beyond a normal submission. No Paid Apps agreement, no
  banking/tax.
- **Fits the product:** the app's whole pitch is *instant, offline, private*. Free
  keeps that promise and maximizes reach for a niche history tool.

### 2. Paid up front (one-time purchase)

- **What:** a single price (e.g. tier 1–3) to download; no IAP code needed.
- **Setup:** Paid Apps agreement + banking/tax (step 1). Set a price tier (step 5).
- **Trade-off:** simplest paid model, but a paywall on an unknown reference app
  suppresses downloads. Apple takes 15–30%.

### 3. Freemium with In-App Purchase (non-consumable unlock)

- **What:** ship free with core search; sell a one-time **"Pro" unlock** (e.g.
  full lineages, extra titles, themes) as a **non-consumable** IAP.
- **Setup:** Paid Apps agreement; create the IAP product in App Store Connect; add
  **StoreKit 2** purchase + restore code in the app. IAPs are reviewed with the
  build.
- **Trade-off:** best revenue/reach balance for a paid model, but it's real app
  work (purchase flow, restore, gating a feature) and you must define what's behind
  the wall.

### 4. "Tip jar" / support (consumable or non-consumable IAP)

- **What:** the app stays fully free; users can **optionally** buy a small tip to
  support development.
- **Setup:** same as #3 (Paid Apps agreement + StoreKit), but nothing is gated.
- **Trade-off:** keeps the free, full-feature experience while allowing goodwill
  revenue. Low effort, low/unpredictable income.

### 5. Subscriptions (auto-renewable)

- **What:** recurring fee for ongoing value.
- **Setup:** Paid Apps agreement; auto-renewable subscription group + StoreKit;
  Apple expects continuously delivered value (e.g. regularly updated data, a
  cloud-synced feature).
- **Trade-off:** **not a good fit** — a mostly-static historical dataset doesn't
  justify a recurring charge, and reviewers scrutinize subscriptions that don't add
  ongoing value.

### 6. Ads

- **What:** display/banner ads via an ad SDK.
- **Trade-off:** **discouraged.** Ad SDKs collect data and add a third-party
  dependency, which directly contradicts the "no data collected" privacy label and
  the offline, dependency-free design. Avoid unless you change that positioning.

### Recommendation

Ship **free** for the initial public release to build an audience. If you later want
revenue without breaking the privacy/offline promise, add a **tip jar (#4)** or a
**one-time Pro unlock (#3)** — both keep the app private and don't require a
recurring-value story the data can't support. Avoid subscriptions and ads.
