package main

import (
	"archive/zip"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"time"

	"database/sql"

	_ "github.com/mattn/go-sqlite3"
)

// Configuration structure to hold all config values
type Config struct {
	DataFolder    string
	GSheetURL     string
	PeriodSheet   string
	RulersSheet   string
	DatabaseName  string
	SpreadsheetID string
}

// Command line arguments
var (
	sheetURL     = flag.String("sheet-url", "", "Google Sheet URL")
	rulersSheet  = flag.String("rulers-sheet", "", "Name of the sheet containing rulers data")
	periodsSheet = flag.String("periods-sheet", "", "Name of the sheet containing periods data")
	eventsSheet  = flag.String("events-sheet", "Events", "Name of the sheet containing events data")
	dbName       = flag.String("db", "", "Output SQLite database name")
	noFromFile   = flag.Bool("no-from-file", false, "Force fetching from Google Sheets instead of using existing TSV files")
	createZip    = flag.Bool("zip", false, "Create zipped database file in script directory")
	alfredOutput = flag.Bool("alfred", false, "Output JSON result for Alfred workflow")
	showHelp     = flag.Bool("help", false, "Show help message")
)

// Usage information
const usage = `WhoWasWhen Database Generator

This application creates a SQLite database for the WhoWasWhen workflow, starting from a public Google spreadsheet.

Usage:
  whowaswhen [options]

Options:
  -sheet-url string     Google Sheet URL
  -rulers-sheet string  Name of the sheet containing rulers data
  -periods-sheet string Name of the sheet containing periods data
  -events-sheet string  Name of the sheet containing events data (default "Events")
  -db string           Output SQLite database name
  -no-from-file        Force fetching from Google Sheets instead of using existing TSV files
  -zip                 Create zipped database file in script directory
  -alfred              Output JSON result for Alfred workflow
  -help                Show this help message
`

// Global variable to track skipped rows
var skippedRows int

func main() {
	flag.Parse()

	if *showHelp {
		fmt.Print(usage)
		os.Exit(0)
	}

	// Initialize configuration with defaults
	config := getConfig()

	// Override with command line arguments if provided
	if *sheetURL != "" {
		config.GSheetURL = *sheetURL
	}
	if *rulersSheet != "" {
		config.RulersSheet = *rulersSheet
	}
	if *periodsSheet != "" {
		config.PeriodSheet = *periodsSheet
	}
	if *dbName != "" {
		config.DatabaseName = *dbName
	}

	fromFile := !*noFromFile

	// Define TSV filenames for local file reading
	rulersCSV := "rulers_data.tsv"
	periodsCSV := "periods_data.tsv"
	eventsCSV := "events_data.tsv"

	logMessage("Starting WhoWasWhen database generation...")
	mainStartTime := time.Now()

	// Define column structures
	// The sheet header is "Personal Name or House" (not "Personal Name"); the
	// mismatch silently imported an empty column, so pope personal names and
	// monarch houses never made it into the database.
	rulersColumns := []string{"RulerID", "Name", "Personal Name or House", "Wikipedia", "Epithet", "Notes", "Born", "Died"}
	periodsColumns := []string{"Title", "RulerID", "Period", "Notes"}
	eventsColumns := []string{"Event Name", "Numerical year", "Notes", "Wikipedia", "Month", "Day"}

	var allRulers, allPeriods, allEvents [][]string
	var err error

	if fromFile {
		// Try to read from local TSV files quietly (they may not exist)
		allRulers, err = readFromTSV(rulersCSV, rulersColumns)
		if err != nil {
			fromFile = false
		}

		if fromFile {
			allPeriods, err = readFromTSV(periodsCSV, periodsColumns)
			if err != nil {
				fromFile = false
			}
		}

		if fromFile {
			allEvents, err = readFromTSV(eventsCSV, eventsColumns)
			if err != nil {
				fromFile = false
			}
		}

		if fromFile {
			logMessage("Using data from local TSV files")
		}
	}

	if !fromFile {
		logMessage("Fetching data from public Google Sheets...")

		if config.GSheetURL == "" {
			logMessage("Error: No Google Sheet URL provided. Use -sheet-url or set in config")
			os.Exit(1)
		}

		// Get data from public Google Sheets
		allRulers, err = getSheet(config.SpreadsheetID, config.RulersSheet, rulersColumns)
		if err != nil {
			logMessage("Error fetching rulers data: %v", err)
			os.Exit(1)
		}

		allPeriods, err = getSheet(config.SpreadsheetID, config.PeriodSheet, periodsColumns)
		if err != nil {
			logMessage("Error fetching periods data: %v", err)
			os.Exit(1)
		}

		allEvents, err = getSheet(config.SpreadsheetID, *eventsSheet, eventsColumns)
		if err != nil {
			logMessage("Error fetching events data: %v", err)
			os.Exit(1)
		}
	}

	// Create the database
	logMessage("Creating database '%s'...", config.DatabaseName)
	startTime := time.Now()

	err = populateRulers(allRulers, config.DatabaseName)
	if err != nil {
		logMessage("Error populating rulers: %v", err)
		os.Exit(1)
	}

	err = populateTables(allPeriods, config.DatabaseName)
	if err != nil {
		logMessage("Error populating tables: %v", err)
		os.Exit(1)
	}

	err = populateEvents(allEvents, config.DatabaseName)
	if err != nil {
		logMessage("Error populating events: %v", err)
		os.Exit(1)
	}

	err = generateBiographies(allPeriods, config.DatabaseName)
	if err != nil {
		logMessage("Error generating biographies: %v", err)
		os.Exit(1)
	}

	dbTime := time.Since(startTime)
	logMessage("Database created in %.3f seconds", dbTime.Seconds())

	// Collect and output database statistics
	err = outputDatabaseStats(config.DatabaseName, config.DataFolder, skippedRows)
	if err != nil {
		logMessage("Error collecting database stats: %v", err)
		// Don't exit, just continue
	}

	// Create timestamp file
	err = createTimestampFile(config.DataFolder)
	if err != nil {
		logMessage("Error creating timestamp file: %v", err)
		// Don't exit, just continue
	}

	// Create zipped version of the database if requested
	if *createZip {
		err = createZippedDatabaseInScriptDir(config.DatabaseName)
		if err != nil {
			logMessage("Error creating zipped database: %v", err)
			os.Exit(1)
		}
	}

	mainTimeElapsed := time.Since(mainStartTime)
	logMessage("Total script completed in %.3f seconds", mainTimeElapsed.Seconds())

	// For Alfred workflow, output JSON result
	if *alfredOutput {
		result := map[string]interface{}{
			"items": []map[string]interface{}{
				{
					"title":    "Done!",
					"subtitle": fmt.Sprintf("WhoWasWhen database created successfully in %.1f seconds", mainTimeElapsed.Seconds()),
					"arg":      "",
					"icon":     map[string]string{"path": "icons/done.png"},
				},
			},
		}
		jsonOutput, _ := json.Marshal(result)
		fmt.Println(string(jsonOutput))
	} else {
		logMessage("Done 👍️")
	}
}

// logMessage prints a message to stderr (similar to Python's log function)
func logMessage(format string, args ...interface{}) {
	fmt.Fprintf(os.Stderr, format+"\n", args...)
}

// outputDatabaseStats collects database statistics and outputs them to STDERR and a markdown file
func outputDatabaseStats(dbPath, dataFolder string, skippedRowCount int) error {
	// Open database connection
	db, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		return fmt.Errorf("failed to open database: %w", err)
	}
	defer db.Close()

	// Collect statistics
	stats := make(map[string]int)

	// Query each table for record counts
	tables := []string{"rulers", "titles", "years", "byPeriod", "byEvents"}
	for _, table := range tables {
		var count int
		err := db.QueryRow(fmt.Sprintf("SELECT COUNT(*) FROM %s", table)).Scan(&count)
		if err != nil {
			return fmt.Errorf("failed to query %s table: %w", table, err)
		}
		stats[table] = count
	}

	// Get database file info
	dbInfo, err := os.Stat(dbPath)
	var dbSize int64 = 0
	if err == nil {
		dbSize = dbInfo.Size()
	}

	// Format statistics for STDERR (plain text)
	statsText := fmt.Sprintf("Database Statistics:\n")
	statsText += fmt.Sprintf("  Rulers: %d\n", stats["rulers"])
	statsText += fmt.Sprintf("  Titles: %d\n", stats["titles"])
	statsText += fmt.Sprintf("  Years: %d\n", stats["years"])
	statsText += fmt.Sprintf("  Periods: %d\n", stats["byPeriod"])
	statsText += fmt.Sprintf("  Events: %d\n", stats["byEvents"])
	if skippedRowCount > 0 {
		statsText += fmt.Sprintf("  Skipped rows: %d\n", skippedRowCount)
	}

	// Output to STDERR
	logMessage(statsText)

	// Create formatted Markdown content
	timestamp := time.Now().Format("2006-01-02 15:04:05")
	markdownContent := fmt.Sprintf("# WhoWasWhen Database Statistics\n\n")
	markdownContent += fmt.Sprintf("**Generated:** %s\n\n", timestamp)
	markdownContent += fmt.Sprintf("**Database File:** `%s`\n", filepath.Base(dbPath))
	markdownContent += fmt.Sprintf("**Database Size:** %.2f MB\n\n", float64(dbSize)/(1024*1024))

	markdownContent += "## Record Counts\n\n"
	markdownContent += "| Table | Records | Description |\n"
	markdownContent += "|-------|---------|-------------|\n"
	markdownContent += fmt.Sprintf("| **Rulers** | %s | Historical rulers and leaders |\n", formatNumber(stats["rulers"]))
	markdownContent += fmt.Sprintf("| **Titles** | %s | Unique titles and positions |\n", formatNumber(stats["titles"]))
	markdownContent += fmt.Sprintf("| **Years** | %s | Individual years covered |\n", formatNumber(stats["years"]))
	markdownContent += fmt.Sprintf("| **Periods** | %s | Reign periods and terms |\n", formatNumber(stats["byPeriod"]))
	markdownContent += fmt.Sprintf("| **Events** | %s | Historical events |\n", formatNumber(stats["byEvents"]))

	if skippedRowCount > 0 {
		markdownContent += "\n## Data Processing\n\n"
		markdownContent += "| Issue | Count | Description |\n"
		markdownContent += "|-------|-------|-------------|\n"
		markdownContent += fmt.Sprintf("| **Skipped Rows** | %s | Rows with missing required data |\n", formatNumber(skippedRowCount))
	}

	markdownContent += "\n## Summary\n\n"
	totalRecords := stats["rulers"] + stats["titles"] + stats["years"] + stats["byPeriod"] + stats["byEvents"]
	markdownContent += fmt.Sprintf("- **Total Records:** %s\n", formatNumber(totalRecords))
	markdownContent += fmt.Sprintf("- **Year Range:** Covers %s unique years\n", formatNumber(stats["years"]))
	markdownContent += fmt.Sprintf("- **Coverage:** %s rulers across %s different titles\n", formatNumber(stats["rulers"]), formatNumber(stats["titles"]))
	if skippedRowCount > 0 {
		markdownContent += fmt.Sprintf("- **Data Quality:** %s rows skipped due to missing data\n", formatNumber(skippedRowCount))
	}

	markdownContent += "\n---\n"
	markdownContent += "*Generated by WhoWasWhen Database Generator*\n"

	// Save to markdown file in data folder
	statsFile := filepath.Join(dataFolder, "database_stats.md")
	err = os.WriteFile(statsFile, []byte(markdownContent), 0644)
	if err != nil {
		return fmt.Errorf("failed to write stats file: %w", err)
	}

	logMessage("Database statistics saved to %s", statsFile)
	return nil
}

// formatNumber adds commas to large numbers for better readability
func formatNumber(n int) string {
	str := fmt.Sprintf("%d", n)
	if len(str) <= 3 {
		return str
	}

	var result string
	for i, digit := range str {
		if i > 0 && (len(str)-i)%3 == 0 {
			result += ","
		}
		result += string(digit)
	}
	return result
}

// createTimestampFile creates a timestamp file in the data folder
func createTimestampFile(dataFolder string) error {
	timestamp := time.Now().Format("2006-01-02 15:04:05")
	timestampFile := filepath.Join(dataFolder, "timestamp.txt")

	err := os.WriteFile(timestampFile, []byte(timestamp), 0644)
	if err != nil {
		return fmt.Errorf("failed to write timestamp file: %w", err)
	}

	logMessage("Timestamp file created: %s", timestampFile)
	return nil
}

// createZippedDatabaseInScriptDir creates a zipped version of the database in the script directory
func createZippedDatabaseInScriptDir(dbPath string) error {
	// Get script directory
	scriptDir, err := os.Getwd()
	if err != nil {
		return fmt.Errorf("failed to get current directory: %w", err)
	}

	// Create zip filename in script directory
	dbBaseName := filepath.Base(dbPath)
	zipFileName := strings.TrimSuffix(dbBaseName, filepath.Ext(dbBaseName)) + ".zip"
	zipPath := filepath.Join(scriptDir, zipFileName)

	logMessage("Creating zipped database '%s'...", zipPath)
	zipStartTime := time.Now()

	zipFile, err := os.Create(zipPath)
	if err != nil {
		return fmt.Errorf("failed to create zip file: %w", err)
	}
	defer zipFile.Close()

	zipWriter := zip.NewWriter(zipFile)
	defer zipWriter.Close()

	// Open the database file
	dbFile, err := os.Open(dbPath)
	if err != nil {
		return fmt.Errorf("failed to open database file: %w", err)
	}
	defer dbFile.Close()

	// Create file in zip with just the database filename (not full path)
	writer, err := zipWriter.Create(dbBaseName)
	if err != nil {
		return fmt.Errorf("failed to create file in zip: %w", err)
	}

	// Copy database file to zip
	_, err = io.Copy(writer, dbFile)
	if err != nil {
		return fmt.Errorf("failed to write database to zip: %w", err)
	}

	zipTime := time.Since(zipStartTime)
	logMessage("Zipped database created in %.3f seconds", zipTime.Seconds())

	return nil
}
