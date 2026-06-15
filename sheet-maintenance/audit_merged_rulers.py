#!/usr/bin/env python3
"""Audit WhoWasWhen Periods sheet for merged-ruler bugs (same rulerID, incompatible reigns)."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from sheets_common import (
    DEFAULT_CONFIG,
    DEFAULT_PATCHES,
    build_sheets_service,
    detect_by_period_sheet,
    detect_column,
    detect_column_optional,
    get_sheet_values,
    is_minor_title,
    load_spreadsheet_config,
    parse_period_start,
)


LEGITIMATE_MULTI = {
    ("Franz II", {"Holy Roman Emperor", "Emperor of Austria"}),
    ("Louis II", {"King of the Franks", "Holy Roman Emperor"}),
    ("Charles VIII", {"King of France", "Neapolitan ruler"}),
    ("Louis XII", {"King of France", "Neapolitan ruler"}),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--patches", type=Path, default=DEFAULT_PATCHES)
    parser.add_argument("--min-span", type=int, default=100, help="Min year span to flag (default 100)")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of text")
    args = parser.parse_args()

    config, patches, spreadsheet_id = load_spreadsheet_config(args.config, args.patches)
    service = build_sheets_service(config)
    sheet_cfg = {**(patches.get("sheets") or {}), **(config.get("sheets") or {})}
    periods_name = detect_by_period_sheet(service, spreadsheet_id, sheet_cfg.get("by_period"))
    rows = get_sheet_values(service, spreadsheet_id, periods_name, "A:Z")
    header = rows[0]

    progr_col = detect_column(header, ["Progr"], "A")
    title_col = detect_column(header, ["Title"], "B")
    name_col = detect_column(header, ["Name"], "D")
    ruler_col = detect_column(header, ["RulerID"], "E")
    cc_col = detect_column_optional(header, ["CountCheck"], "H")
    period_col = detect_column(header, ["Period"], "K")

    pi = ord(progr_col) - ord("A")
    ti = ord(title_col) - ord("A")
    ni = ord(name_col) - ord("A")
    ri = ord(ruler_col) - ord("A")
    ci = ord(cc_col) - ord("A") if cc_col else None
    peri = ord(period_col) - ord("A")

    by_ruler: dict[int, list[dict]] = defaultdict(list)
    for row in rows[1:]:
        if len(row) <= pi:
            continue
        try:
            progr = int(float(str(row[pi]).strip()))
            rid = int(float(str(row[ri]).strip()))
        except (ValueError, IndexError):
            continue
        title = row[ti] if len(row) > ti else ""
        name = row[ni] if len(row) > ni else ""
        period = row[peri] if len(row) > peri else ""
        cc = row[ci] if ci is not None and len(row) > ci else ""
        by_ruler[rid].append(
            {"progr": progr, "title": title, "name": name, "period": period, "count_check": cc}
        )

    applied_progrs = {int(m["progr"]) for m in patches.get("ruler_id_moves", [])}
    findings = []

    for rid, recs in sorted(by_ruler.items()):
        if len(recs) < 2:
            continue
        major = [r for r in recs if not is_minor_title(r["title"])]
        if len(major) < 2:
            continue
        starts = [parse_period_start(r["period"]) for r in recs]
        starts = [s for s in starts if s is not None]
        span = max(starts) - min(starts) if len(starts) >= 2 else 0
        if span < args.min_span:
            continue
        name = recs[0]["name"]
        titles = {r["title"] for r in major}
        if any(name == n and titles <= t for n, t in LEGITIMATE_MULTI):
            continue
        open_progrs = [r["progr"] for r in recs if r["progr"] not in applied_progrs]
        findings.append(
            {
                "ruler_id": rid,
                "name": name,
                "year_span": span,
                "count_check": list({r["count_check"] for r in recs}),
                "periods": recs,
                "unpatched_progrs": open_progrs,
            }
        )

    findings.sort(key=lambda x: -x["year_span"])

    if args.json:
        print(json.dumps(findings, indent=2))
        return

    print(f"Spreadsheet: {spreadsheet_id}")
    print(f"Sheet: {periods_name!r}")
    print(f"Flagged rulerIDs (multi major title, span >= {args.min_span}y): {len(findings)}\n")
    for f in findings:
        print(f"rulerID {f['ruler_id']} | {f['name']} | span {f['year_span']}y | CountCheck {f['count_check']}")
        for r in sorted(f["periods"], key=lambda x: parse_period_start(x["period"]) or 0):
            mark = " [in patches]" if r["progr"] in applied_progrs else ""
            print(f"  progr {r['progr']:4d} | {r['title'][:28]:28s} | {r['period']}{mark}")
        if f["unpatched_progrs"]:
            print(f"  → unpatched progr: {f['unpatched_progrs']}")
        print()


if __name__ == "__main__":
    main()
