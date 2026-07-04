#!/usr/bin/env python3
"""Mark still-living reigns / active lives as open-ended ("present").

When the database is built, every ongoing period is stubbed to the build year
(e.g. Charles III shows "2022-2025" and is only findable through 2025). That
reads as if the reign *ended*, and — because year search uses the materialised
`byYear` link table — time-travelling to the current year no longer finds them.

This script rewrites those periods to be open-ended:

  * `byPeriod.period`  -> "START-present"   (shown verbatim as the item title)
  * `byPeriod.endYear` -> max(endYear, current year)   (travel-to-end target)
  * `byYear`           -> links filled from START through the new end year, so
                          a search for the current year finds them again.

Two populations are treated as ongoing:

  offices      the *current* holder of a still-active office (monarch, pope,
               president, PM...). "Current" = the alive holder with the latest
               start year for that title, so Biden/Sunak (alive but out of
               office) are correctly left closed while Trump/Starmer are not.
  professions  every living person in a vocation title (Artist, Composer,
               Writer, Scientist, Philosopher) — active until death.

It also fixes one known data bug: Felipe VI (King of Spain, alive) carries a
spurious died=2024.

The script is idempotent — re-running it (e.g. next year) simply re-extends the
open periods to the new current year. Run it against every shipped copy of the
database.

Usage:
  python mark_living_present.py --dry-run     # report, change nothing
  python mark_living_present.py --apply       # write the default shipped DBs
  python mark_living_present.py --apply --db path/to/other.db
"""

from __future__ import annotations

import argparse
import sqlite3
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_DBS = [
    REPO / "releases" / "whoWasWhen.db",
    REPO / "ios" / "WhoWasWhen" / "Resources" / "whoWasWhen.db",
]

PROFESSIONS = ("Artist", "Composer", "Philosopher", "Scientist", "Writer")
# A period ending this recently was stubbed at build time, i.e. it is genuinely
# current rather than an ancient floruit that happens to lack a death year.
ERA_MIN = 2024


def fmt_year(year: int) -> str:
    return f"{-year} BC" if year < 0 else str(year)


def fix_felipe(conn: sqlite3.Connection) -> list[str]:
    """Clear the erroneous death year on the living King of Spain."""
    cur = conn.execute(
        "SELECT rulerID FROM rulers WHERE name='Felipe VI' AND died IS NOT NULL"
    )
    notes = []
    for (rid,) in cur.fetchall():
        conn.execute("UPDATE rulers SET died=NULL WHERE rulerID=?", (rid,))
        notes.append("data fix: cleared Felipe VI died year (he is alive)")
    return notes


def find_targets(conn: sqlite3.Connection) -> list[dict]:
    """Return the period rows that should become open-ended."""
    placeholders = ",".join("?" * len(PROFESSIONS))

    # Offices: the alive holder with the latest start year per still-active
    # title. GROUP BY keeps one row per title; MAX(startYear) picks the sitting
    # incumbent over former (but living) holders of the same office.
    office_rows = conn.execute(
        f"""
        SELECT p.periodID, p.startYear, p.endYear, r.name, t.title
        FROM byPeriod p
        JOIN rulers r ON r.rulerID = p.rulerID
        JOIN titles t ON t.titleID = p.titleID
        JOIN (
            SELECT p2.titleID, MAX(p2.startYear) AS mx
            FROM byPeriod p2
            JOIN rulers r2 ON r2.rulerID = p2.rulerID
            JOIN titles t2 ON t2.titleID = p2.titleID
            WHERE r2.died IS NULL
              AND p2.endYear >= ?
              AND t2.title NOT IN ({placeholders})
            GROUP BY p2.titleID
        ) cur ON cur.titleID = p.titleID AND cur.mx = p.startYear
        WHERE r.died IS NULL
        """,
        (ERA_MIN, *PROFESSIONS),
    ).fetchall()

    # Professions: every living person in a vocation title, latest period each.
    prof_rows = conn.execute(
        f"""
        SELECT p.periodID, p.startYear, p.endYear, r.name, t.title
        FROM byPeriod p
        JOIN rulers r ON r.rulerID = p.rulerID
        JOIN titles t ON t.titleID = p.titleID
        JOIN (
            SELECT p2.rulerID, p2.titleID, MAX(p2.startYear) AS mx
            FROM byPeriod p2
            JOIN rulers r2 ON r2.rulerID = p2.rulerID
            WHERE r2.died IS NULL AND p2.endYear >= ?
            GROUP BY p2.rulerID, p2.titleID
        ) cur ON cur.rulerID = p.rulerID AND cur.titleID = p.titleID
                 AND cur.mx = p.startYear
        WHERE r.died IS NULL AND t.title IN ({placeholders})
        """,
        (ERA_MIN, *PROFESSIONS),
    ).fetchall()

    targets = {}
    for kind, rows in (("office", office_rows), ("profession", prof_rows)):
        for period_id, start, end, name, title in rows:
            targets[period_id] = dict(
                periodID=period_id, startYear=start, endYear=end,
                name=name, title=title, kind=kind,
            )
    return sorted(targets.values(), key=lambda t: (t["title"], t["name"]))


def year_id(conn: sqlite3.Connection, year: int) -> int:
    conn.execute("INSERT OR IGNORE INTO years(year) VALUES(?)", (year,))
    return conn.execute(
        "SELECT yearID FROM years WHERE year=?", (year,)
    ).fetchone()[0]


def apply_target(conn: sqlite3.Connection, t: dict, current_year: int) -> str:
    new_end = max(t["endYear"], current_year)
    new_period = f"{fmt_year(t['startYear'])}-present"

    conn.execute(
        "UPDATE byPeriod SET period=?, endYear=? WHERE periodID=?",
        (new_period, new_end, t["periodID"]),
    )
    links = 0
    for yr in range(t["startYear"], new_end + 1):
        yid = year_id(conn, yr)
        cur = conn.execute(
            "INSERT OR IGNORE INTO byYear(yearID, periodID) VALUES(?, ?)",
            (yid, t["periodID"]),
        )
        links += cur.rowcount
    return (
        f"  {t['name']:<24} {t['title']:<24} "
        f"{t['startYear']}-{t['endYear']} -> {new_period} "
        f"(end {new_end}, +{links} year link{'s' if links != 1 else ''})"
    )


def process(db_path: Path, apply: bool, current_year: int) -> None:
    if not db_path.exists():
        print(f"! skipped (not found): {db_path}")
        return
    print(f"\n=== {db_path} ===")
    conn = sqlite3.connect(db_path)
    try:
        fixes = fix_felipe(conn)
        for note in fixes:
            print(f"  {note}")
        targets = find_targets(conn)
        print(f"  {len(targets)} ongoing period(s):")
        for t in targets:
            print(apply_target(conn, t, current_year))
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
    ap.add_argument("--year", type=int, default=date.today().year,
                    help="current year (defaults to today)")
    args = ap.parse_args()

    if args.apply == args.dry_run:
        ap.error("choose exactly one of --apply / --dry-run")

    dbs = args.db if args.db else DEFAULT_DBS
    for db in dbs:
        process(Path(db), args.apply, args.year)


if __name__ == "__main__":
    main()
