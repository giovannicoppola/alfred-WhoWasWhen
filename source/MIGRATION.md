# WhoWasWhen Migration Guide

This document explains the migration from the Jupyter notebook to the Python command-line script.

## What's Changed

1. The original Jupyter notebook has been converted to a standalone Python script (`whowaswhen.py`)
2. Command-line arguments have been added using docopt
3. The configuration file (`config.py`) has been updated for better organization
4. Alfred workflow compatibility has been maintained

## Using the Script

### Basic Usage

```bash
./whowaswhen.py
```

This will use the default settings from `config.py`, including your Alfred workflow data folder and Google Sheet credentials.

### Alfred Workflow Integration

To use the script directly in your Alfred workflow, add the `--alfred` flag to output JSON formatted for Alfred:

```bash
./whowaswhen.py --alfred
```

### Command-Line Options

The script supports various command-line options:

```
Options:
  -h --help                Show this help message and exit.
  --keyfile=<keyfile>      Path to Google API service account key file.
  --sheet-url=<url>        Google Sheet URL.
  --rulers-sheet=<name>    Name of the sheet containing rulers data.
  --periods-sheet=<name>   Name of the sheet containing periods data.
  --db=<dbname>            Output SQLite database name.
  --alfred                 Output JSON result for Alfred workflow.
  --verbose                Show verbose output.
```

## Database Changes

The database structure remains the same:
- `rulers`: Contains ruler information
- `titles`: Contains title information with plurals
- `byPeriod`: Maps rulers to titles and time periods
- `byYear`: Maps years to entries in the period table

## Example Usage in Alfred Workflow

In your Alfred workflow, you can update your script filter to:

```bash
/usr/bin/python3 /path/to/whowaswhen.py --alfred
```

## Further Improvements

Future improvements could include:
1. Adding a search function to the script
2. Supporting different export formats
3. Better error handling and logging 