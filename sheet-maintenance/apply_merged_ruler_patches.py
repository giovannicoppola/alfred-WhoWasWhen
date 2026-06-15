#!/usr/bin/env python3
"""Apply merged-ruler fixes to the WhoWasWhen Google Sheet via Sheets API."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from sheets_common import (
    DEFAULT_CONFIG,
    DEFAULT_PATCHES,
    build_sheets_service,
    build_progr_row_map,
    col_letter_to_index,
    detect_by_period_sheet,
    detect_column,
    detect_column_optional,
    detect_rulers_sheet,
    discover_sheets,
    get_sheet_values,
    load_spreadsheet_config,
    load_yaml,
)


def build_ruler_row_map(rows: list[list[Any]], ruler_col: str) -> dict[int, int]:
    ri = col_letter_to_index(ruler_col)
    mapping: dict[int, int] = {}
    for row_idx, row in enumerate(rows, start=1):
        if row_idx == 1 or len(row) <= ri:
            continue
        raw = row[ri]
        if raw in (None, ""):
            continue
        try:
            rid = int(float(str(raw).strip()))
        except ValueError:
            continue
        mapping[rid] = row_idx
    return mapping


def tier_ok(item: dict[str, Any], tiers: set[str]) -> bool:
    return not tiers or str(item.get("tier", "")).upper() in tiers


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--patches", type=Path, default=DEFAULT_PATCHES)
    parser.add_argument("--discover", action="store_true", help="List tabs and headers, then exit")
    parser.add_argument("--dry-run", action="store_true", help="Show planned changes (default)")
    parser.add_argument("--apply", action="store_true", help="Write changes to the sheet")
    parser.add_argument(
        "--tier",
        action="append",
        help="Apply only this tier letter (repeatable). Default: all tiers in patches file",
    )
    parser.add_argument("--skip-rulers", action="store_true", help="Only patch Periods RulerID column")
    args = parser.parse_args()

    if args.apply and args.dry_run:
        raise SystemExit("Use either --apply or --dry-run, not both")
    dry_run = not args.apply

    config, patches, spreadsheet_id = load_spreadsheet_config(args.config, args.patches)
    tiers = {t.upper() for t in args.tier} if args.tier else set()

    service = build_sheets_service(config)

    if args.discover:
        discover_sheets(service, spreadsheet_id)
        return

    sheet_cfg = {**(patches.get("sheets") or {}), **(config.get("sheets") or {})}
    by_period_name = detect_by_period_sheet(service, spreadsheet_id, sheet_cfg.get("by_period"))
    rulers_name = None if args.skip_rulers else detect_rulers_sheet(service, spreadsheet_id, sheet_cfg.get("rulers"))

    print(f"Periods sheet: {by_period_name!r}")
    print(f"Rulers sheet:  {rulers_name!r}" if rulers_name else "Rulers sheet:  (skipped)")
    print(f"mode: {'DRY RUN' if dry_run else 'APPLY'}")
    if tiers:
        print(f"tiers: {', '.join(sorted(tiers))}")
    print()

    by_rows = get_sheet_values(service, spreadsheet_id, by_period_name, "A:Z")
    if not by_rows:
        raise SystemExit(f"Sheet {by_period_name!r} is empty")

    header = by_rows[0]
    bp_cols = patches.get("by_period_columns") or {}
    progr_col = detect_column(header, ["Progr", "progr"], bp_cols.get("progr"))
    ruler_col = detect_column(header, ["RulerID", "rulerID", "rulerid"], bp_cols.get("ruler_id"))

    progr_map = build_progr_row_map(by_rows, progr_col, ruler_col)
    value_updates: list[dict[str, Any]] = []
    warnings: list[str] = []

    for move in [m for m in patches.get("ruler_id_moves", []) if tier_ok(m, tiers)]:
        progr = int(move["progr"])
        to_id = int(move["to_ruler_id"])
        from_id = move.get("from_ruler_id")
        if progr not in progr_map:
            warnings.append(f"progr {progr} not found — skipped ({move.get('note', '')})")
            continue
        row_idx, current = progr_map[progr]
        if from_id is not None and str(current).strip() not in ("", str(from_id), str(int(from_id))):
            warnings.append(
                f"progr {progr} row {row_idx}: expected RulerID {from_id}, found {current!r} — updating to {to_id}"
            )
        cell = f"'{by_period_name.replace(chr(39), chr(39) * 2)}'!{ruler_col}{row_idx}"
        value_updates.append(
            {
                "range": cell,
                "values": [[to_id]],
                "meta": f"progr {progr}: {current} → {to_id} ({move.get('note', '')})",
            }
        )

    append_rows: list[list[Any]] = []
    rulers_updates: list[dict[str, Any]] = []

    if rulers_name:
        ruler_rows = get_sheet_values(service, spreadsheet_id, rulers_name, "A:Z")
        if not ruler_rows:
            warnings.append(f"Rulers sheet empty — skipping")
            rulers_name = None
        else:
            r_header = ruler_rows[0]
            r_cols = patches.get("rulers_columns") or {}
            rid_col = detect_column(r_header, ["rulerID", "RulerID", "rulerid"], r_cols.get("ruler_id"))
            name_col = detect_column(r_header, ["name", "Name"], r_cols.get("name"))
            personal_col = detect_column_optional(
                r_header,
                ["personal_name", "personal name", "Personal Name", "Personal Name or House"],
                r_cols.get("personal_name"),
            )
            wiki_col = detect_column_optional(r_header, ["wikipedia", "Wikipedia"], r_cols.get("wikipedia"))
            epithet_col = detect_column_optional(r_header, ["epithet", "Epithet"], r_cols.get("epithet"))
            birth_death_col = detect_column_optional(
                r_header,
                ["birthdeath", "BirthDeath", "birth_death", "Birth Death"],
                r_cols.get("birth_death"),
            )
            bio_col = detect_column_optional(r_header, ["biography", "Biography"], None)
            ruler_row_map = build_ruler_row_map(ruler_rows, rid_col)

            for spec in [n for n in patches.get("new_rulers", []) if tier_ok(n, tiers)]:
                rid = int(spec["ruler_id"])
                if rid in ruler_row_map:
                    warnings.append(f"new_rulers: rulerID {rid} already exists — skipped insert")
                    continue
                row = [""] * len(r_header)
                row[col_letter_to_index(rid_col)] = rid
                row[col_letter_to_index(name_col)] = spec.get("name", "")
                if personal_col and spec.get("personal_name"):
                    row[col_letter_to_index(personal_col)] = spec["personal_name"]
                if wiki_col and spec.get("wikipedia"):
                    row[col_letter_to_index(wiki_col)] = spec["wikipedia"]
                if bio_col and spec.get("biography"):
                    row[col_letter_to_index(bio_col)] = spec["biography"]
                append_rows.append(row)
                print(f"NEW ruler row: {rid} {spec.get('name', '')}")

            for upd in [u for u in patches.get("ruler_updates", []) if tier_ok(u, tiers)]:
                rid = int(upd["ruler_id"])
                if rid not in ruler_row_map:
                    warnings.append(f"ruler_updates: rulerID {rid} not on Rulers sheet — skipped")
                    continue
                row_idx = ruler_row_map[rid]
                for field, col in [
                    ("biography", bio_col),
                    ("wikipedia", wiki_col),
                    ("epithet", epithet_col),
                    ("birth_death", birth_death_col),
                    ("personal_name", personal_col),
                    ("name", name_col),
                ]:
                    if not col or field not in upd:
                        continue
                    cell = f"'{rulers_name.replace(chr(39), chr(39) * 2)}'!{col}{row_idx}"
                    rulers_updates.append(
                        {"range": cell, "values": [[upd[field]]], "meta": f"rulerID {rid} {field}"}
                    )

    print(f"Periods RulerID updates: {len(value_updates)}")
    for item in value_updates:
        print(f"  {item['meta']}")
    if rulers_name:
        print(f"Rulers cell updates: {len(rulers_updates)}")
        for item in rulers_updates:
            print(f"  {item['meta']}")
        print(f"Rulers rows to append: {len(append_rows)}")
    if warnings:
        print("\nWarnings:")
        for w in warnings:
            print(f"  ! {w}")

    if dry_run:
        print("\nDry run complete. Re-run with --apply to write changes.")
        return

    if not value_updates and not rulers_updates and not append_rows:
        print("Nothing to apply.")
        return

    if append_rows and rulers_name:
        quoted = rulers_name.replace("'", "''")
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"'{quoted}'!A:Z",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": append_rows},
        ).execute()
        print(f"Appended {len(append_rows)} ruler row(s).")

    data = [{"range": i["range"], "values": i["values"]} for i in value_updates + rulers_updates]
    if data:
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"valueInputOption": "USER_ENTERED", "data": data},
        ).execute()
        print(f"Applied {len(data)} cell update(s).")

    print("\nDone. Rebuild Alfred DB: ::whoWasWhen-refresh")


if __name__ == "__main__":
    main()
