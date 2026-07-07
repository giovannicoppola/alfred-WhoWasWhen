#!/usr/bin/env python3
"""Build the structured `works` table linking each key-work event to its creator.

The creative roster's works are stored in `byEvents` as "Artist: Work" rows
tagged by a `notes` subtitle ("Work of art", "Musical work", ...). This derives
a proper table linking each to the creator's `rulers` record, so the quiz can
ask "Who wrote «work»?" from a real foreign key instead of parsing event names
at runtime. The "Artist" prefix is the canonical `rulers.name` (that is how
load_art_works.py resolved each work's Wikipedia link), so the link is an exact
name match — no fuzzy matching.

Fully derived and idempotent: the table is dropped and rebuilt every run, so it
always reflects the current events + roster. Run against every shipped copy.

Usage:
  python build_works_table.py --dry-run
  python build_works_table.py --apply
  python build_works_table.py --apply --db path/to/other.db
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_DBS = [
    REPO / "releases" / "whoWasWhen.db",
    REPO / "ios" / "WhoWasWhen" / "Resources" / "whoWasWhen.db",
]

# byEvents.notes subtitle -> the creative calling (and the quiz's answer pool).
CATEGORY_BY_NOTE = {
    "Work of art": "Artist",
    "Musical work": "Composer",
    "Literary work": "Writer",
    "Scientific work": "Scientist",
    "Philosophical work": "Philosopher",
}

SCHEMA = """
CREATE TABLE works (
    workID         INTEGER PRIMARY KEY AUTOINCREMENT,
    eventID        INTEGER NOT NULL UNIQUE,
    creatorRulerID INTEGER NOT NULL,
    workTitle      TEXT    NOT NULL,
    year           INTEGER NOT NULL,
    category       TEXT    NOT NULL
);
"""


def process(db_path: Path, apply: bool) -> None:
    if not db_path.exists():
        print(f"! skipped (not found): {db_path}")
        return
    print(f"\n=== {db_path} ===")
    conn = sqlite3.connect(db_path)
    try:
        names = {n: rid for (rid, n) in
                 conn.execute("SELECT rulerID, name FROM rulers")}
        placeholders = ",".join("?" * len(CATEGORY_BY_NOTE))
        events = conn.execute(
            f"SELECT eventID, eventName, startYear, notes FROM byEvents "
            f"WHERE notes IN ({placeholders})",
            tuple(CATEGORY_BY_NOTE),
        ).fetchall()

        linked, unlinked = [], []
        for event_id, name, year, note in events:
            artist, sep, work = name.partition(": ")
            rid = names.get(artist)
            if sep and rid is not None and work:
                linked.append((event_id, rid, work, year, CATEGORY_BY_NOTE[note]))
            else:
                unlinked.append(name)

        conn.execute("DROP TABLE IF EXISTS works")
        conn.execute(SCHEMA)
        conn.executemany(
            "INSERT INTO works(eventID, creatorRulerID, workTitle, year, category) "
            "VALUES (?, ?, ?, ?, ?)",
            linked,
        )
        conn.execute("CREATE INDEX idx_works_category ON works(category)")
        conn.execute("CREATE INDEX idx_works_creator ON works(creatorRulerID)")

        print(f"  {len(linked)} works linked, {len(unlinked)} unlinked")
        if unlinked:
            print(f"  ! could not link: {sorted(unlinked)[:10]}")
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
    ap.add_argument("--db", action="append", type=Path, default=None,
                    help="database file (repeatable); defaults to shipped copies")
    args = ap.parse_args()

    if args.apply == args.dry_run:
        ap.error("choose exactly one of --apply / --dry-run")

    dbs = args.db if args.db else DEFAULT_DBS
    for db in dbs:
        process(Path(db), args.apply)


if __name__ == "__main__":
    main()
