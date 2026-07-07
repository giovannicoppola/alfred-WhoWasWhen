#!/usr/bin/env python3
"""Populate Month/Day columns on the Events tab from Wikidata.

For each Events row that has a Wikipedia URL and no Month/Day yet, resolve
the article's Wikidata item (via the wiki's pageprops API), read its
P585 "point in time" (or P580 "start time") claim, sanity-check the year
against the sheet's Sorting year, and plan Month/Day cell updates.
Dates embedded in event names — "Battle of Rocroi (May 19)" — are a second
source; the two must agree or the row is flagged for manual review.

Usage:
  python add_event_dates.py --dry-run [--limit N] [--report dates.tsv]
  python add_event_dates.py --apply

The Month/Day columns are created (appended after the last header) on first
--apply if they don't exist. Rows already holding a Month value are skipped,
so re-runs are safe.
"""

from __future__ import annotations

import argparse
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import requests

from sheets_common import (
    DEFAULT_CONFIG,
    build_sheets_service,
    col_index_to_letter,
    get_sheet_values,
    load_spreadsheet_config,
    normalize_header,
)

EVENTS_SHEET = "Events"
USER_AGENT = "WhoWasWhen-sheet-maintenance/1.0 (giovannicoppola@gmail.com)"
MONTHS = ["january", "february", "march", "april", "may", "june", "july",
          "august", "september", "october", "november", "december"]

# "(May 19)", "(May 19, 1643)", "(19 May)" — anchored inside parentheses.
NAME_DATE_RE = re.compile(
    r"\((?:"
    r"(?P<m1>" + "|".join(MONTHS) + r")\s+(?P<d1>\d{1,2})"
    r"|(?P<d2>\d{1,2})\s+(?P<m2>" + "|".join(MONTHS) + r")"
    r")(?:,?\s*-?\d{1,4}(?:\s*(?:BC|BCE|CE|AD))?)?\)",
    re.IGNORECASE,
)


def http_get(url: str, params: dict[str, Any]) -> dict[str, Any]:
    for attempt in range(5):
        resp = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=30)
        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", 2 ** (attempt + 1)))
            time.sleep(min(wait, 60))
            continue
        resp.raise_for_status()
        return resp.json()
    resp.raise_for_status()
    return {}


def chunked(seq: list, size: int):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


# ---------------------------------------------------------------- sheet I/O

def read_events(service, spreadsheet_id: str) -> tuple[list[str], list[dict[str, Any]], dict[str, int | None]]:
    rows = get_sheet_values(service, spreadsheet_id, EVENTS_SHEET, "A1:Z3000")
    if not rows:
        raise SystemExit("Events sheet is empty?")
    header = rows[0]
    idx = {normalize_header(h): i for i, h in enumerate(header)}

    def find(*names: str) -> int | None:
        for n in names:
            if n in idx:
                return idx[n]
        # "Progr (max:1003)"-style decorated headers
        for norm, i in idx.items():
            if any(norm.startswith(n) for n in names):
                return i
        return None

    cols = {
        "progr": find("progr"),
        "name": find("event name"),
        "sorting_year": find("sorting year"),
        "wikipedia": find("wikipedia"),
        "month": find("month"),
        "day": find("day"),
    }
    for key in ("progr", "name", "sorting_year", "wikipedia"):
        if cols[key] is None:
            raise SystemExit(f"Column {key!r} not found in Events header: {header}")

    def cell(row: list, i: int | None) -> str:
        return str(row[i]).strip() if i is not None and len(row) > i else ""

    events = []
    for row_idx, row in enumerate(rows[1:], start=2):  # sheet row numbers
        name = cell(row, cols["name"])
        if not name:
            continue
        events.append({
            "row": row_idx,
            "progr": cell(row, cols["progr"]),
            "name": name,
            "sorting_year": cell(row, cols["sorting_year"]),
            "wikipedia": cell(row, cols["wikipedia"]),
            "month": cell(row, cols["month"]),
            "day": cell(row, cols["day"]),
        })
    return header, events, cols


# ------------------------------------------------------------- date sources

def parse_wiki_url(url: str) -> tuple[str, str] | None:
    """→ (host, article title) for *.wikipedia.org URLs."""
    m = re.match(r"https?://([a-z-]+\.(?:m\.)?wikipedia\.org)/wiki/(.+)$", url.strip())
    if not m:
        return None
    host = m.group(1).replace(".m.", ".")
    title = unquote(m.group(2)).replace("_", " ").split("#")[0]
    return host, title


def resolve_qids(items: list[dict[str, Any]]) -> dict[int, str]:
    """row → QID via each wiki's pageprops API (batched, redirect-aware)."""
    by_host: dict[str, list[dict[str, Any]]] = {}
    for it in items:
        parsed = parse_wiki_url(it["wikipedia"])
        if not parsed:
            continue
        host, title = parsed
        it["_title"] = title
        by_host.setdefault(host, []).append(it)

    qids: dict[int, str] = {}
    for host, host_items in by_host.items():
        for batch in chunked(host_items, 50):
            data = http_get(f"https://{host}/w/api.php", {
                "action": "query", "format": "json", "redirects": 1,
                "prop": "pageprops", "ppprop": "wikibase_item",
                "titles": "|".join(it["_title"] for it in batch),
            })
            query = data.get("query", {})
            # map final (post-redirect/normalization) title back to requested
            back: dict[str, str] = {}
            for r in query.get("normalized", []) + query.get("redirects", []):
                back[r["to"]] = back.get(r["from"], r["from"])
            by_title = {it["_title"]: it for it in batch}
            for page in query.get("pages", {}).values():
                title = page.get("title", "")
                requested = back.get(title, title)
                it = by_title.get(requested)
                qid = page.get("pageprops", {}).get("wikibase_item")
                if it is not None and qid:
                    qids[it["row"]] = qid
            time.sleep(0.1)
    return qids


def fetch_dates(qids: dict[int, str]) -> dict[str, dict[str, Any]]:
    """QID → {year, month, day, precision, prop} from P585 else P580."""
    out: dict[str, dict[str, Any]] = {}
    unique = sorted(set(qids.values()))
    for batch in chunked(unique, 50):
        data = http_get("https://www.wikidata.org/w/api.php", {
            "action": "wbgetentities", "format": "json",
            "ids": "|".join(batch), "props": "claims",
        })
        for qid, entity in data.get("entities", {}).items():
            claims = entity.get("claims", {})
            for prop in ("P585", "P580"):
                best = pick_time_claim(claims.get(prop, []))
                if best:
                    best["prop"] = prop
                    out[qid] = best
                    break
        time.sleep(0.1)
    return out


def pick_time_claim(statements: list[dict]) -> dict[str, Any] | None:
    def rank_key(s):  # preferred > normal; skip deprecated
        return {"preferred": 0, "normal": 1}.get(s.get("rank"), 9)

    for s in sorted(statements, key=rank_key):
        if s.get("rank") == "deprecated":
            continue
        value = s.get("mainsnak", {}).get("datavalue", {}).get("value", {})
        t, precision = value.get("time"), value.get("precision", 0)
        if not t or precision < 9:
            continue
        m = re.match(r"([+-]\d+)-(\d{2})-(\d{2})T", t)
        if not m:
            continue
        return {
            "year": int(m.group(1)),
            "month": int(m.group(2)) if precision >= 10 else None,
            "day": int(m.group(3)) if precision >= 11 else None,
            "precision": precision,
        }
    return None


def resolve_qids_no_url(items: list[dict[str, Any]]) -> dict[int, tuple[str, str]]:
    """row → (QID, matched title) for rows with no Wikipedia URL: exact
    en.wikipedia title match first, then a search-API fallback. The year
    sanity check downstream weeds out wrong matches."""
    api = "https://en.wikipedia.org/w/api.php"
    for it in items:
        core = re.sub(r"\s*\([^)]*\)", "", it["name"]).strip()
        it["_title"] = core

    out: dict[int, tuple[str, str]] = {}
    for batch in chunked(items, 50):
        data = http_get(api, {
            "action": "query", "format": "json", "redirects": 1,
            "prop": "pageprops", "ppprop": "wikibase_item",
            "titles": "|".join(it["_title"] for it in batch),
        })
        query = data.get("query", {})
        back: dict[str, str] = {}
        for r in query.get("normalized", []) + query.get("redirects", []):
            back[r["to"]] = back.get(r["from"], r["from"])
        by_title = {it["_title"]: it for it in batch}
        for page in query.get("pages", {}).values():
            title = page.get("title", "")
            it = by_title.get(back.get(title, title))
            qid = page.get("pageprops", {}).get("wikibase_item")
            if it is not None and qid:
                out[it["row"]] = (qid, title)
        time.sleep(0.1)

    remaining = [it for it in items if it["row"] not in out]
    print(f"  title-matched {len(out)}; searching for {len(remaining)} more…")
    for it in remaining:
        # generator=search returns the top hit's pageprops in one request.
        data = http_get(api, {
            "action": "query", "format": "json",
            "generator": "search", "gsrsearch": it["_title"], "gsrlimit": 1,
            "prop": "pageprops", "ppprop": "wikibase_item",
        })
        for page in data.get("query", {}).get("pages", {}).values():
            qid = page.get("pageprops", {}).get("wikibase_item")
            if qid:
                out[it["row"]] = (qid, f"search:{page.get('title', '')}")
        time.sleep(0.4)
    return out


def date_from_name(name: str) -> tuple[int, int] | None:
    m = NAME_DATE_RE.search(name)
    if not m:
        return None
    month_name = (m.group("m1") or m.group("m2")).lower()
    day = int(m.group("d1") or m.group("d2"))
    month = MONTHS.index(month_name) + 1
    return (month, day) if 1 <= day <= 31 else None


def sheet_year(value: str) -> int | None:
    try:
        return int(str(value).strip())
    except ValueError:
        return None


# ------------------------------------------------------------------- plan

def build_plan(events, qids, dates, matched=None) -> list[dict[str, Any]]:
    matched = matched or {}
    plan = []
    for e in events:
        entry = {**e, "new_month": None, "new_day": None, "source": "", "status": ""}
        named = date_from_name(e["name"])

        if e["month"]:
            entry["status"] = "SKIP already has month"
            plan.append(entry)
            continue

        wd = dates.get(qids.get(e["row"], ""), None)
        wd_ok = None
        if wd:
            y = sheet_year(e["sorting_year"])
            # ±1 also absorbs the BCE numbering-convention ambiguity.
            if y is not None and abs(wd["year"] - y) <= 1:
                wd_ok = wd
            else:
                entry["status"] = f"MISMATCH wikidata year {wd['year']} vs sheet {e['sorting_year']}"

        if wd_ok and named and wd_ok["day"] and (wd_ok["month"], wd_ok["day"]) != named:
            # The curator's parenthetical date marks the event itself (fall,
            # effective date) where Wikidata often has the start of a siege
            # or campaign — the name wins, but stays visible in the report.
            entry.update(new_month=named[0], new_day=named[1], source="name",
                         status=f"OK name over wikidata {wd_ok['month']}/{wd_ok['day']}")
        elif wd_ok and wd_ok["month"]:
            src = f"wikidata {wd_ok['prop']}"
            if e["row"] in matched:
                src += f" [{matched[e['row']]}]"
            entry.update(new_month=wd_ok["month"], new_day=wd_ok["day"], source=src,
                         status="OK" if wd_ok["day"] else "OK month only")
        elif named:
            entry.update(new_month=named[0], new_day=named[1], source="name",
                         status="OK from name")
        elif not entry["status"]:
            if e["row"] not in qids:
                entry["status"] = "NO-URL" if not e["wikipedia"] else "NO-QID"
            else:
                entry["status"] = "NO-DATE on wikidata"
        plan.append(entry)
    return plan


def write_report(plan: list[dict[str, Any]], path: Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        f.write("progr\trow\tname\tsorting_year\tmonth\tday\tsource\tstatus\n")
        for e in plan:
            f.write(f"{e['progr']}\t{e['row']}\t{e['name']}\t{e['sorting_year']}\t"
                    f"{e['new_month'] or ''}\t{e['new_day'] or ''}\t{e['source']}\t{e['status']}\n")


# ------------------------------------------------------------------ apply

def ensure_columns(service, spreadsheet_id: str, header: list[str], cols) -> None:
    """Append Month/Day headers after the last used header column if missing."""
    updates = []
    next_i = len(header)
    if cols["month"] is None:
        cols["month"] = next_i
        updates.append(("Month", next_i))
        next_i += 1
    if cols["day"] is None:
        cols["day"] = next_i
        updates.append(("Day", next_i))
        next_i += 1
    if not updates:
        return
    data = [{
        "range": f"'{EVENTS_SHEET}'!{col_index_to_letter(i)}1",
        "values": [[label]],
    } for label, i in updates]
    service.spreadsheets().values().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"valueInputOption": "RAW", "data": data},
    ).execute()
    print(f"Added header column(s): {', '.join(l for l, _ in updates)}")


def apply_plan(service, spreadsheet_id: str, plan, cols) -> int:
    month_col = col_index_to_letter(cols["month"])
    day_col = col_index_to_letter(cols["day"])
    data = []
    for e in plan:
        if e["new_month"] is None:
            continue
        data.append({
            "range": f"'{EVENTS_SHEET}'!{month_col}{e['row']}",
            "values": [[e["new_month"]]],
        })
        if e["new_day"] is not None:
            data.append({
                "range": f"'{EVENTS_SHEET}'!{day_col}{e['row']}",
                "values": [[e["new_day"]]],
            })
    n = 0
    for batch in chunked(data, 500):
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"valueInputOption": "RAW", "data": batch},
        ).execute()
        n += len(batch)
    return n


# ------------------------------------------------------------------- main

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--dry-run", action="store_true", help="Plan only (default)")
    parser.add_argument("--apply", action="store_true", help="Write Month/Day cells")
    parser.add_argument("--limit", type=int, help="Only process the first N events (testing)")
    parser.add_argument("--report", type=Path, default=Path("event-dates-report.tsv"),
                        help="TSV report path (default: event-dates-report.tsv)")
    args = parser.parse_args()

    config, _, spreadsheet_id = load_spreadsheet_config(args.config)
    service = build_sheets_service(config)
    header, events, cols = read_events(service, spreadsheet_id)
    if args.limit:
        events = events[:args.limit]

    todo = [e for e in events if not e["month"] and e["wikipedia"]]
    print(f"{len(events)} events; {len(todo)} to look up on Wikidata…")
    qids = resolve_qids(todo)
    print(f"  resolved {len(qids)} Wikidata items from URLs")
    no_url = [e for e in events
              if not e["month"] and not e["wikipedia"] and not date_from_name(e["name"])]
    found = resolve_qids_no_url(no_url)
    qids.update({row: qid for row, (qid, _) in found.items()})
    matched = {row: label for row, (_, label) in found.items()}
    dates = fetch_dates(qids)
    print(f"  found dates for {len(dates)} items")

    plan = build_plan(events, qids, dates, matched)
    write_report(plan, args.report)

    counts: dict[str, int] = {}
    for e in plan:
        key = e["status"].split()[0]
        counts[key] = counts.get(key, 0) + 1
    print(f"\nPlan summary ({args.report}):")
    for key in sorted(counts):
        print(f"  {key:10} {counts[key]}")
    dated = sum(1 for e in plan if e["new_month"] is not None)
    print(f"  → {dated} rows would get a Month (of {len(plan)})")

    if args.apply:
        ensure_columns(service, spreadsheet_id, header, cols)
        n = apply_plan(service, spreadsheet_id, plan, cols)
        print(f"Applied {n} cell updates.")
    else:
        print("\nDry run only — review the report, then re-run with --apply.")


if __name__ == "__main__":
    main()
