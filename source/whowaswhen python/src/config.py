"""Configuration for WhoWasWhen script.

This module contains configuration variables for the WhoWasWhen database generator.
"""
import sys
import os

# Folder for data storage
DATA_FOLDER = os.getenv('alfred_workflow_data')
if not DATA_FOLDER:
    DATA_FOLDER = ('/Users/giovanni/Library/Application Support/Alfred/Workflow Data/giovanni-whowaswhen')

if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)

# Google API credentials file
KEYFILE = "/Users/giovanni/Library/CloudStorage/GoogleDrive-giovannicoppola@gmail.com/My Drive/SyncApps/alfred-gsheets/burattinaio-3e3a8d3da3b6.json"

# Google Sheets URL
GSHEET_URL = "https://docs.google.com/spreadsheets/d/1GKI1744hxSBmB75CrIYssK6Y8-Hd48kpaggvOG1kUM8/edit#gid=0"

# Sheet names
MY_PERIOD_SHEET = 'Periods'
MY_RULERS_SHEET = 'Rulers'

# Output SQLite database name
MY_DB = f"{DATA_FOLDER}/whoWasWho.db"

# Other data file paths
MYYEARS = f"{DATA_FOLDER}/rulersYears"
MYRULERS = f"{DATA_FOLDER}/rulersInfo"
MYRULERSLISTS = f"{DATA_FOLDER}/rulersLists"
MYICONDICT = f"{DATA_FOLDER}/iconDict"

# Source types dictionary
sourceDict = {
    "regularQuery": "regular",
    "startPeriod": "start",
    "endPeriod": "end",
    "rulerQuery": "ruler"
}

# Logging function
def log(message, *args):
    """Print a log message to stderr."""
    if args:
        message = message % args
    print(message, file=sys.stderr)

