---
name: whowaswhen-events
description: >-
  Adds or lists historical events on the WhoWasWhen Google Sheet Events tab via
  sheet-maintenance/add_events.py. Use when the user asks to add events, battles,
  treaties, or other dated entries to WhoWasWhen, the Events tab, or Alfred event search.
---

# WhoWasWhen — Events maintenance

Add historical events to the master spreadsheet that feeds the Alfred WhoWasWhen workflow.

## Before you start

```bash
cd sheet-maintenance
source .venv/bin/activate   # create with: python3 -m venv .venv && pip install -r requirements.txt
export KEYFILE="/path/to/alfred-gsheets-service-account.json"
```

Spreadsheet ID: `1GKI1744hxSBmB75CrIYssK6Y8-Hd48kpaggvOG1kUM8`  
Full playbook: [sheet-maintenance/AGENT_INSTRUCTIONS.md](../../sheet-maintenance/AGENT_INSTRUCTIONS.md)

## Standard workflow

1. **Check what already exists**
   ```bash
   python add_events.py --list --query "thirty years"
   python add_events.py --list --query "breitenfeld"
   ```

2. **Research** — gather event name, year(s), short notes, Wikipedia URL, category.

3. **Draft YAML** in `sheet-maintenance/patches/events/` (copy an existing file or create new).

4. **Dry run (mandatory)**
   ```bash
   python add_events.py --dry-run --file patches/events/your-batch.yaml
   ```

5. **Show the user** the planned rows and any duplicate warnings. Do not apply without confirmation for bulk adds.

6. **Apply**
   ```bash
   python add_events.py --apply --file patches/events/your-batch.yaml
   ```

7. **Tell the user** to run Alfred: `::whoWasWhen-refresh`

## YAML format

```yaml
spreadsheet_id: "1GKI1744hxSBmB75CrIYssK6Y8-Hd48kpaggvOG1kUM8"
sheets:
  events: Events

events:
  - name: "Battle of Breitenfeld (September 17)"
    start_year: 1631
    end_year: 1631
    notes: "One sentence context."
    wikipedia: "https://en.wikipedia.org/wiki/Battle_of_Breitenfeld_(1631)"
    category: "European History"
    tier: BATCH-ID   # optional; filter with --tier BATCH-ID

batch:
  war: "Thirty Years' War"   # optional default for all events in file
```

The `war` field is appended to the end of `notes` (Alfred subtitle) as ` — Thirty Years' War`, unless the war is already mentioned in the notes.

To refresh notes on events already on the sheet:

```bash
python add_events.py --apply --update-notes --file patches/events/your-batch.yaml
```

## Naming conventions

- Battles: `Battle of …` with optional date in parentheses, e.g. `Battle of Lützen (November 16)`
- Single-day/year events: `start_year` = `end_year`
- Multi-year events: set both years; script fills Numerical year and display columns
- Categories used elsewhere: `European History`, `American History`, `Ancient Greek History`, `Roman History`, `Global History`

## Rules

- Never apply without a dry-run in the same session.
- Skip duplicates — exact name, accent-insensitive match, or same core name without `(date)` suffix
- Dry-run **WARN** lines flag similar names (fuzzy/substring); review before `--apply`
- Do not edit `Progr` on existing rows; new rows get `max(Progr)+1` automatically.
- Do not commit `config.yaml`, credentials, or `.venv/`.
- Ruler/Period fixes use `apply_merged_ruler_patches.py` — keep events separate.

## Example user requests

| User says | You do |
|-----------|--------|
| "Add main battles of the Thirty Years' War" | List existing TYW events → edit/use `patches/events/thirty-years-war-battles.yaml` → dry-run → ask → apply |
| "What events do we have for 1648?" | `python add_events.py --list --query 1648` |
| "Add the French Revolution timeline" | Research key events → new YAML batch → dry-run → apply after approval |

## Example batch

`sheet-maintenance/patches/events/thirty-years-war-battles.yaml` — 11 major battles (not applied by default).
