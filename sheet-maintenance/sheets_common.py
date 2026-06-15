"""Shared Google Sheets helpers for WhoWasWhen sheet maintenance."""

from __future__ import annotations

import os
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import yaml
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT_DIR / "config.yaml"
DEFAULT_PATCHES = ROOT_DIR / "patches" / "merged-rulers.yaml"


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def expand_path(path: str) -> str:
    return os.path.expanduser(path)


def get_credentials(config: dict[str, Any] | None = None):
    config = config or {}
    creds_path = os.environ.get("KEYFILE") or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path and config.get("credentials"):
        creds_path = config["credentials"]
    if not creds_path:
        raise SystemExit(
            "No credentials found. Set KEYFILE (alfred-gsheets), "
            "GOOGLE_APPLICATION_CREDENTIALS, or credentials in config.yaml"
        )
    creds_path = expand_path(creds_path)
    if not os.path.isfile(creds_path):
        raise SystemExit(f"Credentials file not found: {creds_path}")
    return service_account.Credentials.from_service_account_file(creds_path, scopes=SCOPES)


def build_sheets_service(config: dict[str, Any] | None = None):
    return build("sheets", "v4", credentials=get_credentials(config), cache_discovery=False)


def normalize_header(cell: Any) -> str:
    if cell is None:
        return ""
    return re.sub(r"\s+", " ", str(cell).strip().lower())


def col_letter_to_index(letter: str) -> int:
    letter = letter.strip().upper()
    n = 0
    for ch in letter:
        n = n * 26 + (ord(ch) - ord("A") + 1)
    return n - 1


def col_index_to_letter(index: int) -> str:
    index += 1
    letters = []
    while index:
        index, rem = divmod(index - 1, 26)
        letters.append(chr(rem + ord("A")))
    return "".join(reversed(letters))


def get_sheet_values(service, spreadsheet_id: str, sheet_name: str, a1_range: str) -> list[list[Any]]:
    quoted = sheet_name.replace("'", "''")
    full_range = f"'{quoted}'!{a1_range}"
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=full_range)
        .execute()
    )
    return result.get("values", [])


def list_sheets(service, spreadsheet_id: str) -> list[dict[str, Any]]:
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    return meta.get("sheets", [])


def discover_sheets(service, spreadsheet_id: str) -> None:
    print(f"Spreadsheet: {spreadsheet_id}\n")
    for entry in list_sheets(service, spreadsheet_id):
        props = entry["properties"]
        title = props["title"]
        gid = props["sheetId"]
        header = get_sheet_values(service, spreadsheet_id, title, "1:1")
        row1 = header[0] if header else []
        preview = ", ".join(str(c) for c in row1[:14] if c != "")
        print(f"  [{gid}] {title!r}")
        print(f"       headers: {preview or '(empty)'}")
    print()


def detect_column_optional(headers: list[str], candidates: list[str], fallback: str | None) -> str | None:
    norm = [normalize_header(h) for h in headers]
    for candidate in candidates:
        c = normalize_header(candidate)
        if c in norm:
            return col_index_to_letter(norm.index(c))
    return fallback


def detect_column(headers: list[str], candidates: list[str], fallback: str | None) -> str:
    col = detect_column_optional(headers, candidates, fallback)
    if not col:
        raise SystemExit(f"Could not detect column from headers={headers!r} candidates={candidates}")
    return col


def detect_by_period_sheet(service, spreadsheet_id: str, preferred: str | None) -> str:
    if preferred:
        return preferred
    for entry in list_sheets(service, spreadsheet_id):
        title = entry["properties"]["title"]
        header = get_sheet_values(service, spreadsheet_id, title, "1:1")
        if not header:
            continue
        cells = [normalize_header(c) for c in header[0]]
        if "progr" in cells and "rulerid" in cells and "period" in cells:
            return title
    raise SystemExit("Could not auto-detect Periods sheet. Set sheets.by_period in config.yaml")


def detect_rulers_sheet(service, spreadsheet_id: str, preferred: str | None) -> str | None:
    if preferred:
        return preferred
    for entry in list_sheets(service, spreadsheet_id):
        title = entry["properties"]["title"]
        header = get_sheet_values(service, spreadsheet_id, title, "1:1")
        if not header:
            continue
        cells = [normalize_header(h) for h in header[0]]
        if "rulerid" in cells and ("biography" in cells or "wikipedia" in cells):
            return title
        if len(cells) >= 2 and cells[0] == "progr" and "name" in cells:
            return title
    return None


def parse_period_start(period: str | None) -> int | None:
    if not period:
        return None
    m = re.match(r"^(-?\d+)", str(period).strip().replace(" ", ""))
    return int(m.group(1)) if m else None


def is_minor_title(title: str) -> bool:
    return any(
        x in title
        for x in (
            "Roman Consul",
            "Consular Tribune",
            "Decemvir",
            "Dictator",
            "Tribune",
            "Interrex",
            "sine collega",
        )
    )


def build_progr_row_map(
    rows: list[list[Any]], progr_col: str, ruler_col: str
) -> dict[int, tuple[int, Any]]:
    pi = col_letter_to_index(progr_col)
    ri = col_letter_to_index(ruler_col)
    mapping: dict[int, tuple[int, Any]] = {}
    for row_idx, row in enumerate(rows, start=1):
        if row_idx == 1 or len(row) <= pi:
            continue
        progr_raw = row[pi]
        if progr_raw in (None, ""):
            continue
        try:
            progr = int(float(str(progr_raw).strip()))
        except ValueError:
            continue
        current = row[ri] if len(row) > ri else ""
        mapping[progr] = (row_idx, current)
    return mapping


def load_spreadsheet_config(
    config_path: Path = DEFAULT_CONFIG,
    patches_path: Path | None = DEFAULT_PATCHES,
):
    config = load_yaml(config_path) if config_path.is_file() else {}
    patches = load_yaml(patches_path) if patches_path and patches_path.is_file() else {}
    spreadsheet_id = config.get("spreadsheet_id") or patches.get("spreadsheet_id")
    if not spreadsheet_id:
        raise SystemExit("spreadsheet_id missing in config.yaml or patches yaml")
    return config, patches, spreadsheet_id


def normalize_event_name(name: str) -> str:
    """Lowercase, collapse whitespace — legacy exact match key."""
    return re.sub(r"\s+", " ", str(name).strip().lower())


def fold_for_search(text: str) -> str:
    """Match Alfred ruler-query search folding: lowercase, strip accents, ß→ss."""
    text = re.sub(r"\s+", " ", str(text).strip().lower())
    text = text.replace("ß", "ss").replace("ẞ", "ss")
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return unicodedata.normalize("NFC", text).strip()


def event_name_core(name: str) -> str:
    """Name with parenthetical date/details removed, then folded."""
    core = re.sub(r"\s*\([^)]*\)", "", str(name)).strip()
    return fold_for_search(core)


def fold_event_name(name: str) -> str:
    return fold_for_search(name)


def event_duplicate_reason(new_name: str, existing: dict[str, Any]) -> str | None:
    """Return skip reason if new_name duplicates an existing sheet row."""
    new_norm = normalize_event_name(new_name)
    new_fold = fold_event_name(new_name)
    new_core = event_name_core(new_name)

    ex_norm = existing.get("normalized", "")
    ex_fold = existing.get("folded", "")
    ex_core = existing.get("core", "")

    if new_norm and new_norm == ex_norm:
        return "exact name match"
    if new_fold and new_fold == ex_fold:
        return "accent-insensitive name match"
    if new_core and ex_core and new_core == ex_core:
        return "same core name (ignoring dates and accents)"
    if new_fold and ex_core and new_fold == ex_core:
        return "same core name (ignoring dates and accents)"
    if new_core and ex_fold and new_core == ex_fold:
        return "same core name (ignoring dates and accents)"
    return None


def event_similarity_warnings(
    new_name: str,
    existing_rows: list[dict[str, Any]],
    *,
    new_sorting_year: Any = "",
    ratio_threshold: float = 0.88,
) -> list[str]:
    """Non-blocking warnings for near-duplicate names."""
    warnings: list[str] = []
    candidate = enrich_existing_event_row(
        new_name,
        {"name": new_name, "sorting_year": new_sorting_year, "progr": 0, "row_idx": 0},
    )

    for row in existing_rows:
        ok, reason = should_merge_events(candidate, row, similar_threshold=ratio_threshold)
        if ok:
            continue
        ex_name = row.get("name", "")
        if event_duplicate_reason(new_name, row):
            continue
        ex_core = row.get("core", "")
        new_core = candidate.get("core", "")
        if len(new_core) < 8 or not ex_core or new_core == ex_core:
            continue
        ratio = SequenceMatcher(None, new_core, ex_core).ratio()
        if ratio >= ratio_threshold and str(new_sorting_year).strip() == str(row.get("sorting_year", "")).strip():
            warnings.append(f"SIMILAR to {ex_name!r} ({ratio:.0%} match, not appended)")
    return warnings


def enrich_existing_event_row(name: str, row: dict[str, Any]) -> dict[str, Any]:
    row = dict(row)
    row["normalized"] = normalize_event_name(name)
    row["folded"] = fold_event_name(name)
    row["core"] = event_name_core(name)
    return row


def parse_sorting_year(value: Any) -> int | None:
    raw = str(value or "").strip().split("–")[0].split("-")[0]
    try:
        return int(raw)
    except ValueError:
        return None


def should_merge_events(a: dict[str, Any], b: dict[str, Any], *, similar_threshold: float = 0.93) -> tuple[bool, str]:
    """True when two sheet rows represent the same historical event."""
    reason = event_duplicate_reason(a["name"], b)
    ya = str(a.get("sorting_year", "")).strip()
    yb = str(b.get("sorting_year", "")).strip()
    if reason:
        if ya == yb:
            return True, reason
        ia, ib = parse_sorting_year(ya), parse_sorting_year(yb)
        if ia is not None and ib is not None and abs(ia - ib) <= 1:
            return True, f"{reason} (years {ya}/{yb})"
        return False, ""
    if ya == yb and len(a.get("core", "")) >= 8:
        ratio = SequenceMatcher(None, a["core"], b["core"]).ratio()
        if ratio >= similar_threshold:
            return True, f"similar ({ratio:.0%})"
    return False, ""


def score_event_for_keep(event: dict[str, Any]) -> int:
    score = 0
    if event.get("wikipedia"):
        score += 100
    score += len(str(event.get("notes") or ""))
    if "(" in str(event.get("name") or ""):
        score += 20
    score += int(event.get("progr") or 0) // 1000
    return score


def choose_event_keeper(cluster: list[dict[str, Any]]) -> dict[str, Any]:
    return max(cluster, key=score_event_for_keep)


def merge_event_fields(cluster: list[dict[str, Any]]) -> dict[str, Any]:
    keeper = choose_event_keeper(cluster)
    others = [e for e in cluster if e is not keeper]
    notes = str(keeper.get("notes") or "").strip()
    wiki = str(keeper.get("wikipedia") or "").strip()
    name = str(keeper.get("name") or "").strip()

    for other in others:
        other_name = str(other.get("name") or "").strip()
        if len(other_name) > len(name) or (
            "(" in other_name and "(" not in name
        ):
            name = other_name
        other_notes = str(other.get("notes") or "").strip()
        if other_notes and other_notes not in notes:
            notes = f"{notes} {other_notes}".strip() if notes else other_notes
        other_wiki = str(other.get("wikipedia") or "").strip()
        if not wiki and other_wiki:
            wiki = other_wiki

    merged = dict(keeper)
    merged["name"] = name
    merged["notes"] = notes
    merged["wikipedia"] = wiki
    merged["delete_rows"] = [e for e in others]
    return merged


def detect_progr_column(headers: list[str], fallback: str = "A") -> str:
    for i, header in enumerate(headers):
        if normalize_header(header).startswith("progr"):
            return col_index_to_letter(i)
    return fallback


def detect_events_sheet(service, spreadsheet_id: str, preferred: str | None) -> str:
    if preferred:
        return preferred
    for entry in list_sheets(service, spreadsheet_id):
        title = entry["properties"]["title"]
        if title.lower() == "events":
            return title
        header = get_sheet_values(service, spreadsheet_id, title, "1:1")
        if not header:
            continue
        cells = [normalize_header(c) for c in header[0]]
        if "event name" in cells and ("numerical year" in cells or "sorting year" in cells):
            return title
    raise SystemExit("Could not auto-detect Events sheet. Set sheets.events in config or event file yaml")
