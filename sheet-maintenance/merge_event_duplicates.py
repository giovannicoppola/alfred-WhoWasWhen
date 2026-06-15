#!/usr/bin/env python3
"""Merge duplicate Events rows on the WhoWasWhen Google Sheet."""

from __future__ import annotations

import argparse
from pathlib import Path

from sheets_common import (
    DEFAULT_CONFIG,
    ROOT_DIR,
    build_sheets_service,
    detect_events_sheet,
    load_yaml,
    merge_event_fields,
)
from audit_event_duplicates import find_duplicate_clusters, load_all_events

DEFAULT_SPREADSHEET_PATCHES = ROOT_DIR / "patches" / "merged-rulers.yaml"


def get_sheet_id(service, spreadsheet_id: str, sheet_name: str) -> int:
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    for entry in meta.get("sheets", []):
        if entry["properties"]["title"] == sheet_name:
            return entry["properties"]["sheetId"]
    raise SystemExit(f"Sheet {sheet_name!r} not found")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--dry-run", action="store_true", help="Show merge plan (default)")
    parser.add_argument("--apply", action="store_true", help="Merge and delete duplicate rows")
    args = parser.parse_args()

    if args.apply and args.dry_run:
        raise SystemExit("Use either --apply or --dry-run, not both")
    dry_run = not args.apply

    config = load_yaml(args.config) if args.config.is_file() else {}
    sid = config.get("spreadsheet_id") or load_yaml(DEFAULT_SPREADSHEET_PATCHES)["spreadsheet_id"]
    service = build_sheets_service(config)
    events_name = detect_events_sheet(service, sid, (config.get("sheets") or {}).get("events"))
    events, col_map, header = load_all_events(service, sid, events_name)
    clusters = find_duplicate_clusters(events)

    merges = [merge_event_fields(cluster) for cluster in clusters]
    delete_rows = sorted(
        {e["row_idx"] for m in merges for e in m["delete_rows"]},
        reverse=True,
    )

    print(f"Events sheet: {events_name!r}")
    print(f"Duplicate clusters: {len(clusters)}")
    print(f"Rows to delete: {len(delete_rows)}")
    print(f"mode: {'DRY RUN' if dry_run else 'APPLY'}\n")

    for merged in sorted(merges, key=lambda m: m["progr"]):
        print(f"KEEP progr {merged['progr']} row {merged['row_idx']}: {merged['name']!r}")
        if merged.get("notes"):
            print(f"  notes: {str(merged['notes'])[:100]}...")
        for e in merged["delete_rows"]:
            print(f"  DELETE progr {e['progr']} row {e['row_idx']}: {e['name']!r}")

    if dry_run:
        print("\nDry run complete. Re-run with --apply to merge.")
        return

    if not merges:
        print("Nothing to merge.")
        return

    quoted = events_name.replace("'", "''")
    updates = []
    for merged in merges:
        row_idx = merged["row_idx"]
        updates.extend(
            [
                {"range": f"'{quoted}'!{col_map['name']}{row_idx}", "values": [[merged["name"]]]},
                {"range": f"'{quoted}'!{col_map['notes']}{row_idx}", "values": [[merged["notes"]]]},
                {"range": f"'{quoted}'!{col_map['wikipedia']}{row_idx}", "values": [[merged["wikipedia"]]]},
            ]
        )

    service.spreadsheets().values().batchUpdate(
        spreadsheetId=sid,
        body={"valueInputOption": "USER_ENTERED", "data": updates},
    ).execute()
    print(f"Updated {len(merges)} keeper row(s).")

    sheet_id = get_sheet_id(service, sid, events_name)
    delete_requests = [
        {
            "deleteDimension": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "ROWS",
                    "startIndex": row_idx - 1,
                    "endIndex": row_idx,
                }
            }
        }
        for row_idx in delete_rows
    ]
    service.spreadsheets().batchUpdate(
        spreadsheetId=sid,
        body={"requests": delete_requests},
    ).execute()
    print(f"Deleted {len(delete_rows)} duplicate row(s).")
    print("Done. Rebuild Alfred DB: ::whoWasWhen-refresh")


if __name__ == "__main__":
    main()
