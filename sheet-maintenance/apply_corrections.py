#!/usr/bin/env python3
"""Review and apply the Corrections queue (phone-submitted curation).

The iOS admin app appends rows to the **Corrections** tab:

  Timestamp | Action | Tab | Key | Field | Snapshot | Proposed | Note | Status | Applied

Actions:
  edit          change one whitelisted field on a Rulers or Events row
  delete-event  remove an Events row (typically a duplicate)
  note          free-text to-do about a record — listed, never auto-applied

Keys: Rulers rows are `rulerID:<n>`; Events rows are `event:<name>|<sorting year>`
(resolved with the same accent-insensitive folding the search uses).

The Snapshot column holds the value the phone saw at submission time; if the
live cell has changed since, the correction is flagged STALE and skipped.

Usage:
  python apply_corrections.py --list
  python apply_corrections.py --dry-run          # writes corrections-report.tsv
  python apply_corrections.py --apply            # after the user reviews
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
from typing import Any

from sheets_common import (
    DEFAULT_CONFIG,
    build_sheets_service,
    col_index_to_letter,
    fold_for_search,
    get_sheet_values,
    list_sheets,
    load_spreadsheet_config,
    normalize_header,
)

QUEUE_SHEET = "Corrections"
EDITABLE = {
    "Rulers": ["Name", "Epithet", "Personal Name or House", "Notes",
               "Wikipedia", "Born", "Died"],
    "Events": ["Event Name", "Notes", "Wikipedia", "Month", "Day",
               "Event Category"],
}


def header_index(header: list[str]) -> dict[str, int]:
    idx: dict[str, int] = {}
    for i, h in enumerate(header):
        idx.setdefault(normalize_header(h), i)
    return idx


def cell(row: list, i: int | None) -> str:
    return str(row[i]).strip() if i is not None and len(row) > i else ""


# ---------------------------------------------------------------- targets

class SheetData:
    """One target tab: header index plus row lookups by key."""

    def __init__(self, service, spreadsheet_id: str, title: str):
        self.title = title
        self.rows = get_sheet_values(service, spreadsheet_id, title, "A1:Z6000")
        self.idx = header_index(self.rows[0])

    def col(self, header_name: str) -> int | None:
        return self.idx.get(normalize_header(header_name))


def find_ruler_row(rulers: SheetData, ruler_id: str) -> int | None:
    c = rulers.col("RulerID")
    for i, row in enumerate(rulers.rows[1:], start=2):
        if cell(row, c) == ruler_id:
            return i
    return None


def find_event_rows(events: SheetData, name: str, year: str) -> list[int]:
    name_c, year_c = events.col("Event Name"), events.col("Sorting year")
    want = fold_for_search(name)
    hits = []
    for i, row in enumerate(events.rows[1:], start=2):
        if fold_for_search(cell(row, name_c)) == want and cell(row, year_c) == str(year).strip():
            hits.append(i)
    return hits


def resolve(key: str, tab: str, rulers: SheetData, events: SheetData
            ) -> tuple[int | None, str]:
    """→ (sheet row number, problem) for a queue key."""
    if tab == "Rulers" and key.startswith("rulerID:"):
        row = find_ruler_row(rulers, key.split(":", 1)[1])
        return (row, "" if row else "NOT-FOUND rulerID")
    if tab == "Events" and key.startswith("event:"):
        name, _, year = key.split(":", 1)[1].rpartition("|")
        hits = find_event_rows(events, name, year)
        if len(hits) == 1:
            return hits[0], ""
        return None, "NOT-FOUND event" if not hits else f"AMBIGUOUS {len(hits)} rows"
    return None, f"BAD-KEY {key!r}"


# ------------------------------------------------------------------- plan

def build_plan(service, spreadsheet_id: str) -> tuple[list[dict[str, Any]], SheetData, SheetData]:
    queue = get_sheet_values(service, spreadsheet_id, QUEUE_SHEET, "A1:J2000")
    rulers = SheetData(service, spreadsheet_id, "Rulers")
    events = SheetData(service, spreadsheet_id, "Events")

    plan = []
    for qrow_n, row in enumerate(queue[1:], start=2):
        entry = {
            "qrow": qrow_n,
            "when": cell(row, 0), "action": cell(row, 1), "tab": cell(row, 2),
            "key": cell(row, 3), "field": cell(row, 4), "snapshot": cell(row, 5),
            "proposed": cell(row, 6), "note": cell(row, 7), "qstatus": cell(row, 8),
            "row": None, "current": "", "status": "",
        }
        if not entry["action"]:
            continue
        if entry["qstatus"] and entry["qstatus"] != "pending":
            entry["status"] = f"SKIP already {entry['qstatus']}"
            plan.append(entry)
            continue
        if entry["action"] == "note":
            entry["status"] = "MANUAL note"
            plan.append(entry)
            continue

        target = rulers if entry["tab"] == "Rulers" else events
        row_n, problem = resolve(entry["key"], entry["tab"], rulers, events)
        entry["row"] = row_n
        if problem:
            entry["status"] = problem
            plan.append(entry)
            continue

        if entry["action"] == "edit":
            if entry["field"] not in EDITABLE.get(entry["tab"], []):
                entry["status"] = f"REJECT field {entry['field']!r} not editable"
                plan.append(entry)
                continue
            c = target.col(entry["field"])
            if c is None:
                entry["status"] = f"NOT-FOUND column {entry['field']!r}"
                plan.append(entry)
                continue
            entry["current"] = cell(target.rows[row_n - 1], c)
            if entry["current"] == entry["proposed"]:
                entry["status"] = "SKIP already applied"
            elif entry["current"] != entry["snapshot"]:
                entry["status"] = (f"STALE cell changed since submission "
                                   f"({entry['snapshot']!r} -> {entry['current']!r})")
            else:
                entry["status"] = "OK edit"
        elif entry["action"] == "delete-event":
            name_c = events.col("Event Name")
            entry["current"] = cell(events.rows[row_n - 1], name_c)
            entry["status"] = "OK delete"
        else:
            entry["status"] = f"REJECT unknown action {entry['action']!r}"
        plan.append(entry)
    return plan, rulers, events


def print_list(plan: list[dict[str, Any]]) -> None:
    pending = [e for e in plan if not e["status"].startswith("SKIP")]
    if not pending:
        print("Queue is empty — nothing pending.")
        return
    for e in pending:
        loc = f"{e['tab']}!{e['row'] or '?'}"
        if e["action"] == "edit":
            print(f"  [{e['qrow']}] {e['status']:<12} {loc} {e['field']}: "
                  f"{e['current']!r} -> {e['proposed']!r}")
        elif e["action"] == "delete-event":
            print(f"  [{e['qrow']}] {e['status']:<12} {loc} DELETE {e['current']!r}")
        else:
            print(f"  [{e['qrow']}] {e['status']:<12} {e['key']}: {e['note']}")


def write_report(plan: list[dict[str, Any]], path: Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        f.write("qrow\twhen\taction\ttab\trow\tkey\tfield\tcurrent\tproposed\tnote\tstatus\n")
        for e in plan:
            f.write(f"{e['qrow']}\t{e['when']}\t{e['action']}\t{e['tab']}\t"
                    f"{e['row'] or ''}\t{e['key']}\t{e['field']}\t{e['current']}\t"
                    f"{e['proposed']}\t{e['note']}\t{e['status']}\n")


# ------------------------------------------------------------------ apply

def apply_plan(service, spreadsheet_id: str, plan, rulers: SheetData,
               events: SheetData) -> None:
    today = date.today().isoformat()
    edits = [e for e in plan if e["status"] == "OK edit"]
    deletes = [e for e in plan if e["status"] == "OK delete"]

    data = []
    for e in edits:
        target = rulers if e["tab"] == "Rulers" else events
        col_letter = col_index_to_letter(target.col(e["field"]))
        data.append({"range": f"'{e['tab']}'!{col_letter}{e['row']}",
                     "values": [[e["proposed"]]]})
    if data:
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"valueInputOption": "RAW", "data": data}).execute()
        print(f"Applied {len(data)} edits.")

    if deletes:
        sheet_ids = {s["properties"]["title"]: s["properties"]["sheetId"]
                     for s in list_sheets(service, spreadsheet_id)}
        # Bottom-up so earlier deletions don't shift later row numbers.
        requests = [{"deleteDimension": {"range": {
            "sheetId": sheet_ids["Events"], "dimension": "ROWS",
            "startIndex": e["row"] - 1, "endIndex": e["row"],
        }}} for e in sorted(deletes, key=lambda e: -e["row"])]
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id, body={"requests": requests}).execute()
        print(f"Deleted {len(deletes)} event rows.")

    # Mark the queue rows so re-runs skip them.
    marks = []
    for e in edits + deletes:
        marks.append({"range": f"'{QUEUE_SHEET}'!I{e['qrow']}:J{e['qrow']}",
                      "values": [["applied", today]]})
    if marks:
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"valueInputOption": "RAW", "data": marks}).execute()


# ------------------------------------------------------------------- main

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--list", action="store_true", help="Show pending corrections")
    parser.add_argument("--dry-run", action="store_true", help="Plan only (default)")
    parser.add_argument("--apply", action="store_true", help="Apply OK corrections")
    parser.add_argument("--report", type=Path, default=Path("corrections-report.tsv"))
    args = parser.parse_args()

    config, _, spreadsheet_id = load_spreadsheet_config(args.config)
    service = build_sheets_service(config)
    plan, rulers, events = build_plan(service, spreadsheet_id)

    print_list(plan)
    if args.list:
        return

    write_report(plan, args.report)
    counts: dict[str, int] = {}
    for e in plan:
        key = e["status"].split()[0]
        counts[key] = counts.get(key, 0) + 1
    print(f"\nPlan summary ({args.report}):")
    for key in sorted(counts):
        print(f"  {key:10} {counts[key]}")

    if args.apply:
        apply_plan(service, spreadsheet_id, plan, rulers, events)
        print("Remember: ::whoWasWhen-refresh + DB sync for the apps.")
    else:
        print("\nDry run only — review, then re-run with --apply.")


if __name__ == "__main__":
    main()
