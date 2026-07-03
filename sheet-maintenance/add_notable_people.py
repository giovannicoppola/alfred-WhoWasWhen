#!/usr/bin/env python3
"""Add notable people (painters, composers, writers, scientists,
philosophers) to the Rulers + Periods tabs as lifespan "titles".

Candidates come from Wikidata: for each category's occupation(s), the
people with the most Wikipedia sitelinks (a decent fame proxy) who have
an English Wikipedia article and known birth *and* death years (living
people are excluded — a lifespan period ending at the current year would
read as a death). People tagged with several occupations are assigned to
the category their English description supports (Goethe: "German writer,
artist…" → Writer, not Painter).

A person whose Wikipedia URL already exists on the Rulers tab (e.g.
Marcus Aurelius for Philosopher) is REUSEd: only a Periods row is added
under their existing RulerID. Everyone else gets a new RulerID.

Usage:
  python add_notable_people.py --dry-run [--per-category N]
  python add_notable_people.py --apply

Idempotent: existing (RulerID, Title) period pairs are skipped, so
re-runs only add new people.
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

RULERS_SHEET = "Rulers"
PERIODS_SHEET = "Periods"
USER_AGENT = "WhoWasWhen-sheet-maintenance/1.0 (giovannicoppola@gmail.com)"
SPARQL = "https://query.wikidata.org/sparql"

# (title, [occupation QIDs], [description keywords, most specific first])
CATEGORIES: list[tuple[str, list[str], list[str]]] = [
    ("Artist", ["Q1028181"],  # painter (sculptors ride along via keywords)
     ["painter", "sculptor", "artist", "painting"]),
    ("Composer", ["Q36834"],
     ["composer"]),
    ("Writer", ["Q36180", "Q49757"],  # writer, poet
     ["writer", "poet", "novelist", "playwright", "author", "essayist",
      "dramatist"]),
    ("Scientist", ["Q169470", "Q593644", "Q170790", "Q11063", "Q864503",
                   "Q18805"],  # physicist chemist mathematician astronomer biologist naturalist
     ["physicist", "chemist", "mathematician", "scientist", "astronomer",
      "biologist", "naturalist", "inventor"]),
    ("Philosopher", ["Q4964182"],
     ["philosopher"]),
]
# "martial artist", "songwriter", "screenwriter" must not look like matches.
FALSE_FRIENDS = ["martial artist"]
MIN_SITELINKS = 80
MAX_LIFESPAN = 110
MIN_LIFESPAN = 10


def http_get(url: str, params: dict[str, Any], timeout: int = 120) -> requests.Response:
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            resp = requests.get(url, params=params,
                                headers={"User-Agent": USER_AGENT}, timeout=timeout)
        except requests.exceptions.RequestException as e:
            last_error = e
            time.sleep(10 * (attempt + 1))
            continue
        if resp.status_code in (429, 500, 502, 503, 504):
            time.sleep(10 * (attempt + 1))
            continue
        resp.raise_for_status()
        return resp
    raise last_error or RuntimeError(f"giving up on {url}")


def chunked(seq: list, size: int):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def sparql_qids(occupation: str) -> dict[str, int]:
    """QID → sitelink count for one occupation. Kept minimal (no label
    service, no joins) so even huge classes like writer don't time out."""
    query = f"""
    SELECT ?person ?sitelinks WHERE {{
      ?person wdt:P106 wd:{occupation} ; wikibase:sitelinks ?sitelinks .
      FILTER(?sitelinks > {MIN_SITELINKS})
    }}
    """
    resp = http_get(SPARQL, {"query": query, "format": "json"})
    return {
        b["person"]["value"].rsplit("/", 1)[-1]: int(b["sitelinks"]["value"])
        for b in resp.json()["results"]["bindings"]
    }


def pick_year_claim(statements: list[dict]) -> int | None:
    def rank_key(s):
        return {"preferred": 0, "normal": 1}.get(s.get("rank"), 9)

    for s in sorted(statements, key=rank_key):
        if s.get("rank") == "deprecated":
            continue
        value = s.get("mainsnak", {}).get("datavalue", {}).get("value", {})
        t, precision = value.get("time"), value.get("precision", 0)
        if not t or precision < 9:
            continue
        m = re.match(r"([+-]\d+)-", t)
        if m:
            return int(m.group(1))
    return None


def hydrate(qids: list[str]) -> dict[str, dict[str, Any]]:
    """QID → {name, born, died, url, desc} via wbgetentities (batched)."""
    out: dict[str, dict[str, Any]] = {}
    for batch in chunked(qids, 50):
        data = http_get("https://www.wikidata.org/w/api.php", {
            "action": "wbgetentities", "format": "json",
            "ids": "|".join(batch),
            "props": "labels|descriptions|claims|sitelinks/urls",
            "languages": "en", "sitefilter": "enwiki",
        }).json()
        for qid, entity in data.get("entities", {}).items():
            claims = entity.get("claims", {})
            url = entity.get("sitelinks", {}).get("enwiki", {}).get("url", "")
            out[qid] = {
                "qid": qid,
                "name": entity.get("labels", {}).get("en", {}).get("value", ""),
                "born": pick_year_claim(claims.get("P569", [])),
                "died": pick_year_claim(claims.get("P570", [])),
                "url": url,
                "desc": entity.get("descriptions", {}).get("en", {}).get("value", ""),
            }
        time.sleep(0.2)
    return out


def fetch_category(title: str, occupations: list[str]) -> list[dict[str, Any]]:
    sitelinks: dict[str, int] = {}
    for occ in occupations:
        for qid, n in sparql_qids(occ).items():
            sitelinks[qid] = max(n, sitelinks.get(qid, 0))
        time.sleep(1)
    details = hydrate(sorted(sitelinks))
    people = []
    for qid, d in details.items():
        if not d["name"] or not d["url"]:
            continue
        if d["born"] is None or d["died"] is None:
            continue
        if not (MIN_LIFESPAN <= d["died"] - d["born"] <= MAX_LIFESPAN):
            continue
        people.append({**d, "sitelinks": sitelinks[qid], "queried": title})
    return people


def best_category(person: dict[str, Any]) -> tuple[str, bool]:
    """Category whose keyword appears first in the description; falls back
    to the queried category (flagged when the description names none).
    Whole-word matches only, so "songwriter"/"screenwriter" aren't writers."""
    desc = person["desc"].lower()
    for friend in FALSE_FRIENDS:
        desc = desc.replace(friend, "")
    hits: list[tuple[int, str]] = []
    for title, _, keywords in CATEGORIES:
        positions = [m.start() for k in keywords
                     for m in [re.search(rf"\b{k}\b", desc)] if m]
        if positions:
            hits.append((min(positions), title))
    if hits:
        return min(hits)[1], True
    if "polymath" in desc or not desc:
        # Polymaths queried under several categories read best as Scientist.
        queried = person.get("queried_set", {person["queried"]})
        return ("Scientist" if "Scientist" in queried else person["queried"]), True
    return person["queried"], False


def clean_desc(desc: str) -> str:
    """Drop the trailing "(1770–1827)"-style parenthetical; capitalize."""
    desc = re.sub(r"\s*\([^)]*\d[^)]*\)\s*$", "", desc).strip()
    return desc[:1].upper() + desc[1:] if desc else ""


def norm_url(url: str) -> str:
    """Comparison key: sheet URLs and Wikidata sitelinks differ in
    percent-encoding and mobile/desktop hosts."""
    return unquote(url.strip()).replace(".m.wikipedia", ".wikipedia").rstrip("/")


def period_string(born: int, died: int) -> str:
    if born < 0 and died < 0:
        return f"{-born} BC - {-died} BC"
    if born < 0:
        return f"{-born} BC - {died} AD"
    return f"{born}-{died}"


# ---------------------------------------------------------------- sheet I/O

def header_index(header: list[str]) -> dict[str, int]:
    idx: dict[str, int] = {}
    for i, h in enumerate(header):
        idx.setdefault(normalize_header(h), i)
    return idx


def read_sheet_state(service, spreadsheet_id: str) -> dict[str, Any]:
    rulers = get_sheet_values(service, spreadsheet_id, RULERS_SHEET, "A1:Z5000")
    periods = get_sheet_values(service, spreadsheet_id, PERIODS_SHEET, "A1:M6000")
    r_idx = header_index(rulers[0])
    p_idx = header_index(periods[0])

    def cell(row, i):
        return str(row[i]).strip() if i is not None and len(row) > i else ""

    url_to_ruler: dict[str, tuple[int, str]] = {}
    max_ruler_id = 0
    for row in rulers[1:]:
        rid = cell(row, r_idx.get("rulerid"))
        if not rid.isdigit():
            continue
        max_ruler_id = max(max_ruler_id, int(rid))
        url = cell(row, r_idx.get("wikipedia"))
        if url:
            url_to_ruler.setdefault(norm_url(url), (int(rid), cell(row, r_idx.get("name"))))

    existing_titles: set[tuple[int, str]] = set()
    max_progr = 0
    for row in periods[1:]:
        progr = cell(row, p_idx.get("progr"))
        if progr.isdigit():
            max_progr = max(max_progr, int(progr))
        rid = cell(row, p_idx.get("rulerid"))
        title = cell(row, p_idx.get("title"))
        if rid.isdigit() and title:
            existing_titles.add((int(rid), title))

    return {
        "rulers_header": rulers[0], "rulers_rows": len(rulers),
        "periods_header": periods[0], "periods_rows": len(periods),
        "r_idx": r_idx, "p_idx": p_idx,
        "url_to_ruler": url_to_ruler,
        "existing_titles": existing_titles,
        "max_ruler_id": max_ruler_id,
        "max_progr": max_progr,
    }


# ------------------------------------------------------------------- plan

def build_plan(state, per_category: int) -> list[dict[str, Any]]:
    print("Fetching candidates from Wikidata…")
    raw: dict[str, dict[str, Any]] = {}
    for title, occupations, _ in CATEGORIES:
        people = fetch_category(title, occupations)
        print(f"  {title}: {len(people)} candidates")
        for p in people:
            raw.setdefault(p["qid"], p)
            raw[p["qid"]].setdefault("queried_set", set()).add(title)
        time.sleep(1)

    # Assign each person to one category, then rank by fame within it.
    # People whose description doesn't back any category (Chaplin tagged
    # "composer", Lincoln tagged "writer"…) are dropped — Wikidata's
    # occupation lists are generous — but stay visible in the report.
    by_category: dict[str, list[dict[str, Any]]] = {t: [] for t, _, _ in CATEGORIES}
    dropped: list[dict[str, Any]] = []
    for p in raw.values():
        category, confident = best_category(p)
        if confident:
            by_category[category].append(p)
        else:
            dropped.append(p)

    plan: list[dict[str, Any]] = []
    next_ruler_id = state["max_ruler_id"] + 1
    next_progr = state["max_progr"] + 1
    for title, _, _ in CATEGORIES:
        chosen = sorted(by_category[title], key=lambda p: -p["sitelinks"])[:per_category]
        chosen.sort(key=lambda p: p["born"])  # chronological progrTitle order
        for p in chosen:
            entry = {**p, "title": title, "ruler_id": None, "progr": None,
                     "status": ""}
            existing = state["url_to_ruler"].get(norm_url(p["url"]))
            rid = existing[0] if existing else None
            if rid is not None:
                if (rid, title) in state["existing_titles"]:
                    entry["status"] = "SKIP already has this title"
                    plan.append(entry)
                    continue
                entry["ruler_id"] = rid
                entry["status"] = f"REUSE rulerID {rid} ({existing[1]})"
            else:
                entry["ruler_id"] = next_ruler_id
                entry["status"] = "NEW"
                next_ruler_id += 1
            entry["progr"] = next_progr
            next_progr += 1
            plan.append(entry)

    for p in sorted(dropped, key=lambda p: -p["sitelinks"]):
        plan.append({**p, "title": p["queried"], "ruler_id": None, "progr": None,
                     "status": "SKIP description doesn't match category"})
    return plan


def plan_from_report(path: Path, state) -> list[dict[str, Any]]:
    """Rebuild the plan from a reviewed dry-run TSV so --apply writes
    exactly what was approved (no Wikidata refetch, no ranking drift).
    NEW rulerIDs/Progr are re-assigned from the live sheet maxima."""
    plan: list[dict[str, Any]] = []
    next_ruler_id = state["max_ruler_id"] + 1
    next_progr = state["max_progr"] + 1
    with path.open(encoding="utf-8") as f:
        header = f.readline().rstrip("\n").split("\t")
        for line in f:
            row = dict(zip(header, line.rstrip("\n").split("\t")))
            entry = {
                "title": row["category"], "name": row["name"],
                "born": int(row["born"]), "died": int(row["died"]),
                "desc": row["desc"], "url": row["url"],
                "sitelinks": int(row["sitelinks"]),
                "ruler_id": None, "progr": None, "status": row["status"],
            }
            if row["status"].startswith("SKIP"):
                plan.append(entry)
                continue
            if row["status"].startswith("REUSE"):
                entry["ruler_id"] = int(row["rulerID"])
                if (entry["ruler_id"], entry["title"]) in state["existing_titles"]:
                    entry["status"] = "SKIP already has this title"
                    plan.append(entry)
                    continue
            else:
                entry["ruler_id"] = next_ruler_id
                next_ruler_id += 1
            entry["progr"] = next_progr
            next_progr += 1
            plan.append(entry)
    return plan


def write_report(plan: list[dict[str, Any]], path: Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        f.write("category\tname\tborn\tdied\tsitelinks\trulerID\tprogr\tdesc\turl\tstatus\n")
        for e in plan:
            f.write(f"{e['title']}\t{e['name']}\t{e['born']}\t{e['died']}\t"
                    f"{e['sitelinks']}\t{e['ruler_id'] or ''}\t{e['progr'] or ''}\t"
                    f"{clean_desc(e['desc'])}\t{e['url']}\t{e['status']}\n")


# ------------------------------------------------------------------ apply

def sheet_row(width: int, cells: dict[int, Any]) -> list[Any]:
    row: list[Any] = [""] * width
    for i, v in cells.items():
        row[i] = v
    return row


def apply_plan(service, spreadsheet_id: str, state, plan) -> None:
    r_idx, p_idx = state["r_idx"], state["p_idx"]

    # Born/Died columns may not exist yet (created by add_birth_death.py).
    header = state["rulers_header"]
    for label in ("Born", "Died"):
        key = normalize_header(label)
        if key not in r_idx:
            i = len(header)
            header.append(label)
            r_idx[key] = i
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"'{RULERS_SHEET}'!{col_index_to_letter(i)}1",
                valueInputOption="RAW", body={"values": [[label]]},
            ).execute()
            print(f"Added Rulers header column: {label}")

    new_rulers = [e for e in plan if e["status"].startswith("NEW")]
    ruler_width = max(r_idx.values()) + 1
    ruler_rows = [sheet_row(ruler_width, {
        r_idx["name"]: e["name"],
        r_idx["rulerid"]: e["ruler_id"],
        r_idx["wikipedia"]: e["url"],
        r_idx["notes"]: clean_desc(e["desc"]),
        r_idx["born"]: e["born"],
        r_idx["died"]: e["died"],
    }) for e in new_rulers]
    if ruler_rows:
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"'{RULERS_SHEET}'!A1",
            valueInputOption="RAW", insertDataOption="INSERT_ROWS",
            body={"values": ruler_rows},
        ).execute()
        print(f"Appended {len(ruler_rows)} Rulers rows")

    period_entries = [e for e in plan if not e["status"].startswith("SKIP")]
    period_width = max(p_idx.values()) + 1
    name_col = 3  # column D: clean display name (header cell is blank)
    period_rows = [sheet_row(period_width, {
        p_idx["progr"]: e["progr"],
        p_idx["title"]: e["title"],
        name_col: e["name"],
        p_idx["rulerid"]: e["ruler_id"],
        p_idx["period"]: period_string(e["born"], e["died"]),
        p_idx["notes"]: clean_desc(e["desc"]),
    }) for e in period_entries]
    if period_rows:
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"'{PERIODS_SHEET}'!A1",
            valueInputOption="RAW", insertDataOption="INSERT_ROWS",
            body={"values": period_rows},
        ).execute()
        print(f"Appended {len(period_rows)} Periods rows")


# ------------------------------------------------------------------- main

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--dry-run", action="store_true", help="Plan only (default)")
    parser.add_argument("--apply", action="store_true", help="Append sheet rows")
    parser.add_argument("--per-category", type=int, default=40,
                        help="People per category (default 40)")
    parser.add_argument("--report", type=Path, default=Path("notable-people-report.tsv"))
    parser.add_argument("--from-report", type=Path,
                        help="Apply a reviewed dry-run TSV verbatim instead of refetching")
    args = parser.parse_args()

    config, _, spreadsheet_id = load_spreadsheet_config(args.config)
    service = build_sheets_service(config)
    state = read_sheet_state(service, spreadsheet_id)
    print(f"Sheet: max rulerID {state['max_ruler_id']}, max Progr {state['max_progr']}")

    if args.from_report:
        plan = plan_from_report(args.from_report, state)
    else:
        plan = build_plan(state, args.per_category)
        write_report(plan, args.report)

    counts: dict[str, int] = {}
    for e in plan:
        key = f"{e['title']}/{e['status'].split()[0]}"
        counts[key] = counts.get(key, 0) + 1
    print(f"\nPlan summary ({args.report}):")
    for key in sorted(counts):
        print(f"  {key:25} {counts[key]}")

    if args.apply:
        apply_plan(service, spreadsheet_id, state, plan)
        print("Done. Run the DB generator next.")
    else:
        print("\nDry run only — review the report, then re-run with --apply.")


if __name__ == "__main__":
    main()
