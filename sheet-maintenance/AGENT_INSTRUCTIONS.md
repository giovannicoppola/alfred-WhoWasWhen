# Agent instructions: WhoWasWhen Google Sheet maintenance

This document is for **AI agents** (Cursor, etc.) maintaining the master spreadsheet that feeds the Alfred WhoWasWhen workflow database.

Human setup summary: see [README.md](README.md).

---

## 1. System overview

```
Google Sheet (source of truth)
    ↓  whowaswhen build script (outside this repo)
whoWasWhen.db
    ↓  Alfred workflow (ruler-query.go)
Alfred search results
```

**Spreadsheet ID:** `1GKI1744hxSBmB75CrIYssK6Y8-Hd48kpaggvOG1kUM8`

| Tab | GID | Role |
|-----|-----|------|
| **Periods** | 0 | One row per reign/title period. Key columns: `Progr`, `Title`, `RulerID`, `Period`, `CountCheck` |
| **Rulers** | 2053495317 | One row per ruler/title summary. Key columns: `RulerID` (D), `Name` (C), `Wikipedia` (J), `Personal Name or House` (M) |
| **Events** | 877936494 | Historical events (separate maintenance) |
| **consuls** | 1764968386 | Roman consul source data |

**Critical ID mapping:** Sheet column `Progr` on **Periods** = `byPeriod.periodID` in the SQLite DB (not `progrTitle`).

---

## 2. Authentication

Reuse the **alfred-gsheets** service account ([alfred-gsheets](https://github.com/giovannicoppola/alfred-gsheets) repo).

1. Service account JSON path → env var **`KEYFILE`** (same as alfred-gsheets Workflow Configuration → Key File).
2. Spreadsheet shared with service account email as **Editor**.

```bash
export KEYFILE="/path/to/service-account.json"
```

Or set `credentials:` in `config.yaml` (gitignored). `KEYFILE` wins if both are set.

**Never commit** JSON keys or `config.yaml`.

---

## 3. Repository layout

```
sheet-maintenance/
  AGENT_INSTRUCTIONS.md      ← this file
  README.md                  ← human quick start
  sheets_common.py           ← shared API helpers
  apply_merged_ruler_patches.py
  add_events.py
  audit_merged_rulers.py
  patches/merged-rulers.yaml   ← machine-readable fixes (versioned)
  patches/events/              ← event batches for add_events.py
  config.example.yaml
  requirements.txt
```

---

## 4. Standard agent workflow

### Step 0 — Environment

```bash
cd sheet-maintenance
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export KEYFILE="..."
```

### Step 1 — Discover (after sheet structure changes)

```bash
python apply_merged_ruler_patches.py --discover
```

Confirm **Periods** and **Rulers** tabs match `patches/merged-rulers.yaml` → `sheets:` and column maps.

### Step 2 — Audit (find new bugs)

```bash
python audit_merged_rulers.py
python audit_merged_rulers.py --json   # for programmatic use
```

Interpreting results:

- **Merged-ruler bug:** same `RulerID` on **Periods** rows that cannot be one person (e.g. Ferdinand I HRE 1558 + Austria 1835).
- **CountCheck = 2** on Periods often flags these (not always — verify dates).
- **Roman consul homonyms** (~400+ cases): same name across centuries — lower priority; disambiguate in `Name` or split IDs deliberately.
- **Legitimate multi-title** (do NOT split): Franz II (HRE + Austria), Louis the German, James VI/I (Scotland 1567+ + England 1603+), contemporary France+Naples.

### Step 3 — Draft fix in YAML

Edit `patches/merged-rulers.yaml`. Use a **new tier letter** for each batch (e.g. `E`, `F`) so `--tier` applies only new work.

#### Move period to existing orphan `rulerID` (preferred)

Check **Rulers** tab for a row with target `RulerID` and no conflicting periods, or query local DB:

```sql
SELECT rulerID, name, wikipedia FROM rulers ru
LEFT JOIN byPeriod p ON ru.rulerID = p.rulerID
WHERE p.periodID IS NULL AND ru.name LIKE '%Name%';
```

```yaml
ruler_id_moves:
  - { progr: 913, from_ruler_id: 744, to_ruler_id: 865, tier: D, note: "short reason" }
```

#### Move period + create new ruler

Pick `ruler_id` = `MAX(rulerID) + 1` from Rulers tab or DB.

```yaml
ruler_id_moves:
  - { progr: 1022, from_ruler_id: 455, to_ruler_id: 3441, tier: E, note: "..." }

new_rulers:
  - { ruler_id: 3441, name: "Philip II", personal_name: "Habsburg",
      wikipedia: "https://en.wikipedia.org/wiki/Philip_II_of_Spain", tier: E }

ruler_updates:
  - { ruler_id: 455, wikipedia: "https://en.wikipedia.org/wiki/Philip_II_of_France", tier: E }
```

**Rulers tab has no `biography` column** — `biography` in YAML is ignored; subtitles are built at DB generation. Only `wikipedia`, `name`, `personal_name` are written.

### Step 4 — Dry run (mandatory before apply)

```bash
python apply_merged_ruler_patches.py --dry-run --tier E
```

Review:

- Each `progr` → expected `from_ruler_id` → `to_ruler_id`
- Warnings about already-applied rows (safe to ignore if idempotent)
- New ruler rows not duplicating existing IDs

### Step 5 — Apply

```bash
python apply_merged_ruler_patches.py --apply --tier E
```

**Order inside script:** append `new_rulers` → batch cell updates (Periods + Rulers).

### Step 6 — Verify

1. Re-export or API-read affected Periods rows (`Progr`, `RulerID`).
2. Tell user to run Alfred: `::whoWasWhen-refresh`
3. Spot-check searches mentioned in patch `note` fields.

```bash
python audit_merged_rulers.py   # unpatched_progrs should shrink
```

---

## 5. Patch tiers (history)

| Tier | Status | Description |
|------|--------|-------------|
| A | Applied | Orphan rulerID splits (Ferdinand, Alexanders, James, Mary, etc.) |
| B | Applied | New IDs 3425–3429 (Constantine I Scotland, Naples Philips) |
| C | Applied | Pope/Antipope splits 3430–3440 |
| D | Applied | Constantine II → 865 + 902 |
| E+ | — | Future batches |

Re-applying an old tier prints warnings when `from_ruler_id` no longer matches; generally harmless.

---

## 6. Common bug patterns

| Pattern | Example | Fix |
|---------|---------|-----|
| Same regnal name, different countries/centuries | Ferdinand I HRE vs Austria | Split `RulerID` on Periods |
| Pope + Antipope same name | Clement VII | Antipope row → new `rulerID` |
| Scotland vs England/James numbering | James I 1406 vs James VI/I | Early Scotland → orphan 930 |
| France Capet vs Spain/Naples Philip | Philip IV | Naples period → new Habsburg ID |
| Roman emperor + Scottish king | Constantine I/II/III | Move Scottish/Antipope off emperor ID |
| Interregnum placeholder | rulerID 805 | Special — not a person; do not merge-fix as ruler |

---

## 7. What agents must NOT do

- Do not edit the live sheet by hand when the API scripts can do it.
- Do not commit `config.yaml`, `.venv/`, or `*.json` credentials.
- Do not split **legitimate** multi-title same-person records (see §4 Step 2).
- Do not write to Rulers column G (`Occur_periods`) via biography fallback — there is no biography column.
- Do not run `--apply` without `--dry-run` first in the same session.
- Do not change `Progr` values — only `RulerID` (and Rulers tab fields).

---

## 8. User requests → agent actions

| User says | Agent does |
|-----------|------------|
| "Audit the sheet" | Run `audit_merged_rulers.py`, summarize top findings |
| "Fix X like Ferdinand" | Research progr/rulerIDs, add YAML tier, dry-run, apply |
| "Apply tier E" | `--dry-run --tier E` then `--apply --tier E` |
| "KEYFILE is …" | Export KEYFILE, run discover/audit/apply |
| "What happened with Y?" | Grep Periods + Rulers for name; check if in `merged-rulers.yaml` |
| "Add events / battles to the sheet" | `add_events.py --list`, draft YAML, dry-run, apply after confirm |
| "Refresh Alfred" | Remind: `::whoWasWhen-refresh` after sheet changes |

---

## 9. Events maintenance

Use **`add_events.py`** for the **Events** tab (append-only). Ruler logic stays in `apply_merged_ruler_patches.py`.

### Events tab columns

| Column | Role |
|--------|------|
| **Progr** | Row ID (do not reuse; script assigns `max+1`) |
| **Event Name** | Searchable title |
| **Sorting year** | Start year (negative = BCE) |
| **Numerical year** | Start or range for DB (`1618–1648`, `-480`) |
| **Notes** | Subtitle in Alfred |
| **Wikipedia** | Enter action URL |
| **Event Category** | e.g. `European History` |
| **Year or Year Range** (×3) | Display strings (`1631 CE`, etc.) — auto-filled by script |
| **Month** / **Day** | Exact start date (integers, blank = unknown) — feeds the iOS "On this day" |

SQLite `byEvents`: `eventName`, `startYear`, `endYear`, `notes`, `wikipedia`,
`startMonth`, `startDay` (the last two NULL when Month/Day are blank).

### Event dates (Month/Day)

Use **`add_event_dates.py`** to fill Month/Day from Wikidata (P585 "point in
time", else P580 "start time"), resolved through each row's Wikipedia URL —
or by en.wikipedia title/search match when there is no URL. Dates embedded in
names ("Battle of Rocroi (May 19)") are a second source and win on conflict.
A Wikidata year that doesn't match Sorting year (±1) is skipped as MISMATCH.

```bash
python add_event_dates.py --dry-run          # writes event-dates-report.tsv
python add_event_dates.py --apply            # after the user reviews the report
```

Rows with a Month already set are skipped, so re-runs only fill new events.

### Events workflow

```bash
python add_events.py --list --query "thirty years"
python add_events.py --dry-run --file patches/events/thirty-years-war-battles.yaml
python add_events.py --apply --file patches/events/thirty-years-war-battles.yaml
```

1. `--list` / `--query` — avoid duplicates (exact, accent-insensitive, and same core name without dates)
2. Draft YAML in `patches/events/`
3. `--dry-run` — review planned Progr numbers; **SKIP** = duplicate, **WARN** = similar name still appended
4. `--apply` — append rows (only after user confirms bulk adds)
5. User runs `::whoWasWhen-refresh`

Optional `tier:` on each event; filter with `--tier TYW`.

Optional `war:` on an event (or `batch.war` for the whole file) — appended to the end of **Notes** (Alfred subtitle) as ` — Thirty Years' War` when not already mentioned. Update existing rows with `--update-notes`.

### Duplicate detection and merge

Duplicates require a **matching sorting year** (±1 year for same-named events like COVID/GFC). Same name + different year is **not** a duplicate (e.g. US Presidential Election rows).

```bash
python audit_event_duplicates.py          # list duplicate clusters
python merge_event_duplicates.py --dry-run
python merge_event_duplicates.py --apply  # merge notes/wiki, delete extra rows
```

### Events YAML example

```yaml
events:
  - name: "Battle of Rocroi (May 19)"
    start_year: 1643
    end_year: 1643
    notes: "French victory ending Spanish military supremacy in Europe."
    wikipedia: "https://en.wikipedia.org/wiki/Battle_of_Rocroi"
    category: "European History"
    tier: TYW
```

Cursor skill: `.cursor/skills/whowaswhen-events/SKILL.md`

---

## 10. Extending scripts

- **Events tab:** `add_events.py` + `patches/events/` (see §9).
- **Consuls / other tabs:** add script + YAML schema; keep Periods logic separate.
- **Idempotency:** `from_ruler_id` in YAML enables safe re-runs.
- **Shared code:** put helpers in `sheets_common.py`.

---

## 11. Related repos

- [alfred-WhoWasWhen](https://github.com/giovannicoppola/alfred-WhoWasWhen) — Alfred workflow + `ruler-query.go`
- [alfred-gsheets](https://github.com/giovannicoppola/alfred-gsheets) — service account setup, sheet browsing
