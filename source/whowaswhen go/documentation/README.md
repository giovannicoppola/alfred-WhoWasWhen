# WhoWasWhen Go Edition

This Alfred workflow allows you to look up historical rulers by year or name. This version uses Go for improved performance.

## Features

- Query rulers by name (e.g. "Henry VIII", "Churchill")
- Query rulers by year (e.g. "1776", "44BC")
- View ruler details including reign periods
- Open Wikipedia pages for rulers
- Show lineage/succession for rulers
- Fast and efficient Go implementation

## Installation

1. Import this workflow into Alfred (double-click the .alfredworkflow file)
2. Use the keyword `wwho-go` to start a search

## Requirements

- Alfred 4 or later with Powerpack license
- macOS with SQLite installed (comes with macOS by default)
- Internet connection (for initial database setup and Wikipedia links)

## Initial Setup

On first use, the workflow will generate the rulers database from the configured Google Sheet. You can force a database refresh using the keyword `WhoWasWhen::refresh`.

## Usage Tips

- Use `wwho-go` followed by a name to search for rulers by name
  - Example: `wwho-go henry viii`
  - Example: `wwho-go napoleon`

- Use `wwho-go` followed by a year to see rulers from that time
  - Example: `wwho-go 1776`
  - Example: `wwho-go 44BC`

- Use `wwho-go` with multiple terms to filter by year and name
  - Example: `wwho-go 1500 king`

- Use keyboard modifiers with search results:
  - `⌘ CMD` + `Enter` - Go to the ruler's end year
  - `⌃ CTRL` + `Enter` - Go to the ruler's start year
  - `⌥ ALT` + `Enter` - Show all rulers with the same title
  - `⇧ SHIFT` + `Enter` - Copy the ruler's period to clipboard

## About This Workflow

This workflow was created by Giovanni and uses a Go implementation for improved performance. The database is built using data from a Google Spreadsheet.

## Technical Details

- Built with Go for excellent performance
- Uses SQLite for data storage
- Database is stored in Alfred's workflow data directory
- Regular expressions used for flexible search queries

## Customization

If you want to use your own data source, edit the `config.py` file to point to your Google Sheet.

## Support

For issues or feature requests, please contact the developer through GitHub. 