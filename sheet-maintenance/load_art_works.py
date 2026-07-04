#!/usr/bin/env python3
"""Load "key works" of the creative roster into the events table.

Reads a reviewed TSV (Category / Artist / Year / Work) and inserts one event
per row, titled "Artist: Work" and dated to its year, so a work of art shows up
in a year search alongside historical events. The event's Wikipedia link points
at the artist's page (every roster artist has one), since the composite event
name has no article of its own.

The `notes` column doubles as a searchable subtitle ("Musical work", "Work of
art", ...) matching the artist's category.

Idempotent: an event whose exact name already exists is skipped, so re-running
never duplicates. Run it against every shipped copy of the database.

Usage:
  python load_art_works.py --dry-run
  python load_art_works.py --apply
  python load_art_works.py --apply --db path/to/other.db --tsv path/to/other.tsv
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_TSV = REPO / "sheet-maintenance" / "patches" / "events" / "art-works.tsv"
DEFAULT_DBS = [
    REPO / "releases" / "whoWasWhen.db",
    REPO / "ios" / "WhoWasWhen" / "Resources" / "whoWasWhen.db",
]

SUBTITLE = {
    "Composer": "Musical work",
    "Artist": "Work of art",
    "Writer": "Literary work",
    "Scientist": "Scientific work",
    "Philosopher": "Philosophical work",
}


def load_rows(tsv: Path) -> list[dict]:
    with tsv.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        rows = []
        for r in reader:
            rows.append({
                "category": r["Category"].strip(),
                "artist": r["Artist"].strip(),
                "year": int(r["Year"].strip()),
                "work": r["Work"].strip(),
            })
    return rows


def artist_wiki(conn: sqlite3.Connection) -> dict[str, str]:
    cur = conn.execute("SELECT name, wikipedia FROM rulers")
    return {name: (wiki or "") for name, wiki in cur.fetchall()}


def year_id(conn: sqlite3.Connection, year: int) -> int:
    conn.execute("INSERT OR IGNORE INTO years(year) VALUES(?)", (year,))
    return conn.execute(
        "SELECT yearID FROM years WHERE year=?", (year,)
    ).fetchone()[0]


def process(db_path: Path, rows: list[dict], apply: bool) -> None:
    if not db_path.exists():
        print(f"! skipped (not found): {db_path}")
        return
    print(f"\n=== {db_path} ===")
    conn = sqlite3.connect(db_path)
    try:
        wiki = artist_wiki(conn)
        inserted = skipped = 0
        missing_wiki = []
        for r in rows:
            name = f"{r['artist']}: {r['work']}"
            exists = conn.execute(
                "SELECT 1 FROM byEvents WHERE eventName=?", (name,)
            ).fetchone()
            if exists:
                skipped += 1
                continue
            w = wiki.get(r["artist"], "")
            if not w:
                missing_wiki.append(r["artist"])
            cur = conn.execute(
                """INSERT INTO byEvents
                   (eventName, startYear, endYear, notes, wikipedia,
                    startMonth, startDay)
                   VALUES (?, ?, ?, ?, ?, NULL, NULL)""",
                (name, r["year"], r["year"],
                 SUBTITLE.get(r["category"], ""), w),
            )
            event_id = cur.lastrowid
            yid = year_id(conn, r["year"])
            conn.execute(
                "INSERT INTO byYear(yearID, eventID) VALUES(?, ?)",
                (yid, event_id),
            )
            inserted += 1

        print(f"  {inserted} inserted, {skipped} already present")
        if missing_wiki:
            print(f"  ! no wiki for: {sorted(set(missing_wiki))}")
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
    print(f"loaded {len(rows)} work(s) from {args.tsv}")
    dbs = args.db if args.db else DEFAULT_DBS
    for db in dbs:
        process(Path(db), rows, args.apply)


if __name__ == "__main__":
    main()
