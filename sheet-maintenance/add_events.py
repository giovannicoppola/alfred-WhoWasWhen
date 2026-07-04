#!/usr/bin/env python3
"""Add historical events to the WhoWasWhen Google Sheet Events tab."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from sheets_common import (
    DEFAULT_CONFIG,
    ROOT_DIR,
    build_sheets_service,
    col_letter_to_index,
    detect_column,
    detect_column_optional,
    detect_events_sheet,
    detect_progr_column,
    discover_sheets,
    get_sheet_values,
    load_yaml,
    event_similarity_warnings,
    enrich_existing_event_row,
    should_merge_events,
)

DEFAULT_SPREADSHEET_PATCHES = ROOT_DIR / "patches" / "merged-rulers.yaml"


def resolve_spreadsheet_id(config: dict[str, Any], event_data: dict[str, Any]) -> str | None:
    sid = config.get("spreadsheet_id") or event_data.get("spreadsheet_id")
    if sid:
        return sid
    if DEFAULT_SPREADSHEET_PATCHES.is_file():
        return load_yaml(DEFAULT_SPREADSHEET_PATCHES).get("spreadsheet_id")
    return None


def tier_ok(item: dict[str, Any], tiers: set[str]) -> bool:
    return not tiers or str(item.get("tier", "")).upper() in tiers


def format_numerical_year(start: int, end: int) -> str:
    if start == end:
        return str(start)
    if start < 0 or end < 0:
        return f"{start}–{end}"
    return f"{start}–{end}"


def format_year_display(start: int, end: int) -> tuple[str, str, str]:
    if start < 0 or end < 0:
        if start == end:
            label = f"{abs(start)} BCE"
            return label, label, label
        label = f"{abs(start)}–{abs(end)} BCE"
        return label, label, label
    if start == end:
        label = f"{start} CE"
        return label, label, str(start)
    label = f"{start}–{end} CE"
    return label, label, f"{start}–{end}"


def format_event_notes(notes: str, war: str = "") -> str:
    """Build Alfred subtitle text; append parent war at the end when not already mentioned."""
    notes = str(notes or "").strip()
    war = str(war or "").strip()
    if not war:
        return notes
    if war.lower() in notes.lower():
        return notes
    if notes:
        return f"{notes} — {war}"
    return war


def apply_batch_defaults(data: dict[str, Any], specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    batch = data.get("batch") or {}
    default_war = batch.get("war") or data.get("default_war")
    if not default_war:
        return specs
    enriched: list[dict[str, Any]] = []
    for spec in specs:
        item = dict(spec)
        if not item.get("war"):
            item["war"] = default_war
        enriched.append(item)
    return enriched


def parse_event_spec(spec: dict[str, Any]) -> dict[str, Any]:
    name = str(spec.get("name", "")).strip()
    if not name:
        raise ValueError("event missing name")

    if "start_year" not in spec:
        raise ValueError(f"{name!r}: missing start_year")
    start = int(spec["start_year"])
    end = int(spec.get("end_year", start))
    if end < start:
        raise ValueError(f"{name!r}: end_year {end} before start_year {start}")

    sorting = str(start)
    numerical = format_numerical_year(start, end)
    display_h, display_i, display_j = format_year_display(start, end)

    return {
        "name": name,
        "start_year": start,
        "end_year": end,
        "notes": format_event_notes(spec.get("notes", ""), spec.get("war", "")),
        "wikipedia": str(spec.get("wikipedia", "") or ""),
        "category": str(spec.get("category", "") or "European History"),
        "sorting_year": sorting,
        "numerical_year": numerical,
        "year_display_1": display_h,
        "year_display_2": display_i,
        "year_display_3": display_j,
        "tier": spec.get("tier", ""),
        "note": spec.get("note", ""),
    }


def load_events_file(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    data = load_yaml(path)
    events = [e for e in data.get("events", []) if isinstance(e, dict)]
    if not events:
        raise SystemExit(f"No events found in {path}")
    return data, apply_batch_defaults(data, events)


def read_existing_events(
    service,
    spreadsheet_id: str,
    events_name: str,
    col_map: dict[str, str],
) -> tuple[list[dict[str, Any]], int]:
    rows = get_sheet_values(service, spreadsheet_id, events_name, "A:J")
    if not rows:
        return [], 0

    progr_col = col_map["progr"]
    name_col = col_map["name"]
    sort_col = col_map["sorting_year"]
    num_col = col_map["numerical_year"]

    pi = col_letter_to_index(progr_col)
    ni = col_letter_to_index(name_col)
    si = col_letter_to_index(sort_col)
    numi = col_letter_to_index(num_col)

    existing: list[dict[str, Any]] = []
    max_progr = 0
    for row_idx, row in enumerate(rows, start=1):
        if row_idx == 1:
            continue
        if len(row) <= pi or row[pi] in (None, ""):
            continue
        try:
            progr = int(float(str(row[pi]).strip()))
        except ValueError:
            continue
        max_progr = max(max_progr, progr)
        name = row[ni] if len(row) > ni else ""
        existing.append(
            enrich_existing_event_row(
                str(name),
                {
                    "progr": progr,
                    "row_idx": row_idx,
                    "name": name,
                    "sorting_year": row[si] if len(row) > si else "",
                    "numerical_year": row[numi] if len(row) > numi else "",
                },
            )
        )
    return existing, max_progr


def candidate_from_parsed(parsed: dict[str, Any]) -> dict[str, Any]:
    return enrich_existing_event_row(
        parsed["name"],
        {
            "name": parsed["name"],
            "sorting_year": str(parsed["start_year"]),
            "progr": 0,
            "row_idx": 0,
        },
    )


def match_existing_event(
    name: str, sorting_year: int, existing: list[dict[str, Any]]
) -> dict[str, Any] | None:
    candidate = enrich_existing_event_row(
        name,
        {"name": name, "sorting_year": str(sorting_year), "progr": 0, "row_idx": 0},
    )
    for row in existing:
        # should_merge_events returns (bool, reason); a bare 2-tuple is always
        # truthy, so the boolean must be unpacked before testing it.
        merge, _ = should_merge_events(candidate, row)
        if merge:
            return row
    return None


def plan_event_note_updates(
    specs: list[dict[str, Any]],
    existing: list[dict[str, Any]],
    tiers: set[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    updates: list[dict[str, Any]] = []
    warnings: list[str] = []
    for spec in specs:
        if not tier_ok(spec, tiers):
            continue
        try:
            parsed = parse_event_spec(spec)
        except ValueError as exc:
            warnings.append(str(exc))
            continue
        row = match_existing_event(parsed["name"], parsed["start_year"], existing)
        if row is None:
            warnings.append(f"not found on sheet: {parsed['name']!r}")
            continue
        updates.append(
            {
                "row_idx": row["row_idx"],
                "name": parsed["name"],
                "notes": parsed["notes"],
            }
        )
    return updates, warnings


def print_note_updates(updates: list[dict[str, Any]], warnings: list[str]) -> None:
    print(f"Notes to update: {len(updates)}")
    for item in updates:
        print(f"  row {item['row_idx']}: {item['name']!r}")
        print(f"    → {item['notes']}")
    if warnings:
        print("\nWarnings:")
        for warning in warnings:
            print(f"  ! {warning}")


def detect_events_columns(header: list[str], yaml_cols: dict[str, str]) -> dict[str, str]:
    progr_col = yaml_cols.get("progr") or detect_progr_column(header, "A")
    return {
        "progr": progr_col,
        "name": detect_column(header, ["event name", "name"], yaml_cols.get("name")),
        "sorting_year": detect_column(header, ["sorting year"], yaml_cols.get("sorting_year")),
        "numerical_year": detect_column(header, ["numerical year"], yaml_cols.get("numerical_year")),
        "notes": detect_column_optional(header, ["notes"], yaml_cols.get("notes")) or "E",
        "wikipedia": detect_column_optional(header, ["wikipedia"], yaml_cols.get("wikipedia")) or "F",
        "category": detect_column_optional(header, ["event category", "category"], yaml_cols.get("category")) or "G",
        "year_display_1": detect_column_optional(
            header, ["year or year range"], yaml_cols.get("year_display_1")
        )
        or "H",
        "year_display_2": yaml_cols.get("year_display_2") or "I",
        "year_display_3": yaml_cols.get("year_display_3") or "J",
    }


def build_sheet_row(parsed: dict[str, Any], header_len: int, col_map: dict[str, str]) -> list[Any]:
    row = [""] * header_len
    values = {
        col_map["progr"]: parsed.get("progr", ""),
        col_map["name"]: parsed["name"],
        col_map["sorting_year"]: parsed["sorting_year"],
        col_map["numerical_year"]: parsed["numerical_year"],
        col_map["notes"]: parsed["notes"],
        col_map["wikipedia"]: parsed["wikipedia"],
        col_map["category"]: parsed["category"],
        col_map["year_display_1"]: parsed["year_display_1"],
        col_map["year_display_2"]: parsed["year_display_2"],
        col_map["year_display_3"]: parsed["year_display_3"],
    }
    for col, value in values.items():
        row[col_letter_to_index(col)] = value
    return row


def batch_duplicate_reason(
    name: str, sorting_year: int, batch: list[dict[str, Any]]
) -> str | None:
    candidate = enrich_existing_event_row(
        name,
        {"name": name, "sorting_year": str(sorting_year), "progr": 0, "row_idx": 0},
    )
    for prior in batch:
        ok, reason = should_merge_events(candidate, prior)
        if ok:
            return reason
    return None


def plan_event_additions(
    specs: list[dict[str, Any]],
    existing: list[dict[str, Any]],
    max_progr: int,
    tiers: set[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    planned: list[dict[str, Any]] = []
    warnings: list[str] = []
    next_progr = max_progr + 1
    batch_candidates: list[dict[str, Any]] = []

    for spec in specs:
        if not tier_ok(spec, tiers):
            continue
        try:
            parsed = parse_event_spec(spec)
        except ValueError as exc:
            warnings.append(str(exc))
            continue

        candidate = candidate_from_parsed(parsed)
        matched = match_existing_event(parsed["name"], parsed["start_year"], existing)
        if matched:
            _, reason = should_merge_events(candidate, matched)
            warnings.append(
                f"SKIP duplicate ({reason}): {parsed['name']!r} "
                f"(existing: {matched['name']!r}, progr {matched['progr']})"
            )
            continue

        batch_reason = batch_duplicate_reason(parsed["name"], parsed["start_year"], batch_candidates)
        if batch_reason:
            warnings.append(
                f"SKIP duplicate in batch ({batch_reason}): {parsed['name']!r}"
            )
            continue

        for similar in event_similarity_warnings(
            parsed["name"], existing, new_sorting_year=parsed["start_year"]
        ):
            warnings.append(f"WARN {parsed['name']!r}: {similar}")

        parsed["progr"] = next_progr
        planned.append(parsed)
        batch_candidates.append(candidate)
        next_progr += 1

    return planned, warnings


def print_plan(planned: list[dict[str, Any]], warnings: list[str]) -> None:
    print(f"Events to append: {len(planned)}")
    for item in planned:
        year = item["start_year"] if item["start_year"] == item["end_year"] else f"{item['start_year']}-{item['end_year']}"
        extra = f" — {item['note']}" if item.get("note") else ""
        print(f"  progr {item['progr']}: {year}  {item['name']}{extra}")
    if warnings:
        print("\nWarnings:")
        for warning in warnings:
            print(f"  ! {warning}")


def list_events(existing: list[dict[str, Any]], query: str | None) -> None:
    rows = existing
    if query:
        q = query.lower()
        rows = [
            item
            for item in existing
            if q in item["name"].lower()
            or q in str(item["numerical_year"]).lower()
            or q in str(item["sorting_year"]).lower()
        ]
    print(f"Matching events: {len(rows)}")
    for item in sorted(rows, key=lambda x: (str(x["sorting_year"]), x["progr"])):
        print(f"  {item['progr']:>4}  {item['sorting_year']:>12}  {item['name']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--file",
        type=Path,
        help="YAML file with events to add (default: required unless --list or --discover)",
    )
    parser.add_argument("--discover", action="store_true", help="List tabs and headers, then exit")
    parser.add_argument("--list", action="store_true", help="List existing Events rows")
    parser.add_argument("--query", help="Filter for --list (case-insensitive substring)")
    parser.add_argument("--dry-run", action="store_true", help="Show planned additions (default)")
    parser.add_argument("--apply", action="store_true", help="Append rows to Events tab")
    parser.add_argument(
        "--update-notes",
        action="store_true",
        help="Update Notes column for existing events matched by name",
    )
    parser.add_argument(
        "--tier",
        action="append",
        help="Apply only events with this tier value (repeatable)",
    )
    parser.add_argument("--json", action="store_true", help="With --list, emit JSON")
    args = parser.parse_args()

    if args.apply and args.dry_run:
        raise SystemExit("Use either --apply or --dry-run, not both")
    if args.update_notes and args.list:
        raise SystemExit("Use --update-notes with --file, not --list")
    dry_run = not args.apply

    config = load_yaml(args.config) if args.config.is_file() else {}

    event_data: dict[str, Any] = {}
    specs: list[dict[str, Any]] = []
    if args.file:
        event_data, specs = load_events_file(args.file)

    spreadsheet_id = resolve_spreadsheet_id(config, event_data)
    if not spreadsheet_id:
        raise SystemExit(
            "spreadsheet_id missing. Set it in config.yaml or the events YAML file."
        )

    service = build_sheets_service(config)

    if args.discover:
        discover_sheets(service, spreadsheet_id)
        return

    sheet_cfg = {**(event_data.get("sheets") or {}), **(config.get("sheets") or {})}
    events_name = detect_events_sheet(service, spreadsheet_id, sheet_cfg.get("events"))

    rows = get_sheet_values(service, spreadsheet_id, events_name, "A:J")
    if not rows:
        raise SystemExit(f"Sheet {events_name!r} is empty")

    header = rows[0]
    col_map = detect_events_columns(header, event_data.get("events_columns") or {})
    existing, max_progr = read_existing_events(service, spreadsheet_id, events_name, col_map)

    if args.list:
        if args.json:
            q = args.query.lower() if args.query else None
            filtered = existing
            if q:
                filtered = [
                    item
                    for item in existing
                    if q in item["name"].lower()
                    or q in str(item["numerical_year"]).lower()
                    or q in str(item["sorting_year"]).lower()
                ]
            print(json.dumps(filtered, indent=2))
        else:
            list_events(existing, args.query)
        return

    if not args.file:
        raise SystemExit("Provide --file, or use --list / --discover")

    tiers = {t.upper() for t in args.tier} if args.tier else set()

    if args.update_notes:
        updates, warnings = plan_event_note_updates(specs, existing, tiers)
        print(f"Events sheet: {events_name!r}")
        print(f"mode: {'DRY RUN' if dry_run else 'APPLY'} (update notes)")
        if tiers:
            print(f"tiers: {', '.join(sorted(tiers))}")
        print()
        print_note_updates(updates, warnings)
        if dry_run:
            print("\nDry run complete. Re-run with --apply --update-notes to write changes.")
            return
        if not updates:
            print("Nothing to apply.")
            return
        quoted = events_name.replace("'", "''")
        data = [
            {
                "range": f"'{quoted}'!{col_map['notes']}{item['row_idx']}",
                "values": [[item["notes"]]],
            }
            for item in updates
        ]
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"valueInputOption": "USER_ENTERED", "data": data},
        ).execute()
        print(f"\nUpdated {len(data)} note(s).")
        print("Done. Rebuild Alfred DB: ::whoWasWhen-refresh")
        return

    planned, warnings = plan_event_additions(specs, existing, max_progr, tiers)

    print(f"Events sheet: {events_name!r}")
    print(f"Current max Progr: {max_progr}")
    print(f"mode: {'DRY RUN' if dry_run else 'APPLY'}")
    if tiers:
        print(f"tiers: {', '.join(sorted(tiers))}")
    print()
    print_plan(planned, warnings)

    if dry_run:
        print("\nDry run complete. Re-run with --apply to append rows.")
        return

    if not planned:
        print("Nothing to apply.")
        return

    append_rows = [build_sheet_row(item, len(header), col_map) for item in planned]
    quoted = events_name.replace("'", "''")
    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=f"'{quoted}'!A:J",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": append_rows},
    ).execute()
    print(f"\nAppended {len(append_rows)} event row(s).")
    print("Done. Rebuild Alfred DB: ::whoWasWhen-refresh")


if __name__ == "__main__":
    main()
