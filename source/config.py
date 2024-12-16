
import os
import sys


def log(s, *args):
    if args:
        s = s % args
    print(s, file=sys.stderr)

sourceDict = {
    "regularQuery": "regular",
    "startPeriod": "start",
    "endPeriod": "end",
    "rulerQuery": "ruler"

}

DATA_FOLDER = os.getenv('alfred_workflow_data')
DATA_FOLDER = ('/Users/giovanni/Library/Application Support/Alfred/Workflow Data/giovanni-whowaswhen')

if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)

MY_DB = f"{DATA_FOLDER}/whoWasWho.db"
MYYEARS = f"{DATA_FOLDER}/rulersYears"
MYRULERS = f"{DATA_FOLDER}/rulersInfo"
MYRULERSLISTS = f"{DATA_FOLDER}/rulersLists"
MYICONDICT = f"{DATA_FOLDER}/iconDict"

KEYFILE = "/Users/giovanni/Library/CloudStorage/GoogleDrive-giovannicoppola@gmail.com/My Drive/SyncApps/alfred-gsheets/burattinaio-3e3a8d3da3b6.json"
GSHEET_URL = "https://docs.google.com/spreadsheets/d/1GKI1744hxSBmB75CrIYssK6Y8-Hd48kpaggvOG1kUM8/edit#gid=0"
MY_PERIOD_SHEET = 'Periods'
MY_RULERS_SHEET = 'Rulers'

