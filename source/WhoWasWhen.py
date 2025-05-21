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
  --alfred                 Output JSON result for Alfred workflow.
  --verbose                Show verbose output.

"""
import pickle
import json
import sqlite3
import gspread
import gspread.exceptions
from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2 import service_account
from time import time
from docopt import docopt
import sys
import os

# Try to import from config, but provide defaults if not available
try:
    from config import KEYFILE, log, GSHEET_URL, MY_PERIOD_SHEET, MY_RULERS_SHEET, MY_DB
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

def getSheet(keyfile, mysheetURL, myPeriodSheet, myColumns):
    """Retrieve tables from a Google Sheet and convert them into a nested dictionary.
    
    Args:
        keyfile: Path to the Google API service account key file
        mysheetURL: URL of the Google Sheet
        myPeriodSheet: Name of the sheet to retrieve
        myColumns: List of column names to include
        
    Returns:
        A nested dictionary with data from the sheet
    """
    def list_to_nested_dict(all_values, selected_columns):
        headers = all_values[0]  # The first row is the header
        indices = [headers.index(col) for col in selected_columns if col in headers]  # Indices of selected columns
        data_dict = {}
        
        for row in all_values[1:]:
            # Create a dictionary for each row with selected columns only
            row_dict = {headers[i]: row[i] for i in indices}
            # Use the first column as the key for the main dictionary
            data_dict[row[0]] = row_dict
        
        return data_dict

    scopes = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
    ]
    credentials = ServiceAccountCredentials.from_json_keyfile_name(keyfile, scopes) 
    file = gspread.authorize(credentials) # authenticate the JSON key with gspread
    
    # opening the file
    try:
        sheet = file.open_by_url(mysheetURL)
    
    except gspread.exceptions.NoValidUrlKeyFound as e:
        log("URL not valid")
        raise
    except ValueError as e:
        log("ValueError")
        raise
    except IOError as e:
    # Handle input/output errors
        log("IOError")
        raise
    except Exception as e:
    # Catch any remaining errors
        log("Exception")
        raise

    
    # fetching the worksheet
    try:
        worksheet = sheet.worksheet(myPeriodSheet) 
    
    except gspread.exceptions.WorksheetNotFound as e:
        log("Sheet Not Found")
        raise

    # Get all values from the worksheet
    all_values = worksheet.get_all_values()

    # converting into a dictionary with key = counter and value = all values
    data_dict = list_to_nested_dict(all_values, myColumns)
    
    return data_dict

def parse_period(years):
    """Parse a period string into start and end years.
    
    Args:
        years: A string representing a time period (e.g., "1509-1547" or "44BC")
        
    Returns:
        A tuple of (start_year, end_year) as integers
    """
    if '-' in years:
        start_year, end_year = years.split('-')
        
        # Convert start year
        if 'BC' in start_year:
            start_year = -int(start_year.replace('BC', ''))
        else:
            start_year = int(start_year)

        # Convert end year
        if 'BC' in end_year:
            end_year = -int(end_year.replace('BC', ''))
        else:
            if 'AD' in end_year:
                end_year = int(end_year.replace('AD', ''))
            elif len(end_year) <= 2:
                # Handle short form end year like '95' in '1981-95'
                end_year = int(f"{str(start_year)[:-len(end_year)]}{end_year}")
            else:
                end_year = int(end_year)
    else:
        if 'BC' in years:
            start_year = end_year = -int(years.replace('BC', ''))
        elif 'AD' in years:
            start_year = end_year = int(years.replace('AD', ''))
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
        cursor.execute('DROP TABLE IF EXISTS titles;')
        cursor.execute('DROP TABLE IF EXISTS years;')
        cursor.execute('DROP TABLE IF EXISTS byPeriod;')
        cursor.execute('DROP TABLE IF EXISTS byYear;')


        # Create the tables
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS titles (
            titleID INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT UNIQUE,
            maxCount INTEGER,
            titlePlural TEXT
        );
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS years (
            yearID INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER UNIQUE
        );
        ''')


        cursor.execute('''
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
        ''')


        cursor.execute('''
        CREATE TABLE IF NOT EXISTS byYear (
            yearID INTEGER,
            periodID INTEGER,
                FOREIGN KEY (yearID) REFERENCES years (yearID),
                FOREIGN KEY (periodID) REFERENCES byPeriod (periodID),
                PRIMARY KEY (yearID, periodID)
        );
        ''')
    def fetchTitleID(title):
        # Function to get the titleID for a given title
        cursor.execute('''
            SELECT titleID FROM titles WHERE title = ?
        ''', (title,))
        title_id = cursor.fetchone()
        return title_id[0] if title_id else None

    def insert_title(title):
    # Function to insert a unique title and get its titleID
        cursor.execute('''
            INSERT OR IGNORE INTO titles (title)
            VALUES (?)
            ''', (title,))
        conn.commit()
        

        # Retrieve the titleID for the given title
        title_id = fetchTitleID(title)
        
        return title_id if title_id else None

    def populate_byPeriod (rulerID, titleID, progrTitle, period, startYear, endYear,notes):

        # Insert each period in the byPeriod table and get the periodID
        cursor.execute('''
            INSERT INTO byPeriod (rulerID, titleID, progrTitle, period, startYear, endYear,notes)
            VALUES (?, ?, ?, ?, ?, ?,?)
            ''', (rulerID, titleID, progrTitle, period, startYear, endYear,notes))
        conn.commit()    
        return cursor.lastrowid

    def insert_year(year):
    # Function to insert unique year and get its yearID
        cursor.execute('''
        INSERT OR IGNORE INTO years (year)
        VALUES (?)
        ''', (year,))
        conn.commit()
        # Retrieve the yearID for the given year
        
        cursor.execute('''
            SELECT yearID FROM years WHERE year = ?
        ''', (year,))
        year_id = cursor.fetchone()
        
        # Return the yearID
        return year_id[0] if year_id else None

    def populateByYear (periodID, startYear, endYear):
        # Function to insert ruler title relationships for each year

        for year in range(startYear, endYear + 1):

            # Insert each year into the years table and get the yearID
            yearID = insert_year(year)


            # Insert periodID and yearID into the byYear table
            cursor.execute('''
            INSERT OR IGNORE INTO byYear (periodID, yearID)
            VALUES (?, ?)
            ''', (periodID, yearID))
        conn.commit()

    # Connect to SQLite database
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    
    # Create tables
    creatingTables()
    
    # processing the dictionary
    titleCheck = {}
    for key,row in myData.items():
        title = row['Title']
        rulerID = row['RulerID']
        period = row['Period'].strip()  # e.g. "1509-1547"
        notes = row['Notes']
        startYear, endYear = parse_period(period)

        if title not in titleCheck:
            titleCheck[title] = 1
            titleID = insert_title(title)
            # Insert the title into the titles table and get its titleID
        else:
            titleCheck[title] += 1
            titleID = fetchTitleID(title)
            
        
        periodID = populate_byPeriod(rulerID, titleID, titleCheck[title], period, startYear, endYear, notes)        
        
        # Insert year and period relationships into the byYear table
        populateByYear (periodID, startYear, endYear)
        
    for myTitle in titleCheck:
        cursor.execute('''
            UPDATE titles
            SET maxCount = ?
            WHERE title = ?
        ''', (titleCheck[myTitle], myTitle))
        conn.commit()


    # adding plurals
    myPlurals = {'Pope': 'Popes', 
                 'English Monarch': 'English Monarchs', 
                 'US president': 'US presidents', 
                 'British Prime Minister': 'British Prime Ministers', 
                 'French Monarch': 'French Monarchs', 
                 'King of the West Franks': 'Kings of the West Franks', 
                 'King of the East Franks': 'Kings of the East Franks', 
                 'King of the Franks': 'Kings of the Franks', 
                 'King of France': 'Kings of France', 
                 'French Government': 'French Governments', 
                 'French Emperor': 'French Emperors', 
                 'French President': 'French Presidents', 
                 'Byzantine Emperor': 'Byzantine Emperors', 
                 'Emperor of China': 'Emperors of China', 
                 'Holy Roman Emperor': 'Holy Roman Emperors', 
                 'Emperor of the Carolingian Empire': 'Emperors of the Carolingian Empire', 
                 'Roman Emperor': 'Roman Emperors', 
                 'Roman Emperor (East)': 'Roman Emperors (East)', 
                 'Roman Emperor (West)': 'Roman Emperors (West)', 
                 'Russian Emperor': 'Russian Emperors', 
                 'Prince of Moscow': 'Princes of Moscow', 
                 'Tsar of Russia': 'Tsars of Russia', 
                 'Chairman of the Communist Party of the Soviet Union': 'Chairmen of the Communist Party of the Soviet Union', 
                 'Russian President': 'Russian Presidents',
                 'Antipope': 'Antipopes',
                 'Scottish Monarch': 'Scottish Monarchs',
                 'Neapolitan ruler': 'Neapolitan rulers',
                 'Spanish Monarch': 'Spanish Monarchs'}
    
    for myTitle in myPlurals:
        cursor.execute('''
            UPDATE titles
            SET titlePlural = ?
            WHERE title = ?
        ''', (myPlurals[myTitle], myTitle))
    conn.commit()

    log("Titles and junction table successfully exported to SQLite database")
    
    # Close the connection
    conn.close()

def populateRulers(myData, db_name):
    """Populate the rulers table in the database.
    
    Args:
        myData: Dictionary containing the rulers data
        db_name: Name of the SQLite database
    """
    # Connect to SQLite database (or create it if it doesn't exist)
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    
    cursor.execute('DROP TABLE IF EXISTS rulers;')
    # Create the rulers table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rulers (
            rulerID INTEGER PRIMARY KEY,
            name TEXT,
            personal_name TEXT,
            epithet TEXT,
            wikipedia TEXT,
            notes TEXT
        )
    """)

    # Insert data into the rulers table
    for key, row in myData.items():
        cursor.execute("""
            INSERT OR IGNORE INTO rulers (
                rulerID, name, personal_name, epithet, wikipedia, notes
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            int(row['RulerID']),
            row['Name'],
            row['Personal Name'],
            row['Epithet'],
            row['Wikipedia'],
            row['Notes']
        ))

    # Commit changes and close the connection
    conn.commit()
    conn.close()

    log(f"Rulers table successfully exported to SQLite database")

def main():
    """Main function to run the database creation process."""
    args = docopt(__doc__)
    
    # Override config values with command line arguments if provided
    keyfile = args['--keyfile'] if args['--keyfile'] else KEYFILE
    sheet_url = args['--sheet-url'] if args['--sheet-url'] else GSHEET_URL
    rulers_sheet = args['--rulers-sheet'] if args['--rulers-sheet'] else MY_RULERS_SHEET
    periods_sheet = args['--periods-sheet'] if args['--periods-sheet'] else MY_PERIOD_SHEET
    db_name = args['--db'] if args['--db'] else MY_DB
    alfred_output = args['--alfred']
    verbose = args['--verbose']
    
    if not sheet_url:
        log("Error: No Google Sheet URL provided. Use --sheet-url or set GSHEET_URL in config.py")
        sys.exit(1)
    
    if not os.path.exists(keyfile):
        log(f"Error: Keyfile {keyfile} not found")
        sys.exit(1)
        
    main_start_time = time()
    
    # Get rulers data
    log(f"Fetching rulers data from sheet '{rulers_sheet}'...")
    allRulers = getSheet(
        keyfile, 
        sheet_url, 
        rulers_sheet, 
        ["RulerID", "Name", "Personal Name", "Wikipedia", "Epithet", "Personal Name", "Notes"]
    )
    
    # Get periods data
    log(f"Fetching periods data from sheet '{periods_sheet}'...")
    selected_columns = ["Title", "RulerID", "Period", "Notes"]
    allValues = getSheet(keyfile, sheet_url, periods_sheet, selected_columns)
    
    # Create the database
    log(f"Creating database '{db_name}'...")
    populateRulers(allRulers, db_name)
    populateTables(allValues, db_name)
    
    main_timeElapsed = time() - main_start_time
    log(f"Script completed in {round(main_timeElapsed, 3)} seconds")
    
    # For Alfred workflow, output JSON result
    if alfred_output:
        result = {"items": [{
            "title": "Done!" ,
            "subtitle": f"WhoWasWhen database created successfully in {round(main_timeElapsed, 1)} seconds",
            "arg": "",
            "icon": {
                "path": "icons/done.png"
            }
        }]}
        print(json.dumps(result))
    else:
        log("Done 👍️")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())