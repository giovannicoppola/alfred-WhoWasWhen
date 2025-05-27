# WhoWasWhen Go - Technical Documentation

## Architecture

The WhoWasWhen workflow consists of several key components:

1. **Database Generator** (`whowaswhen.py`): Python script that fetches data from Google Sheets and creates a SQLite database.
2. **Query Engine** (`ruler-query-go`): Go executable that performs searches against the SQLite database.
3. **Configuration** (`config.py`): Contains paths, credentials, and settings.
4. **Alfred Workflow** (`info.plist`): Defines workflow triggers and behavior in Alfred.

## Database Schema

The SQLite database consists of several tables:

1. **rulers**: Contains ruler information
   - `rulerID` (INTEGER PRIMARY KEY)
   - `name` (TEXT)
   - `personal_name` (TEXT)
   - `epithet` (TEXT)
   - `wikipedia` (TEXT)
   - `notes` (TEXT)

2. **titles**: Contains title information
   - `titleID` (INTEGER PRIMARY KEY AUTOINCREMENT)
   - `title` (TEXT UNIQUE)
   - `maxCount` (INTEGER)
   - `titlePlural` (TEXT)

3. **years**: Contains all relevant years
   - `yearID` (INTEGER PRIMARY KEY AUTOINCREMENT)
   - `year` (INTEGER UNIQUE)

4. **byPeriod**: Maps rulers to titles and periods
   - `periodID` (INTEGER PRIMARY KEY AUTOINCREMENT)
   - `rulerID` (INTEGER)
   - `titleID` (INTEGER)
   - `progrTitle` (INTEGER)
   - `period` (TEXT)
   - `startYear` (INTEGER)
   - `endYear` (INTEGER)
   - `notes` (TEXT)

5. **byYear**: Junction table linking years to periods
   - `yearID` (INTEGER)
   - `periodID` (INTEGER)

## Query Flow

When a user enters a query:

1. Alfred passes the query to `ruler-query-go`
2. The Go executable parses the query to identify:
   - Number/year terms (using regex pattern matching)
   - Text search terms
3. Based on the query type, it executes either:
   - Year-based search (if it contains a year)
   - Ruler name search (default)
4. Results are formatted as JSON for Alfred
5. Alfred renders the results using the workflow's predefined item template

## Performance Considerations

The Go implementation offers significant performance improvements:

1. Compiled binary execution vs Python interpreter
2. Efficient memory management
3. Fast regex pattern matching
4. Optimized database query execution

## Dependencies

- **Go Dependencies**:
  - github.com/mattn/go-sqlite3 - SQLite3 database driver for Go

- **Python Dependencies**:
  - docopt - Command line argument parsing
  - gspread - Google Spreadsheets API client
  - oauth2client - Google OAuth 2.0 client
  - google-auth - Google authentication library

## Customization Possibilities

Advanced users can extend this workflow by:

1. Adding new search types in the Go code
2. Modifying the database schema to include additional information
3. Implementing additional Alfred actions using modifiers
4. Adding visualization features for ruler timelines

## Filesystem Layout

```
WhoWasWhen-Go/
├── ruler-query-go          # Go executable for queries
├── whowaswhen.py           # Python script for database generation
├── config.py               # Configuration file
├── info.plist              # Alfred workflow configuration
└── icons/                  # Icon files for the workflow
    ├── crown.png           # Default ruler icon
    ├── hopeless.png        # No results icon
    └── [title].png         # Title-specific icons
```

## Environmental Variables

The workflow uses these environment variables:

- `alfred_workflow_data`: Path to Alfred's workflow data directory
- `mySource`: Source context for queries ("ruler" for lineage browsing)
- `myRulerID`: Current ruler ID when browsing lineage
- `myTitle`: Current title when browsing lineage
- `mytitleProg`: Current progression number when browsing lineage 