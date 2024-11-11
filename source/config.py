
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

MYFILE = 'rulers.json'
KEYFILE = "/Users/giovanni/Library/CloudStorage/GoogleDrive-giovannicoppola@gmail.com/My Drive/SyncApps/alfred-gsheets/burattinaio-3e3a8d3da3b6.json"
GSHEET_URL = "https://docs.google.com/spreadsheets/d/1GKI1744hxSBmB75CrIYssK6Y8-Hd48kpaggvOG1kUM8/edit#gid=0"
MY_PERIOD_SHEET = 'Sheet1'

