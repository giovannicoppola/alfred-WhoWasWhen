#!/usr/bin/env python3
"""Populate Born/Died year columns on the Rulers tab from Wikidata.

For each Rulers row without Born/Died yet, resolve the Wikidata item from
the row's Wikipedia URL (exact en.wikipedia title match as fallback for
rows without a URL — no fuzzy search, homonym consuls make that unsafe),
read P569 "date of birth" / P570 "date of death" (year precision or
better), and sanity-check against the ruler's reign span from the local
whoWasWhen.db: born must not postdate the first reign start, died must
not predate the last reign end, and the lifespan must stay ≤ 110 years.
The curator's existing BirthDeath column ("972-999", "???-1241") is a
second source: used alone when Wikidata has nothing, flagged when the
two disagree (Wikidata wins but stays visible in the report).

Usage:
  python add_birth_death.py --dry-run [--limit N] [--report birth-death.tsv]
  python add_birth_death.py --apply

Born/Died columns are appended to the header on first --apply. Rows that
already hold a Born value are skipped, so re-runs only fill new rulers.
"""

from __future__ import annotations

import argparse
import re
import sqlite3
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

RULERS_SHEET = "Rulers"
USER_AGENT = "WhoWasWhen-sheet-maintenance/1.0 (giovannicoppola@gmail.com)"
DEFAULT_DB = Path(
    "~/Library/Application Support/Alfred/Workflow Data/"
    "giovanni-whowaswhen/whoWasWhen.db"
).expanduser()
MAX_LIFESPAN = 110

# "972-999", "1160/61-1216", "???-1241", "c. 1150-1200", "-63-14" (BC birth)
BIRTHDEATH_RE = re.compile(
    r"^(?:c?a?\.?\s*)?(?P<b>\?+|-?\d{1,4})(?:/\d{1,4})?\s*[-–—]\s*"
    r"(?:c?a?\.?\s*)?(?P<d>\?+|-?\d{1,4})(?:/\d{1,4})?$"
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

def read_rulers(service, spreadsheet_id: str) -> tuple[list[str], list[dict[str, Any]], dict[str, int | None]]:
    rows = get_sheet_values(service, spreadsheet_id, RULERS_SHEET, "A1:Z4000")
    if not rows:
        raise SystemExit("Rulers sheet is empty?")
    header = rows[0]
    idx: dict[str, int] = {}
    for i, h in enumerate(header):
        idx.setdefault(normalize_header(h), i)  # keep first on duplicates

    def find(*names: str) -> int | None:
        for n in names:
            if n in idx:
                return idx[n]
        return None

    cols = {
        "ruler_id": find("rulerid"),
        "name": find("name"),
        "wikipedia": find("wikipedia"),
        "birthdeath": find("birthdeath"),
        "born": find("born"),
        "died": find("died"),
    }
    for key in ("ruler_id", "name", "wikipedia"):
        if cols[key] is None:
            raise SystemExit(f"Column {key!r} not found in Rulers header: {header}")

    def cell(row: list, i: int | None) -> str:
        return str(row[i]).strip() if i is not None and len(row) > i else ""

    rulers = []
    for row_idx, row in enumerate(rows[1:], start=2):  # sheet row numbers
        rid = cell(row, cols["ruler_id"])
        if not rid.isdigit():
            continue
        rulers.append({
            "row": row_idx,
            "ruler_id": int(rid),
            "name": cell(row, cols["name"]),
            "wikipedia": cell(row, cols["wikipedia"]),
            "birthdeath": cell(row, cols["birthdeath"]),
            "born": cell(row, cols["born"]),
            "died": cell(row, cols["died"]),
        })
    return header, rulers, cols


def read_reign_spans(db_path: Path) -> dict[int, tuple[int, int]]:
    """rulerID → (first reign startYear, last reign endYear) from the local DB."""
    if not db_path.is_file():
        print(f"WARNING: {db_path} not found — reign sanity checks disabled")
        return {}
    con = sqlite3.connect(db_path)
    try:
        cur = con.execute(
            "SELECT rulerID, MIN(startYear), MAX(endYear) FROM byPeriod "
            "WHERE startYear IS NOT NULL GROUP BY rulerID"
        )
        return {rid: (lo, hi) for rid, lo, hi in cur.fetchall() if lo is not None}
    finally:
        con.close()


# ------------------------------------------------------------- date sources

def parse_wiki_url(url: str) -> tuple[str, str] | None:
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
            back: dict[str, str] = {}
            for r in query.get("normalized", []) + query.get("redirects", []):
                back[r["to"]] = back.get(r["from"], r["from"])
            by_title = {it["_title"]: it for it in batch}
            for page in query.get("pages", {}).values():
                title = page.get("title", "")
                it = by_title.get(back.get(title, title))
                qid = page.get("pageprops", {}).get("wikibase_item")
                if it is not None and qid:
                    qids[it["row"]] = qid
            time.sleep(0.1)
    return qids


def resolve_qids_no_url(items: list[dict[str, Any]]) -> dict[int, str]:
    """Exact en.wikipedia title match only — no search fallback; too many
    Roman-consul homonyms share names for a top-search-hit to be safe."""
    api = "https://en.wikipedia.org/w/api.php"
    for it in items:
        it["_title"] = re.sub(r"\s*\([^)]*\)", "", it["name"]).strip()

    out: dict[int, str] = {}
    for batch in chunked([it for it in items if it["_title"]], 50):
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
                out[it["row"]] = qid
        time.sleep(0.1)
    return out


def fetch_years(qids: dict[int, str]) -> dict[str, dict[str, int]]:
    """QID → {"born": year, "died": year} (either may be missing)."""
    out: dict[str, dict[str, int]] = {}
    unique = sorted(set(qids.values()))
    for batch in chunked(unique, 50):
        data = http_get("https://www.wikidata.org/w/api.php", {
            "action": "wbgetentities", "format": "json",
            "ids": "|".join(batch), "props": "claims",
        })
        for qid, entity in data.get("entities", {}).items():
            claims = entity.get("claims", {})
            years: dict[str, int] = {}
            for key, prop in (("born", "P569"), ("died", "P570")):
                y = pick_year_claim(claims.get(prop, []))
                if y is not None:
                    years[key] = y
            if years:
                out[qid] = years
        time.sleep(0.1)
    return out


def pick_year_claim(statements: list[dict]) -> int | None:
    def rank_key(s):  # preferred > normal; skip deprecated
        return {"preferred": 0, "normal": 1}.get(s.get("rank"), 9)

    for s in sorted(statements, key=rank_key):
        if s.get("rank") == "deprecated":
            continue
        value = s.get("mainsnak", {}).get("datavalue", {}).get("value", {})
        t, precision = value.get("time"), value.get("precision", 0)
        if not t or precision < 9:  # need year precision or better
            continue
        m = re.match(r"([+-]\d+)-", t)
        if m:
            return int(m.group(1))
    return None


def parse_birthdeath(raw: str) -> tuple[int | None, int | None]:
    m = BIRTHDEATH_RE.match(raw.strip())
    if not m:
        return None, None
    born = int(m.group("b")) if not m.group("b").startswith("?") else None
    died = int(m.group("d")) if not m.group("d").startswith("?") else None
    return born, died


# ------------------------------------------------------------------- plan

def check_sanity(born: int | None, died: int | None,
                 span: tuple[int, int] | None) -> str | None:
    """Return a rejection reason, or None if the years are plausible."""
    if born is not None and died is not None:
        if died < born:
            return f"died {died} before born {born}"
        if died - born > MAX_LIFESPAN:
            return f"lifespan {died - born}y > {MAX_LIFESPAN}"
    if span:
        first_start, last_end = span
        # ±1 absorbs BCE numbering ambiguity and new-year-style drift.
        if born is not None and born > first_start + 1:
            return f"born {born} after reign start {first_start}"
        if died is not None and died < last_end - 1:
            return f"died {died} before reign end {last_end}"
        if born is not None and last_end - born > MAX_LIFESPAN + 1:
            return f"reign end {last_end} is {last_end - born}y after birth {born}"
    return None


def build_plan(rulers, qids, years, spans) -> list[dict[str, Any]]:
    plan = []
    for r in rulers:
        entry = {**r, "new_born": None, "new_died": None, "source": "", "status": ""}
        span = spans.get(r["ruler_id"])
        entry["reign"] = f"{span[0]}–{span[1]}" if span else ""

        if r["born"] or r["died"]:
            entry["status"] = "SKIP already has born/died"
            plan.append(entry)
            continue

        wd = years.get(qids.get(r["row"], ""), {})
        sheet_b, sheet_d = parse_birthdeath(r["birthdeath"]) if r["birthdeath"] else (None, None)

        born = wd.get("born", sheet_b)
        died = wd.get("died", sheet_d)
        if born is None and died is None:
            if r["row"] not in qids:
                entry["status"] = "NO-URL no title match" if not r["wikipedia"] else "NO-QID"
            else:
                entry["status"] = "NO-DATE on wikidata"
            plan.append(entry)
            continue

        reason = check_sanity(born, died, span)
        if reason:
            entry["status"] = f"MISMATCH {reason}"
            plan.append(entry)
            continue

        src = []
        if wd:
            src.append("wikidata")
        if (born is not None and born == sheet_b and "born" not in wd) or \
           (died is not None and died == sheet_d and "died" not in wd):
            src.append("sheet")
        entry["source"] = "+".join(src) or "sheet"

        conflict = (
            ("born" in wd and sheet_b is not None and abs(wd["born"] - sheet_b) > 1)
            or ("died" in wd and sheet_d is not None and abs(wd["died"] - sheet_d) > 1)
        )
        entry.update(new_born=born, new_died=died)
        if conflict:
            entry["status"] = f"OK wikidata over sheet {r['birthdeath']}"
        elif born is None:
            entry["status"] = "OK died only"
        elif died is None:
            entry["status"] = "OK born only"
        else:
            entry["status"] = "OK"
        plan.append(entry)
    return plan


def write_report(plan: list[dict[str, Any]], path: Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        f.write("rulerID\trow\tname\treign\tsheet_birthdeath\tborn\tdied\tsource\tstatus\n")
        for e in plan:
            f.write(f"{e['ruler_id']}\t{e['row']}\t{e['name']}\t{e['reign']}\t"
                    f"{e['birthdeath']}\t"
                    f"{'' if e['new_born'] is None else e['new_born']}\t"
                    f"{'' if e['new_died'] is None else e['new_died']}\t"
                    f"{e['source']}\t{e['status']}\n")


# ------------------------------------------------------------------ apply

def ensure_columns(service, spreadsheet_id: str, header: list[str], cols) -> None:
    updates = []
    next_i = len(header)
    if cols["born"] is None:
        cols["born"] = next_i
        updates.append(("Born", next_i))
        next_i += 1
    if cols["died"] is None:
        cols["died"] = next_i
        updates.append(("Died", next_i))
        next_i += 1
    if not updates:
        return
    data = [{
        "range": f"'{RULERS_SHEET}'!{col_index_to_letter(i)}1",
        "values": [[label]],
    } for label, i in updates]
    service.spreadsheets().values().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"valueInputOption": "RAW", "data": data},
    ).execute()
    print(f"Added header column(s): {', '.join(l for l, _ in updates)}")


def apply_plan(service, spreadsheet_id: str, plan, cols) -> int:
    born_col = col_index_to_letter(cols["born"])
    died_col = col_index_to_letter(cols["died"])
    data = []
    for e in plan:
        if e["new_born"] is not None:
            data.append({
                "range": f"'{RULERS_SHEET}'!{born_col}{e['row']}",
                "values": [[e["new_born"]]],
            })
        if e["new_died"] is not None:
            data.append({
                "range": f"'{RULERS_SHEET}'!{died_col}{e['row']}",
                "values": [[e["new_died"]]],
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
    parser.add_argument("--db", type=Path, default=DEFAULT_DB,
                        help="whoWasWhen.db for reign sanity checks")
    parser.add_argument("--dry-run", action="store_true", help="Plan only (default)")
    parser.add_argument("--apply", action="store_true", help="Write Born/Died cells")
    parser.add_argument("--limit", type=int, help="Only process the first N rulers (testing)")
    parser.add_argument("--report", type=Path, default=Path("birth-death-report.tsv"))
    args = parser.parse_args()

    config, _, spreadsheet_id = load_spreadsheet_config(args.config)
    service = build_sheets_service(config)
    header, rulers, cols = read_rulers(service, spreadsheet_id)
    if args.limit:
        rulers = rulers[:args.limit]
    spans = read_reign_spans(args.db)

    todo = [r for r in rulers if not r["born"] and not r["died"]]
    with_url = [r for r in todo if r["wikipedia"]]
    no_url = [r for r in todo if not r["wikipedia"]]
    print(f"{len(rulers)} rulers; {len(todo)} to fill "
          f"({len(with_url)} with URL, {len(no_url)} without)…")
    qids = resolve_qids(with_url)
    print(f"  resolved {len(qids)} Wikidata items from URLs")
    qids.update(resolve_qids_no_url(no_url))
    print(f"  {len(qids)} total after exact-title matching")
    years = fetch_years(qids)
    print(f"  found birth/death years for {len(years)} items")

    plan = build_plan(rulers, qids, years, spans)
    write_report(plan, args.report)

    counts: dict[str, int] = {}
    for e in plan:
        key = e["status"].split()[0]
        counts[key] = counts.get(key, 0) + 1
    print(f"\nPlan summary ({args.report}):")
    for key in sorted(counts):
        print(f"  {key:10} {counts[key]}")
    filled = sum(1 for e in plan if e["new_born"] is not None or e["new_died"] is not None)
    print(f"  → {filled} rows would get Born/Died (of {len(plan)})")

    if args.apply:
        ensure_columns(service, spreadsheet_id, header, cols)
        n = apply_plan(service, spreadsheet_id, plan, cols)
        print(f"Applied {n} cell updates.")
    else:
        print("\nDry run only — review the report, then re-run with --apply.")


if __name__ == "__main__":
    main()
