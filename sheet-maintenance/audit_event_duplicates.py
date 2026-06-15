#!/usr/bin/env python3
"""Find duplicate Events rows (year-aware) on the WhoWasWhen spreadsheet."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sheets_common import (
    DEFAULT_CONFIG,
    ROOT_DIR,
    build_sheets_service,
    detect_events_sheet,
    enrich_existing_event_row,
    load_yaml,
    merge_event_fields,
    should_merge_events,
)
from add_events import detect_events_columns

DEFAULT_SPREADSHEET_PATCHES = ROOT_DIR / "patches" / "merged-rulers.yaml"


def load_all_events(service, spreadsheet_id: str, events_name: str) -> list[dict]:
    rows = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"'{events_name.replace(chr(39), chr(39)*2)}'!A:J",
    ).execute().get("values", [])
    header = rows[0] if rows else []
    col_map = detect_events_columns(header, {})

    events = []
    for row_idx, row in enumerate(rows[1:], start=2):
        if not row or not row[0]:
            continue
        try:
            progr = int(float(str(row[0]).strip()))
        except ValueError:
            continue
        name = row[1] if len(row) > 1 else ""
        events.append(
            enrich_existing_event_row(
                str(name),
                {
                    "progr": progr,
                    "row_idx": row_idx,
                    "name": name,
                    "notes": row[4] if len(row) > 4 else "",
                    "wikipedia": row[5] if len(row) > 5 else "",
                    "sorting_year": row[2] if len(row) > 2 else "",
                    "numerical_year": row[3] if len(row) > 3 else "",
                    "category": row[6] if len(row) > 6 else "",
                },
            )
        )
    return events, col_map, header


def find_duplicate_clusters(events: list[dict]) -> list[list[dict]]:
    clusters: list[list[dict]] = []
    used: set[int] = set()
    for i, a in enumerate(events):
        if i in used:
            continue
        cluster = [a]
        used.add(i)
        changed = True
        while changed:
            changed = False
            for j, b in enumerate(events):
                if j in used:
                    continue
                for member in cluster:
                    ok, _ = should_merge_events(member, b)
                    if ok:
                        cluster.append(b)
                        used.add(j)
                        changed = True
                        break
        if len(cluster) > 1:
            clusters.append(cluster)
    return clusters


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    config = load_yaml(args.config) if args.config.is_file() else {}
    sid = config.get("spreadsheet_id") or load_yaml(DEFAULT_SPREADSHEET_PATCHES)["spreadsheet_id"]
    service = build_sheets_service(config)
    events_name = detect_events_sheet(service, sid, (config.get("sheets") or {}).get("events"))
    events, _, _ = load_all_events(service, sid, events_name)
    clusters = find_duplicate_clusters(events)

    if args.json:
        payload = []
        for cluster in clusters:
            merged = merge_event_fields(cluster)
            payload.append(
                {
                    "keep_progr": merged["progr"],
                    "delete_progrs": [e["progr"] for e in merged["delete_rows"]],
                    "name": merged["name"],
                    "sorting_year": merged["sorting_year"],
                    "members": [{"progr": e["progr"], "name": e["name"]} for e in cluster],
                }
            )
        print(json.dumps(payload, indent=2))
        return

    print(f"Events: {len(events)}")
    print(f"Duplicate clusters: {len(clusters)}")
    print(f"Rows to delete if merged: {sum(len(c) - 1 for c in clusters)}")
    for cluster in sorted(clusters, key=lambda c: c[0]["progr"]):
        merged = merge_event_fields(cluster)
        print(f"\nKEEP progr {merged['progr']}  {merged['name']!r}  ({merged['sorting_year']})")
        for e in merged["delete_rows"]:
            ok, reason = should_merge_events(merged, e)
            print(f"  DELETE progr {e['progr']:>4} row {e['row_idx']:>4}  {e['name']!r}  [{reason}]")


if __name__ == "__main__":
    main()
