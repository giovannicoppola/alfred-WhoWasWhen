# WhoWasWhen Database Generator

This script creates a SQLite database for the WhoWasWhen workflow, which allows you to look up historical rulers by year.

## Prerequisites

- Python 3.6+
- Google API credentials (service account key file)
- A properly formatted Google Sheet with rulers and periods data

## Dependencies

Install required packages:

```bash
pip install docopt gspread oauth2client google-auth
```

## Configuration

Edit the `config.py` file to set your Google Sheet URL and other configuration options, or use command-line arguments.

## Usage

```bash
python whowaswhen.py [options]
```

### Options

- `-h --help`: Show help message and exit
- `--keyfile=<keyfile>`: Path to Google API service account key file [default: keyfile.json]
- `--sheet-url=<url>`: Google Sheet URL
- `--rulers-sheet=<name>`: Name of the sheet containing rulers data
- `--periods-sheet=<name>`: Name of the sheet containing periods data
- `--db=<dbname>`: Output SQLite database name
- `--verbose`: Show verbose output

## Google Sheet Format

### Rulers Sheet
Should contain columns:
- RulerID
- Name
- Personal Name
- Wikipedia
- Epithet
- Notes

### Periods Sheet
Should contain columns:
- Title
- RulerID
- Period (in format like "1509-1547" or "44BC")
- Notes

## Output

The script creates a SQLite database with the following tables:
- rulers
- titles
- years
- byPeriod
- byYear 