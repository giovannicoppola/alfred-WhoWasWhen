#!/usr/bin/env python3
"""Fill in Wikipedia links for rulers whose bare name resolves to a Wikipedia
*disambiguation* page (e.g. "Frederick II" → the "may refer to:" list), which
made the detail view's "About" summary useless. Each link in the reviewed TSV
was auto-suggested from the ruler's title and confirmed against the live
Wikipedia API (regnal/era/country articles verified as real pages; reused
Chinese temple names disambiguated by matching the reign year).

Only fills rulers whose `wikipedia` column is still empty — never overwrites a
link already curated. Idempotent; run against every shipped copy.

Usage:
  python set_ruler_wikipedia.py --dry-run
  python set_ruler_wikipedia.py --apply
  python set_ruler_wikipedia.py --apply --db path/to/other.db --tsv path/to/other.tsv
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_TSV = REPO / "sheet-maintenance" / "patches" / "rulers" / "wikipedia-links.tsv"
DEFAULT_DBS = [
    REPO / "releases" / "whoWasWhen.db",
    REPO / "ios" / "WhoWasWhen" / "Resources" / "whoWasWhen.db",
]


def load_rows(tsv: Path) -> list[dict]:
    with tsv.open(encoding="utf-8", newline="") as fh:
        return [
            {"rulerID": int(r["rulerID"]), "name": r["name"].strip(),
             "wikipedia": r["wikipedia"].strip()}
            for r in csv.DictReader(fh, delimiter="\t")
        ]


def process(db_path: Path, rows: list[dict], apply: bool) -> None:
    if not db_path.exists():
        print(f"! skipped (not found): {db_path}")
        return
    print(f"\n=== {db_path} ===")
    conn = sqlite3.connect(db_path)
    try:
        set_ = skipped_filled = missing = mismatch = 0
        for r in rows:
            cur = conn.execute(
                "SELECT name, wikipedia FROM rulers WHERE rulerID=?", (r["rulerID"],)
            ).fetchone()
            if cur is None:
                missing += 1
                print(f"  ! no ruler #{r['rulerID']} ({r['name']})")
                continue
            name, wiki = cur
            # Guard against the TSV drifting out of sync with the database.
            if name != r["name"]:
                mismatch += 1
                print(f"  ! name mismatch #{r['rulerID']}: db='{name}' tsv='{r['name']}' (skipped)")
                continue
            if wiki:
                skipped_filled += 1          # already has a link — leave it
                continue
            conn.execute("UPDATE rulers SET wikipedia=? WHERE rulerID=?",
                         (r["wikipedia"], r["rulerID"]))
            set_ += 1

        print(f"  {set_} set, {skipped_filled} already had a link, "
              f"{missing} missing, {mismatch} name-mismatch")
        if apply:
            conn.commit()
            print("  committed.")
        else:
            conn.rollback()
            print("  dry-run: no changes written.")
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write changes")
    ap.add_argument("--dry-run", action="store_true", help="report only")
    ap.add_argument("--tsv", type=Path, default=DEFAULT_TSV)
    ap.add_argument("--db", action="append", type=Path, default=None,
                    help="database file (repeatable); defaults to shipped copies")
    args = ap.parse_args()

    if args.apply == args.dry_run:
        ap.error("choose exactly one of --apply / --dry-run")

    rows = load_rows(args.tsv)
    print(f"loaded {len(rows)} link(s) from {args.tsv}")
    for db in (args.db if args.db else DEFAULT_DBS):
        process(Path(db), rows, args.apply)


if __name__ == "__main__":
    main()
