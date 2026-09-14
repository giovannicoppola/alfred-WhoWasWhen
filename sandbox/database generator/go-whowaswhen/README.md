# WhoWasWhen Database Generator (Go)

A Go implementation of the WhoWasWhen database generator that creates a SQLite database for the WhoWasWhen Alfred workflow from a public Google Sheets data source.

## Features

- **Public Google Sheets Access**: No authentication required - works with public Google Sheets
- **Identical Results**: Produces the same SQLite database structure as the Python version
- **Performance**: High-performance database generation with optimized batch operations
- **TSV Fallback**: Reads from local TSV files when available for offline usage
- **Biography Generation**: Intelligent ruler biography generation from period data
- **Database Compression**: Optional ZIP file creation for distribution
- **Alfred Integration**: Direct JSON output support for Alfred workflow

## Requirements

- Go 1.16 or later
- SQLite3 (automatically handled by Go driver)
- Internet connection for Google Sheets access

## Installation

```bash
# Clone or navigate to the project directory
cd go-whowaswhen

# Install dependencies
go mod download

# Build the application
go build -o whowaswhen
```

## Usage

### Basic Usage

```bash
# Generate database using public Google Sheets
./whowaswhen

# Generate database without using cached TSV files
./whowaswhen -no-from-file

# Generate database with custom name
./whowaswhen -db my_database.db

# Generate database with zipped version
./whowaswhen -zip

# Generate for Alfred workflow (JSON output)
./whowaswhen -alfred
```

### Command Line Options

```
-sheet-url string       Google Sheet URL (default: configured public sheet)
-rulers-sheet string    Name of the rulers sheet (default: "Rulers")
-periods-sheet string   Name of the periods sheet (default: "Periods") 
-events-sheet string    Name of the events sheet (default: "Events")
-db string             Output SQLite database name (default: from config)
-no-from-file          Force fetching from Google Sheets instead of using existing TSV files
-zip                   Create zipped database file in script directory
-alfred                Output JSON result for Alfred workflow
-help                  Show help message
```

## Data Source

The application uses a public Google Sheets document containing historical ruler data across three sheets:

- **Periods Sheet**: Contains ruler titles, periods of reign, and notes
- **Rulers Sheet**: Contains ruler names, personal information, and references
- **Events Sheet**: Contains historical events with dates and descriptions

## Database Schema

The generated SQLite database contains the following tables:

- `rulers`: Ruler information with generated biographies
- `titles`: Unique titles with occurrence counts and plurals
- `years`: Individual years covered by the dataset
- `byPeriod`: Period-based ruler data with foreign key relationships
- `byYear`: Year-based lookup table for fast queries
- `byEvents`: Historical events with date ranges

## Output Files

The application generates:

- **SQLite Database**: Main database file (`.db`) in the data folder
- **Zipped Database**: Compressed version for distribution (`.db.zip`) in script directory (only when `-zip` flag is used)
- **Database Statistics**: Formatted statistics file (`database_stats.md`) with record counts and summaries in the data folder
- **Timestamp File**: Creation timestamp (`timestamp.txt`) for tracking when the database was last updated in the data folder

**Note**: TSV files are only used for offline fallback when manually created or when using the Python version.

## Performance

Typical performance on modern hardware:
- Database generation: ~5-6 seconds
- Total records: ~3,300 rulers, ~4,200 periods, ~800 events
- Database size: ~1.4MB (compressed: ~620KB when using `-zip` flag)

## Database Statistics

The application automatically generates and displays database statistics:
- **Rulers**: Total number of historical rulers
- **Titles**: Number of unique titles/positions
- **Years**: Number of individual years covered
- **Periods**: Number of reign periods
- **Events**: Number of historical events
- **Skipped Rows**: Number of rows with missing required data

Statistics are output to STDERR during execution and saved to a formatted `database_stats.md` file in the data folder with detailed tables, file size information, summary data, and data quality metrics.

## Public Sheet Access

The application accesses public Google Sheets using CSV export URLs without requiring authentication. The sheet GIDs are configured automatically:

- Periods: GID 0
- Rulers: GID 2053495317
- Events: GID 877936494

## Development

To modify the data source or add features:

1. Update `config.go` for configuration changes
2. Modify `sheets.go` for data fetching logic
3. Edit database operations in `database.go`
4. Test with: `go test ./...`

## Comparison with Python Version

This Go implementation provides:
- ✅ Identical database output
- ✅ Same command-line interface
- ✅ Public sheet access (no credentials needed)
- ✅ Better performance for large datasets
- ✅ Single binary deployment
- ✅ Cross-platform compatibility

## License

This project maintains the same license as the original Python implementation. 