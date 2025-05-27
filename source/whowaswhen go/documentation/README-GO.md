# WhoWasWhen Go Implementation

This is a Go implementation of the WhoWasWhen ruler-query system for Alfred.

## Prerequisites

- Go 1.18+ installed
- SQLite3 development files (needed for the `go-sqlite3` package)

## Installation

1. Install the required dependencies:

```bash
# On macOS
brew install sqlite3

# On Ubuntu/Debian
sudo apt-get install sqlite3 libsqlite3-dev

# On other systems, install SQLite3 and development files accordingly
```

2. Install Go dependencies:

```bash
go mod download
```

3. Build the executable:

```bash
go build -o ruler-query-go ruler-query.go
```

## Usage with Alfred

Update your Alfred workflow script filter to use the Go version instead of the Python version:

```bash
/path/to/ruler-query-go "$1"
```

## Features

The Go implementation offers the same functionality as the Python version:

- Query by ruler name
- Query by year or year range
- Support for Alfred workflow integration
- JSON output for Alfred
- Same UI and interaction patterns

## Performance

The Go version should offer better performance and lower memory usage compared to the Python version, especially with larger datasets.

## Configuration

The application reads its configuration from environment variables, the same as the Python version:

- `alfred_workflow_data`: The path to Alfred's workflow data directory
- `mySource`: Source type ("ruler" for showing lineage)
- `myRulerID`: ID of the current ruler
- `myTitle`: Title for lineage listing
- `mytitleProg`: Title progression number

## Troubleshooting

If you encounter any issues:

1. Check that SQLite3 and development files are installed correctly
2. Ensure the database path is accessible
3. Verify that the Go version is compatible (1.18+)
4. Make sure all environment variables are set correctly

If problems persist, you can revert to the Python version by updating the Alfred workflow script filter. 