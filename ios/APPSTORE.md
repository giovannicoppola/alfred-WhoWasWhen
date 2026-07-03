# Submitting WhoWasWhen to the App Store (public release)

This picks up where **[TESTFLIGHT.md](TESTFLIGHT.md)** leaves off. TestFlight gets a
build to internal testers; the steps below take that same build through **App
Review** to a public listing.

Reuse the project config already documented in TESTFLIGHT.md (team `VDG762YNX9`,
bundle id `com.giovannicoppola.WhoWasWhen`, automatic signing, build/version in
`ios/project.yml`).

## Resubmission after the 4.2 rejection (v1.1)

Build 1.0 (10) was rejected under **Guideline 4.2 Minimum Functionality**
("primarily offers content to view… not enough content/features"). v1.1 answers
it with four tabs of functionality on top of search:

- **On this day** — the search home shows an event that happened on today's
  date (300+ events now carry exact dates), linked to its detail view.
- **Discover** — featured ruler & event with shuffle, plus "100/200/300… years
  ago" anniversary sections, date-aware where the data allows.
- **Quiz** — endless multiple-choice trivia generated on-device from the
  database (mixed, rulers, events, notable-people, or per-title rounds;
  scores and bests tracked, with a confetti celebration for new records).
- **Favorites** — save any ruler or event; persists across launches.
- **Timeline** — every title's lineage as a visual timeline with century
  markers; ruler details show a reign-position bar within the title's era.
- **Ages & lifespans** — 1,600+ people carry birth/death years: single-year
  searches show each ruler's age that year, and details show the lifespan.
- **Notable people** — 200 of history's most famous artists, composers,
  writers, scientists, and philosophers join the rulers, searchable by year
  (e.g. "1888 artist" → van Gogh, Monet, Degas…).
- **Wikipedia enrichment** — portraits and summary paragraphs load inline
  (graceful offline fallback), on top of the existing 3,500+ rulers and ~900
  events spanning 776 BC–today.

When resubmitting, reply in the rejection thread in App Store Connect so the
resolution is tracked against the original review, and paste the same text
into the **App Review notes** field for the new build.

### Reply to App Review (paste into the rejection thread / review notes)

> Thank you for reviewing build 1.0 (10), which was rejected under
> Guideline 4.2 – Design – Minimum Functionality as primarily offering
> content to view. Version 1.1 (build 14) addresses this directly by adding
> substantial interactive functionality around the reference database:
>
> • QUIZ — an endless multiple-choice history quiz generated on-device from
> the database: mixed rounds, rulers, events, notable people, or any
> specific title ("Who was Pope in 1500?", "When did the French Revolution
> begin?", "When was van Gogh born?"). The bundled data yields thousands of
> distinct questions; per-category best scores are tracked, with a
> celebration animation for new records.
> • DISCOVER — a featured ruler and event with shuffle, plus "100/200/300…
> years ago" anniversary sections that favor events dated closest to today.
> • ON THIS DAY — the search home surfaces an event that happened on
> today's calendar date (300+ events now carry exact dates), linked to its
> detail view.
> • TIMELINES — every title's lineage as a scrollable visual timeline with
> century markers; each ruler's detail shows where the reign sits within
> the title's whole era.
> • FAVORITES — save any ruler or event; persists across launches.
>
> The dataset itself was also expanded for this release: 1,600+ figures now
> carry birth/death years — searching a year shows how old every ruler was
> at that moment (or that they were born or died that year) — and 200 of
> history's most famous artists, composers, writers, scientists, and
> philosophers join the rulers, searchable by year like everyone else
> (e.g. "1888 artist" finds van Gogh, Monet, and Degas with their ages that
> year, and the search filter offers All / People / Events).
>
> Everything works fully offline, with no account, no ads, and no data
> collection. Screenshots have been refreshed to show the new Quiz,
> Discover, and Timeline surfaces rather than search alone. We believe the
> app now offers rich interactive functionality well beyond viewing
> content, and we appreciate your taking another look.

### App Store description (paste into the Description field)

```
Who was king of France in 1789? Who was Pope when the Black Death struck?
How old was van Gogh in 1888 — and who was painting alongside him?

WhoWasWhen answers questions like these in an instant, from a single search
box, entirely offline.

SEARCH ANY YEAR
Type a year — 1789, a decade like 177*, a range like 1500-1600, or -44 for
BC — and see every ruler in office, how old each of them was that year, and
the events happening around them. Add a word to narrow it: "1789 france",
"15** pope", "1888 artist".

3,500+ HISTORICAL FIGURES
Kings, queens, emperors, popes, Roman consuls, presidents and prime
ministers — joined by 200 of history's most famous artists, composers,
writers, scientists, and philosophers. Portraits and summary paragraphs
load from Wikipedia when you're online; everything else lives on your
phone.

ON THIS DAY
The search screen greets you with an event that happened on today's date,
one tap from its full story.

DISCOVER
A featured ruler and event every visit (shuffle for more), plus what
happened 100, 200, 300… years ago today.

QUIZ
Endless multiple-choice trivia generated from the database — mixed rounds,
rulers, events, notable people ("When was van Gogh born?"), or any title
with enough holders. Best scores are tracked, and new records earn
confetti.

TIMELINES
Every title's lineage as a scrollable visual timeline: all 267 Popes, all
66 English Monarchs, every Roman consul — with century markers and each
reign's place in the era.

FAVORITES
Save any ruler or event to your own collection. No account needed.

PRIVATE AND OFFLINE BY DESIGN
The full history database ships inside the app. Search, quiz, timelines,
and favorites all work with no connection, no account, no ads, and no data
collection of any kind.
```

### Screenshots (6.9" set, 1320×2868 — ready to upload)

The refreshed set lives in `ios/screenshots-appstore/` (captured on the
iPhone 16 Pro Max simulator, clean 9:41 status bar):

1. `01-onthisday-gettysburg.png` / `01-onthisday-hattin.png` — search home
   with the "On this day" card (two variants for the July 3 slot; pick one)
2. `02-year-1789.png` — who ruled in 1789, with portraits and ages
3. `03-artists.png` — "1888 artist": the painters of 1888
4. `04-einstein.png` — detail view: lifespan line + era position bar
5. `05-discover.png` — Discover with featured cards and anniversaries
6. `06-quiz.png` — an event quiz question
7. `07-newbest.png` — new-best score screen with confetti
8. `08-timeline.png` — the English Monarchs timeline
9. `09-quiz-people.png` — a Notable people quiz question

Suggested upload order: 02, 03, 06, 09, 05, 04, 08, 01, 07 (lead with the
two strongest data screens, then interactivity).

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
