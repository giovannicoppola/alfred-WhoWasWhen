# TSV File Feature for WhoWasWhen Database Generator

## Overview

The WhoWasWhen script has been enhanced with the ability to save Google Sheets data to local TSV (Tab-Separated Values) files and read from them instead of making API calls every time. This provides several benefits:

- **Faster execution**: No need to wait for API calls once data is cached locally
- **Offline capability**: Can generate databases without internet connection (after initial data fetch)
- **Reduced API usage**: Fewer Google Sheets API calls
- **Data backup**: Local copies of your data for backup purposes

## New Functionality

### New Command Line Option

- `--no-from-file`: Force the script to make API calls instead of reading from local TSV files

### Default Behavior

By default, the script now:
1. **Tries to read from local TSV files first** (`rulers_data.tsv` and `periods_data.tsv`)
2. **Falls back to API calls** if TSV files don't exist or are corrupted
3. **Saves data to TSV files** whenever API calls are made

### Generated Files

When the script makes API calls, it creates two TSV files:
- `rulers_data.tsv`: Contains ruler information (RulerID, Name, Personal Name, Wikipedia, Epithet, Notes)
- `periods_data.tsv`: Contains period information (Title, RulerID, Period, Notes)

## Usage Examples

### 1. First Run (will fetch from API and save to TSV)
```bash
python3 WhoWasWhen.py
```
Since no TSV files exist yet, this will:
- Fetch data from Google Sheets API
- Save data to TSV files
- Create the SQLite database

### 2. Subsequent Runs (will use TSV files)
```bash
python3 WhoWasWhen.py
```
This will:
- Read data from existing TSV files (much faster)
- Create the SQLite database

### 3. Force API Update
```bash
python3 WhoWasWhen.py --no-from-file
```
This will:
- Ignore existing TSV files
- Fetch fresh data from Google Sheets API
- Update the TSV files with new data
- Create the SQLite database

### 4. Other Options Still Work
```bash
python3 WhoWasWhen.py --db custom.db --verbose
python3 WhoWasWhen.py --no-from-file --alfred
```

## Technical Details

### New Functions Added

1. **`saveToTSV(data_dict, filename, selected_columns)`**
   - Saves nested dictionary data to TSV format
   - Preserves data structure for later reading

2. **`readFromTSV(filename, selected_columns)`**
   - Reads TSV data back into the same nested dictionary format
   - Handles missing files gracefully
   - Validates column structure

### Enhanced Functions

1. **`getSheet(keyfile, mysheetURL, myPeriodSheet, myColumns, tsv_filename=None)`**
   - Enhanced version of the original function with optional TSV saving
   - When `tsv_filename` is provided, automatically saves data to TSV file
   - Maintains backward compatibility (existing calls work unchanged)

### Data Integrity

- TSV files preserve the exact same data structure as API calls
- Column validation ensures data consistency
- Automatic fallback to API if TSV files are missing or corrupted

## Benefits

1. **Performance**: Subsequent runs are much faster (no network delays)
2. **Reliability**: Less dependent on network connectivity and API availability
3. **Cost**: Reduced API usage if you have quota limits
4. **Backup**: Local data copies for safety
5. **Development**: Easier testing without repeatedly hitting the API

## Migration

Existing usage remains unchanged. The script is fully backward compatible:
- Existing command line options work the same way
- No changes needed to existing workflows
- TSV functionality is transparent and automatic

## File Management

- TSV files are created in the same directory as the script
- Files are automatically updated when using `--no-from-file`
- Safe to delete TSV files if you want to force a fresh API fetch
- TSV files use UTF-8 encoding for international character support 