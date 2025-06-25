#!/usr/bin/env python3
"""WhoWasWhen Database Generator.

This script creates a SQLite database for the WhoWasWhen workflow, starting from a Google spreadsheet.

Usage:
  whowaswhen.py [options]
  whowaswhen.py -h | --help

Options:
  -h --help                Show this help message and exit.
  --keyfile=<keyfile>      Path to Google API service account key file [default from config].
  --sheet-url=<url>        Google Sheet URL [default from config].
  --rulers-sheet=<name>    Name of the sheet containing rulers data [default from config].
  --periods-sheet=<name>   Name of the sheet containing periods data [default from config].
  --db=<dbname>            Output SQLite database name [default from config].
  --no-from-file           Force API calls instead of reading from local TSV files.
  --alfred                 Output JSON result for Alfred workflow.

"""
import csv
import json
import os
import sqlite3
import sys
from time import time

import gspread
import gspread.exceptions
from docopt import docopt
from google.oauth2 import service_account

# Try to import from config, but provide defaults if not available
try:
    from config import GSHEET_URL, KEYFILE, MY_DB, MY_PERIOD_SHEET, MY_RULERS_SHEET, log
except ImportError:
    # Default values if config.py is not available
    KEYFILE = "keyfile.json"
    GSHEET_URL = None
    MY_PERIOD_SHEET = "Periods"
    MY_RULERS_SHEET = "Rulers"
    MY_DB = "whowaswhen.db"

    def log(message):
        """Default log function if not imported from config."""
        print(message, file=sys.stderr)


def getSheet(keyfile, mysheetURL, myPeriodSheet, myColumns, tsv_filename=None):
    """Retrieve tables from a Google Sheet and convert them into a nested dictionary.

    Args:
        keyfile: Path to the Google API service account key file
        mysheetURL: URL of the Google Sheet
        myPeriodSheet: Name of the sheet to retrieve
        myColumns: List of column names to include
        tsv_filename: Optional filename to save TSV data

    Returns:
        A nested dictionary with data from the sheet
    """

    def list_to_nested_dict(all_values, selected_columns):
        headers = all_values[0]  # The first row is the header
        indices = [
            headers.index(col) for col in selected_columns if col in headers
        ]  # Indices of selected columns
        data_dict = {}

        for row in all_values[1:]:
            # Create a dictionary for each row with selected columns only
            row_dict = {headers[i]: row[i] for i in indices}
            # Use the first column as the key for the main dictionary
            data_dict[row[0]] = row_dict

        return data_dict

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    credentials = service_account.Credentials.from_service_account_file(
        keyfile, scopes=scopes
    )
    file = gspread.authorize(credentials)  # authenticate the JSON key with gspread

    # opening the file
    try:
        sheet = file.open_by_url(mysheetURL)

    except gspread.exceptions.NoValidUrlKeyFound as e:
        log(f"URL not valid: {e}")
        raise
    except ValueError as e:
        log(f"ValueError: {e}")
        raise
    except IOError as e:
        # Handle input/output errors
        log(f"IOError: {e}")
        raise
    except Exception as e:
        # Catch any remaining errors
        log(f"Exception: {e}")
        raise

    # fetching the worksheet
    try:
        worksheet = sheet.worksheet(myPeriodSheet)

    except gspread.exceptions.WorksheetNotFound as e:
        log(f"Sheet Not Found: {e}")
        raise

    # Get all values from the worksheet
    all_values = worksheet.get_all_values()

    # converting into a dictionary with key = counter and value = all values
    data_dict = list_to_nested_dict(all_values, myColumns)

    # Save to TSV if filename provided
    if tsv_filename:
        saveToTSV(data_dict, tsv_filename, myColumns)

    return data_dict


def saveToTSV(data_dict, filename, selected_columns):
    """Save the nested dictionary data to a TSV file.

    Args:
        data_dict: Nested dictionary with data
        filename: Name of the TSV file to create
        selected_columns: List of column names to include
    """
    with open(filename, "w", newline="", encoding="utf-8") as tsvfile:
        writer = csv.writer(tsvfile, delimiter="\t")

        # Write header
        writer.writerow(selected_columns)

        # Write data rows
        for key, row_dict in data_dict.items():
            row = [row_dict.get(col, "") for col in selected_columns]
            writer.writerow(row)

    log(f"Data saved to {filename}")


def readFromTSV(filename, selected_columns):
    """Read data from a TSV file and convert to nested dictionary format.

    Args:
        filename: Name of the TSV file to read
        selected_columns: List of column names expected

    Returns:
        A nested dictionary with data from the TSV file
    """
    if not os.path.exists(filename):
        log(f"Error: TSV file {filename} not found")
        return None

    data_dict = {}

    with open(filename, "r", newline="", encoding="utf-8") as tsvfile:
        reader = csv.reader(tsvfile, delimiter="\t")
        headers = next(reader)  # Read header row

        # Verify headers match expected columns
        if headers != selected_columns:
            log(f"Warning: Headers in {filename} don't match expected columns")
            log(f"Expected: {selected_columns}")
            log(f"Found: {headers}")

        for row in reader:
            if row:  # Skip empty rows
                # Create row dictionary
                row_dict = {
                    headers[i]: row[i] if i < len(row) else ""
                    for i in range(len(headers))
                }
                # Use the first column as the key
                key = row[0] if row else ""
                data_dict[key] = row_dict

    log(f"Data loaded from {filename}")
    return data_dict


def parse_period(years):
    """Parse a period string into start and end years.

    Args:
        years: A string representing a time period (e.g., "1509-1547" or "44BC")

    Returns:
        A tuple of (start_year, end_year) as integers
    """
    if "-" in years:
        start_year, end_year = years.split("-")

        # Convert start year
        if "BC" in start_year:
            start_year = -int(start_year.replace("BC", ""))
        else:
            start_year = int(start_year)

        # Convert end year
        if "BC" in end_year:
            end_year = -int(end_year.replace("BC", ""))
        else:
            if "AD" in end_year:
                end_year = int(end_year.replace("AD", ""))
            elif len(end_year) <= 2:
                # Handle short form end year like '95' in '1981-95'
                end_year = int(f"{str(start_year)[:-len(end_year)]}{end_year}")
            else:
                end_year = int(end_year)
    else:
        if "BC" in years:
            start_year = end_year = -int(years.replace("BC", ""))
        elif "AD" in years:
            start_year = end_year = int(years.replace("AD", ""))
        else:
            start_year = end_year = int(years)
    return start_year, end_year


def populateTables(myData, db_name):
    """Populate the titles, years, byPeriod, and byYear tables in the database.

    Args:
        myData: Dictionary containing the periods data
        db_name: Name of the SQLite database
    """

    def creatingTables():
        # Drop tables if they exist
        cursor.execute("DROP TABLE IF EXISTS titles;")
        cursor.execute("DROP TABLE IF EXISTS years;")
        cursor.execute("DROP TABLE IF EXISTS byPeriod;")
        cursor.execute("DROP TABLE IF EXISTS byYear;")

        # Create the tables with the same schema
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS titles (
            titleID INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT UNIQUE,
            maxCount INTEGER,
            titlePlural TEXT
        );
        """
        )

        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS years (
            yearID INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER UNIQUE
        );
        """
        )

        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS byPeriod (
            periodID INTEGER PRIMARY KEY AUTOINCREMENT,
            rulerID INTEGER,
            titleID INTEGER,
            progrTitle INTEGER,
            period TEXT,
            startYear INTEGER,
            endYear INTEGER,
            notes TEXT,
            FOREIGN KEY (rulerID) REFERENCES rulers (rulerID),
            FOREIGN KEY (titleID) REFERENCES titles (titleID)
        );
        """
        )

        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS byYear (
            yearID INTEGER,
            periodID INTEGER,
            FOREIGN KEY (yearID) REFERENCES years (yearID),
            FOREIGN KEY (periodID) REFERENCES byPeriod (periodID),
            PRIMARY KEY (yearID, periodID)
        );
        """
        )

    def batch_insert_titles(titles_data):
        # Batch insert titles
        cursor.executemany(
            "INSERT OR IGNORE INTO titles (title) VALUES (?)",
            [(title,) for title in titles_data],
        )
        conn.commit()

        # Get all titleIDs in one query
        cursor.execute(
            "SELECT title, titleID FROM titles WHERE title IN ({})".format(
                ",".join("?" * len(titles_data))
            ),
            list(titles_data),
        )
        return dict(cursor.fetchall())

    def batch_insert_years(all_years):
        # Batch insert years
        cursor.executemany(
            "INSERT OR IGNORE INTO years (year) VALUES (?)",
            [(year,) for year in all_years],
        )
        conn.commit()

        # Get all yearIDs in one query
        cursor.execute(
            "SELECT year, yearID FROM years WHERE year IN ({})".format(
                ",".join("?" * len(all_years))
            ),
            list(all_years),
        )
        return dict(cursor.fetchall())

    # Connect to SQLite database
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # Enable faster inserts
    cursor.execute("PRAGMA synchronous = OFF")
    cursor.execute("PRAGMA journal_mode = MEMORY")

    # Create tables
    creatingTables()

    # Collect all unique titles and years first
    titles = set()
    all_years = set()
    periods_data = []
    titleCheck = {}

    # First pass - collect data
    for key, row in myData.items():
        title = row["Title"]
        titles.add(title)
        titleCheck[title] = titleCheck.get(title, 0) + 1

        period = row["Period"].strip()
        startYear, endYear = parse_period(period)
        all_years.update(range(startYear, endYear + 1))

        periods_data.append(
            {
                "title": title,
                "rulerID": row["RulerID"],
                "period": period,
                "startYear": startYear,
                "endYear": endYear,
                "notes": row["Notes"],
                "progrTitle": titleCheck[title],
            }
        )

    # Batch insert titles and get title mappings
    title_mappings = batch_insert_titles(titles)

    # Batch insert years and get year mappings
    year_mappings = batch_insert_years(all_years)

    # Batch insert periods
    byPeriod_data = []
    for period in periods_data:
        byPeriod_data.append(
            (
                period["rulerID"],
                title_mappings[period["title"]],
                period["progrTitle"],
                period["period"],
                period["startYear"],
                period["endYear"],
                period["notes"],
            )
        )

    cursor.executemany(
        """
        INSERT INTO byPeriod (rulerID, titleID, progrTitle, period, startYear, endYear, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
        byPeriod_data,
    )
    conn.commit()

    # Get all periodIDs
    cursor.execute("SELECT periodID, startYear, endYear FROM byPeriod")
    period_ranges = cursor.fetchall()

    # Prepare byYear data
    byYear_data = []
    for periodID, startYear, endYear in period_ranges:
        for year in range(startYear, endYear + 1):
            byYear_data.append((year_mappings[year], periodID))

    # Batch insert byYear data
    cursor.executemany(
        """
        INSERT OR IGNORE INTO byYear (yearID, periodID)
        VALUES (?, ?)
    """,
        byYear_data,
    )

    # Update maxCount for titles
    cursor.executemany(
        """
        UPDATE titles
        SET maxCount = ?
        WHERE title = ?
    """,
        [(count, title) for title, count in titleCheck.items()],
    )

    # Update plurals
    myPlurals = {
        "Pope": "Popes",
        "English Monarch": "English Monarchs",
        "US president": "US presidents",
        "British Prime Minister": "British Prime Ministers",
        "French Monarch": "French Monarchs",
        "King of the West Franks": "Kings of the West Franks",
        "King of the East Franks": "Kings of the East Franks",
        "King of the Franks": "Kings of the Franks",
        "King of France": "Kings of France",
        "French Government": "French Governments",
        "French Emperor": "French Emperors",
        "French President": "French Presidents",
        "Byzantine Emperor": "Byzantine Emperors",
        "Emperor of China": "Emperors of China",
        "Holy Roman Emperor": "Holy Roman Emperors",
        "Emperor of the Carolingian Empire": "Emperors of the Carolingian Empire",
        "Roman Emperor": "Roman Emperors",
        "Roman Emperor (East)": "Roman Emperors (East)",
        "Roman Emperor (West)": "Roman Emperors (West)",
        "Russian Emperor": "Russian Emperors",
        "Prince of Moscow": "Princes of Moscow",
        "Tsar of Russia": "Tsars of Russia",
        "Chairman of the Communist Party of the Soviet Union": "Chairmen of the Communist Party of the Soviet Union",
        "Russian President": "Russian Presidents",
        "Antipope": "Antipopes",
        "Scottish Monarch": "Scottish Monarchs",
        "Neapolitan ruler": "Neapolitan rulers",
        "Spanish Monarch": "Spanish Monarchs",
        "King of the Lombards": "Kings of the Lombards",
        "Emperor of Austria": "Emperors of Austria",
        "Roman Consul": "Roman Consuls",
        "Decemvir": "Decemviri",
        "Dictator": "Dictators",
        "King of Italy": "Kings of Italy",
        "Consular Tribune": "Consular Tribunes",
    }

    cursor.executemany(
        """
        UPDATE titles
        SET titlePlural = ?
        WHERE title = ?
    """,
        [(plural, title) for title, plural in myPlurals.items()],
    )

    conn.commit()
    conn.close()

    log("Titles and junction table successfully exported to SQLite database")


def populateRulers(myData, db_name):
    """Populate the rulers table in the database.

    Args:
        myData: Dictionary containing the rulers data
        db_name: Name of the SQLite database
    """
    # Connect to SQLite database (or create it if it doesn't exist)
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    cursor.execute("DROP TABLE IF EXISTS rulers;")
    # Create the rulers table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS rulers (
            rulerID INTEGER PRIMARY KEY,
            name TEXT,
            personal_name TEXT,
            epithet TEXT,
            wikipedia TEXT,
            notes TEXT
        )
    """
    )

    # Insert data into the rulers table
    skipped_count = 0
    for key, row in myData.items():
        # Skip rows where RulerID is empty, null, or not a valid number
        ruler_id = row.get("RulerID", "").strip()
        if not ruler_id:
            skipped_count += 1
            log(f"Skipping row with empty RulerID: {row.get('Name', 'Unknown')}")
            continue

        try:
            ruler_id_int = int(ruler_id)
        except ValueError:
            skipped_count += 1
            log(
                f"Skipping row with invalid RulerID '{ruler_id}': {row.get('Name', 'Unknown')}"
            )
            continue

        cursor.execute(
            """
            INSERT OR IGNORE INTO rulers (
                rulerID, name, personal_name, epithet, wikipedia, notes
            ) VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                ruler_id_int,
                row["Name"],
                row["Personal Name"],
                row["Epithet"],
                row["Wikipedia"],
                row["Notes"],
            ),
        )

    # Commit changes and close the connection
    conn.commit()
    conn.close()

    if skipped_count > 0:
        log(
            f"Rulers table successfully exported to SQLite database (skipped {skipped_count} rows with invalid RulerID)"
        )
    else:
        log(f"Rulers table successfully exported to SQLite database")


def main():
    """Main function to run the database creation process."""
    args = docopt(__doc__)

    # Override config values with command line arguments if provided
    keyfile = args["--keyfile"] if args["--keyfile"] else KEYFILE
    sheet_url = args["--sheet-url"] if args["--sheet-url"] else GSHEET_URL
    rulers_sheet = args["--rulers-sheet"] if args["--rulers-sheet"] else MY_RULERS_SHEET
    periods_sheet = (
        args["--periods-sheet"] if args["--periods-sheet"] else MY_PERIOD_SHEET
    )
    db_name = args["--db"] if args["--db"] else MY_DB
    from_file = not args["--no-from-file"]  # This will be True by default
    alfred_output = args["--alfred"]

    # Define TSV filenames
    rulers_tsv = "rulers_data.tsv"
    periods_tsv = "periods_data.tsv"
    allRulers = {}
    allValues = {}

    main_start_time = time()

    # Define column structures
    rulers_columns = [
        "RulerID",
        "Name",
        "Personal Name",
        "Wikipedia",
        "Epithet",
        "Notes",
    ]
    periods_columns = ["Title", "RulerID", "Period", "Notes"]

    if from_file:
        # Try to read from TSV files
        log("Reading data from local TSV files...")

        allRulers = readFromTSV(rulers_tsv, rulers_columns)
        allValues = readFromTSV(periods_tsv, periods_columns)

        # If either file doesn't exist or is empty, fall back to API
        if allRulers is None or allValues is None:
            log("TSV files not found or empty. Falling back to API calls...")
            from_file = False

    if not from_file:
        # Make API calls and save to TSV files
        if not sheet_url:
            log(
                "Error: No Google Sheet URL provided. Use --sheet-url or set GSHEET_URL in config.py"
            )
            sys.exit(1)

        if not os.path.exists(keyfile):
            log(f"Error: Keyfile {keyfile} not found")
            sys.exit(1)

        # Get rulers data
        log(f"Fetching rulers data from sheet '{rulers_sheet}'...")
        allRulers = getSheet(
            keyfile, sheet_url, rulers_sheet, rulers_columns, rulers_tsv
        )

        # Get periods data
        log(f"Fetching periods data from sheet '{periods_sheet}'...")
        allValues = getSheet(
            keyfile, sheet_url, periods_sheet, periods_columns, periods_tsv
        )

    # Create the database
    log(f"Creating database '{db_name}'...")
    start_time = time()
    populateRulers(allRulers, db_name)
    populateTables(allValues, db_name)
    db_time = time() - start_time
    log(f"Database created in {round(db_time, 3)} seconds")

    main_timeElapsed = time() - main_start_time
    log(f"Total script completed in {round(main_timeElapsed, 3)} seconds")

    # For Alfred workflow, output JSON result
    if alfred_output:
        result = {
            "items": [
                {
                    "title": "Done!",
                    "subtitle": f"WhoWasWhen database created successfully in {round(main_timeElapsed, 1)} seconds",
                    "arg": "",
                    "icon": {"path": "icons/done.png"},
                }
            ]
        }
        print(json.dumps(result))
    else:
        log("Done 👍️")

    return 0


if __name__ == "__main__":
    sys.exit(main())
