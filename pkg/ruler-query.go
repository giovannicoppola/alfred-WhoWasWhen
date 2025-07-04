package main

import (
	"archive/zip"
	"database/sql"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"time"

	_ "github.com/mattn/go-sqlite3"
)

// Config holds configuration settings from environment
type Config struct {
	MySource    string
	MyRulerID   string
	MyTitle     string
	MyTitleProg string
	DBPath      string
	ShowEvents  bool
}

// AlfredResult represents the JSON output structure for Alfred
type AlfredResult struct {
	Items []AlfredItem `json:"items"`
}

// AlfredItem represents a single item in the Alfred results
type AlfredItem struct {
	Title     string                 `json:"title"`
	Subtitle  string                 `json:"subtitle"`
	Valid     bool                   `json:"valid"`
	Arg       string                 `json:"arg"`
	Mods      map[string]AlfredMod   `json:"mods"`
	Icon      map[string]string      `json:"icon"`
	Variables map[string]interface{} `json:"variables,omitempty"`
}

// AlfredMod represents a modifier for an Alfred item
type AlfredMod struct {
	Valid     bool              `json:"valid"`
	Arg       string            `json:"arg"`
	Subtitle  string            `json:"subtitle"`
	Variables map[string]string `json:"variables,omitempty"`
}

// Row represents a database row result
type RulerRow struct {
	RulerID            int
	Name               string
	PersonalName       sql.NullString
	Epithet            sql.NullString
	Wikipedia          sql.NullString
	Notes              sql.NullString
	Biography          sql.NullString
	PeriodID           int
	TitleID            int
	Title              string
	TitlePlural        sql.NullString
	TitleCount         int
	Period             string
	ProgrTitle         int
	StartYear          int
	EndYear            int
	Year               sql.NullInt64
	ConcatenatedTitles sql.NullString
	ConcatenatedNotes  sql.NullString
}

// EventRow represents an event database row result
type EventRow struct {
	EventID   int
	EventName string
	StartYear int
	EndYear   int
	Notes     sql.NullString
	Wikipedia sql.NullString
	Year      sql.NullInt64
}

func getConfig() Config {
	// Get Alfred workflow data path from environment or use default
	dataFolder := os.Getenv("alfred_workflow_data")
	if dataFolder == "" {
		home, err := os.UserHomeDir()
		if err != nil {
			log.Fatalf("Error getting home directory: %v", err)
		}
		dataFolder = filepath.Join(home, "Library/Application Support/Alfred/Workflow Data/giovanni-whowaswhen")
	}

	// Load configuration from environment variables
	// SHOW_EVENTS defaults to true unless explicitly set to "false" or "0" (unchecked checkbox)
	showEvents := true
	showEventsEnv := os.Getenv("SHOW_EVENTS")
	if showEventsEnv == "false" || showEventsEnv == "0" {
		showEvents = false
	}

	return Config{
		MySource:    os.Getenv("mySource"),
		MyRulerID:   os.Getenv("myRulerID"),
		MyTitle:     os.Getenv("myTitle"),
		MyTitleProg: os.Getenv("mytitleProg"),
		DBPath:      filepath.Join(dataFolder, "whoWasWhen.db"),
		ShowEvents:  showEvents,
	}
}

// Log messages to stderr
func logMsg(format string, v ...interface{}) {
	fmt.Fprintf(os.Stderr, format+"\n", v...)
}

// Format duration with appropriate units
func formatDuration(d time.Duration) string {
	if d < time.Millisecond {
		return fmt.Sprintf("%.0f μs", float64(d.Nanoseconds())/1000)
	} else if d < time.Second {
		return fmt.Sprintf("%.2f ms", float64(d.Nanoseconds())/1000000)
	} else {
		return fmt.Sprintf("%.3f s", d.Seconds())
	}
}

// formatNumber adds thousand separators to numbers
func formatNumber(n int) string {
	str := strconv.Itoa(n)
	if len(str) <= 3 {
		return str
	}

	var result []byte
	for i, char := range []byte(str) {
		if i > 0 && (len(str)-i)%3 == 0 {
			result = append(result, ',')
		}
		result = append(result, char)
	}
	return string(result)
}

// ensureDatabase checks for the presence of the workflow data folder and the SQLite database.
// If a zipped database is found in the current directory, it will be extracted and moved to the
// workflow data folder. In case the database is missing, an error is returned so that the caller
// can emit an Alfred-compatible JSON error message.
func ensureDatabase(dataFolder string) error {
	// 1) Ensure the workflow data folder exists
	if _, err := os.Stat(dataFolder); os.IsNotExist(err) {
		if err := os.MkdirAll(dataFolder, 0o755); err != nil {
			return fmt.Errorf("error creating data folder: %w", err)
		}
	}

	const zipName = "whoWasWhen.db.zip"
	const dbName = "whoWasWhen.db"

	cwd, err := os.Getwd()
	if err != nil {
		return fmt.Errorf("cannot determine current directory: %w", err)
	}

	zipPath := filepath.Join(cwd, zipName)
	dbDestPath := filepath.Join(dataFolder, dbName)

	// 2) If the zip file is present, extract it and move the DB to the data folder
	if _, err := os.Stat(zipPath); err == nil {
		// Extract directly into a temporary directory inside cwd
		tempExtractDir := filepath.Join(cwd, "_db_extract_tmp")
		if err := os.MkdirAll(tempExtractDir, 0o755); err != nil {
			return fmt.Errorf("error preparing temp dir: %w", err)
		}

		if err := unzipFile(zipPath, tempExtractDir); err != nil {
			return fmt.Errorf("error unzipping database: %w", err)
		}

		// Debug: log what files were extracted
		filepath.Walk(tempExtractDir, func(path string, info os.FileInfo, err error) error {
			if err == nil && !info.IsDir() {
				logMsg("Extracted file: %s", path)
			}
			return nil
		})

		// Locate the .db file inside the extracted directory (could be nested)
		var extractedDBPath string
		err = filepath.Walk(tempExtractDir, func(path string, info os.FileInfo, err error) error {
			if err != nil {
				return err
			}
			if !info.IsDir() && strings.EqualFold(info.Name(), dbName) {
				extractedDBPath = path
				logMsg("Found database file at: %s", path)
				return io.EOF // stop walking early
			}
			return nil
		})
		if err != nil && err != io.EOF {
			return fmt.Errorf("error locating extracted db: %w", err)
		}
		if extractedDBPath == "" {
			return fmt.Errorf("unzipped database %s not found in archive", dbName)
		}

		// Copy (not rename) to support cross-filesystem moves
		if err := copyFile(extractedDBPath, dbDestPath); err != nil {
			return fmt.Errorf("error copying database to data folder: %w", err)
		}

		// Clean-up zip and temp directory
		_ = os.Remove(zipPath)
		_ = os.RemoveAll(tempExtractDir)
		return nil
	}

	// 3) If zip is not present, ensure database already exists in data folder
	if _, err := os.Stat(dbDestPath); os.IsNotExist(err) {
		return fmt.Errorf("database missing at %s", dbDestPath)
	}

	return nil
}

// unzipFile extracts the contents of srcZip into destDir.
func unzipFile(srcZip, destDir string) error {
	zr, err := zip.OpenReader(srcZip)
	if err != nil {
		return err
	}
	defer zr.Close()

	for _, f := range zr.File {
		fpath := filepath.Join(destDir, f.Name)

		// Ensure parent directories exist
		if f.FileInfo().IsDir() {
			if err := os.MkdirAll(fpath, f.Mode()); err != nil {
				return err
			}
			continue
		}

		if err := os.MkdirAll(filepath.Dir(fpath), 0o755); err != nil {
			return err
		}

		rc, err := f.Open()
		if err != nil {
			return err
		}
		defer rc.Close()

		outFile, err := os.OpenFile(fpath, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, f.Mode())
		if err != nil {
			return err
		}
		if _, err := io.Copy(outFile, rc); err != nil {
			outFile.Close()
			return err
		}
		outFile.Close()
	}
	return nil
}

// copyFile copies a file from src to dst, replacing dst if it exists.
func copyFile(src, dst string) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()

	if err := os.MkdirAll(filepath.Dir(dst), 0o755); err != nil {
		return err
	}

	out, err := os.OpenFile(dst, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0o644)
	if err != nil {
		return err
	}
	defer out.Close()

	if _, err := io.Copy(out, in); err != nil {
		return err
	}
	return out.Sync()
}

// Helper function to get plural title with fallback
func getTitlePlural(titlePlural sql.NullString, title string) string {
	if titlePlural.Valid && titlePlural.String != "" {
		return titlePlural.String
	}
	return title + "s"
}

// Helper function to format year with BC/AD
func formatYear(year int) string {
	if year < 0 {
		return fmt.Sprintf("%d BC", -year)
	}
	return fmt.Sprintf("%d", year)
}

// Helper function to get title ranking (lower number = higher priority)
func getTitleRank(title string) int {
	titleLower := strings.ToLower(title)

	// Highest priority - Emperors
	if strings.Contains(titleLower, "roman emperor") {
		return 1
	}
	if strings.Contains(titleLower, "byzantine emperor") {
		return 2
	}
	if strings.Contains(titleLower, "holy roman emperor") {
		return 3
	}

	// High priority - Major rulers
	if strings.Contains(titleLower, "king") || strings.Contains(titleLower, "queen") {
		return 10
	}
	if strings.Contains(titleLower, "emperor") {
		return 15
	}
	if strings.Contains(titleLower, "tsar") || strings.Contains(titleLower, "czar") {
		return 20
	}

	// Medium-high priority - Modern leaders
	if strings.Contains(titleLower, "president") {
		return 30
	}
	if strings.Contains(titleLower, "prime minister") || strings.Contains(titleLower, "premier") {
		return 35
	}
	if strings.Contains(titleLower, "chancellor") {
		return 40
	}

	// Medium priority - Regional/religious rulers
	if strings.Contains(titleLower, "duke") || strings.Contains(titleLower, "duchess") {
		return 50
	}
	if strings.Contains(titleLower, "pope") {
		return 55
	}
	if strings.Contains(titleLower, "patriarch") {
		return 60
	}

	// Lower priority - Administrative/military positions
	if strings.Contains(titleLower, "consul") {
		return 100
	}
	if strings.Contains(titleLower, "tribune") {
		return 110
	}
	if strings.Contains(titleLower, "dictator") {
		return 120
	}

	// Default priority for unknown titles
	return 1000
}

// TitleGroup represents a title with its periods and ranking
type TitleGroup struct {
	Title   string
	Periods []PeriodInfo
	Rank    int
}

// formatSubtitle creates the new formatted subtitle for rulers with multiple periods
func formatSubtitle(periods []PeriodInfo, personalName sql.NullString) string {
	// Group periods by title
	titleGroups := make(map[string][]PeriodInfo)
	for _, period := range periods {
		titleGroups[period.Title] = append(titleGroups[period.Title], period)
	}

	// Create sorted title groups by rank
	var sortedTitleGroups []TitleGroup
	for title, titlePeriods := range titleGroups {
		sortedTitleGroups = append(sortedTitleGroups, TitleGroup{
			Title:   title,
			Periods: titlePeriods,
			Rank:    getTitleRank(title),
		})
	}

	// Sort by rank (lower number = higher priority)
	for i := 0; i < len(sortedTitleGroups); i++ {
		for j := i + 1; j < len(sortedTitleGroups); j++ {
			if sortedTitleGroups[i].Rank > sortedTitleGroups[j].Rank {
				sortedTitleGroups[i], sortedTitleGroups[j] = sortedTitleGroups[j], sortedTitleGroups[i]
			}
		}
	}

	// Format each title group in ranked order
	var titleParts []string
	for _, titleGroup := range sortedTitleGroups {
		var periodParts []string

		for _, period := range titleGroup.Periods {
			var periodStr string
			if period.StartYear == period.EndYear {
				periodStr = formatYear(period.StartYear)
			} else {
				periodStr = fmt.Sprintf("%s-%s", formatYear(period.StartYear), formatYear(period.EndYear))
			}

			// Add notes if present and not empty
			if period.Notes != "" && period.Notes != "," {
				periodStr = fmt.Sprintf("%s, %s", periodStr, period.Notes)
			}

			periodParts = append(periodParts, periodStr)
		}

		titlePart := fmt.Sprintf("%s (%s)", titleGroup.Title, strings.Join(periodParts, "; "))
		titleParts = append(titleParts, titlePart)
	}

	// Combine all title parts
	titlesString := strings.Join(titleParts, "; ")

	// Build final subtitle
	if personalName.Valid && personalName.String != "" {
		return fmt.Sprintf("%s, %s", personalName.String, titlesString)
	} else {
		return titlesString
	}
}

// getHighestRankedTitle returns the title with the highest rank (lowest rank number)
func getHighestRankedTitle(periods []PeriodInfo) string {
	if len(periods) == 0 {
		return ""
	}

	highestTitle := periods[0].Title
	highestRank := getTitleRank(highestTitle)

	for _, period := range periods {
		rank := getTitleRank(period.Title)
		if rank < highestRank {
			highestRank = rank
			highestTitle = period.Title
		}
	}

	return highestTitle
}

func main() {
	startTime := time.Now()

	// Get configuration
	config := getConfig()

	// Validate database presence / perform extraction if needed
	if err := ensureDatabase(filepath.Dir(config.DBPath)); err != nil {
		// Log detailed error to stderr for Alfred debugger
		logMsg("Database initialization error: %v", err)

		// Emit Alfred-compatible JSON error and exit (stdout)
		errorResult := AlfredResult{Items: []AlfredItem{{
			Title:    "⚠️ Error, missing database",
			Subtitle: "delete and re-install this workflow, or contact the developer",
			Valid:    false,
			Arg:      "",
			Icon:     map[string]string{"path": "icons/hopeless.png"},
		}}}
		jsonOut, _ := json.Marshal(errorResult)
		fmt.Println(string(jsonOut))
		return
	}

	// Check if we have input argument or a restored query
	var input string
	if len(os.Args) >= 2 {
		input = strings.TrimSpace(strings.ToLower(os.Args[1]))
	}

	// Check for restored query from go back action
	restoredQuery := os.Getenv("restoredQuery")
	if input == "" && restoredQuery != "" {
		input = strings.TrimSpace(strings.ToLower(restoredQuery))
		logMsg("Restored query: %s", input)
	}

	// Connect to SQLite database
	db, err := sql.Open("sqlite3", config.DBPath)
	if err != nil {
		logMsg("Error opening database: %v", err)
		return
	}
	defer db.Close()

	// Set pragmas for better performance
	_, err = db.Exec("PRAGMA case_sensitive_like=OFF")
	if err != nil {
		logMsg("Error setting pragma: %v", err)
		return
	}

	// If mySource == 'ruler' show a list of rulers
	if config.MySource == "ruler" {
		// Get the original query from environment if available
		originalQueryFromEnv := os.Getenv("originalQuery")
		if originalQueryFromEnv != "" {
			byRuler(db, "", "listLineage", config, originalQueryFromEnv)
		} else {
			byRuler(db, "", "listLineage", config, input)
		}
		return
	}

	// Check if we have input for non-ruler modes
	if input == "" {
		logMsg("No search input provided")
		return
	}

	// Split search terms
	searchTerms := strings.Fields(input)

	// Check if any term looks like a number or year range
	criteriaTerms := []string{}
	for _, term := range searchTerms {
		if isNumberLike(term) {
			criteriaTerms = append(criteriaTerms, term)
		}
	}

	containsNumber := len(criteriaTerms) > 0

	if containsNumber {
		// Use the first matched term as the year
		matchedTerm := criteriaTerms[0]

		// Remove the matched term from search terms
		var searchTermsWN []string
		for _, term := range searchTerms {
			if term != matchedTerm {
				searchTermsWN = append(searchTermsWN, term)
			}
		}

		logMsg("Matched Term: %s", matchedTerm)
		logMsg("Remaining terms: %v", searchTermsWN)

		// Search by year
		byYear(db, searchTermsWN, matchedTerm, config, input)
	} else {
		// Search by ruler and events
		if config.ShowEvents {
			// Search both rulers and events, then combine results
			result := AlfredResult{Items: []AlfredItem{}}

			// Get ruler results (without individual counters)
			rulerItems := getRulerResultsWithoutCounters(db, searchTerms, config, input)
			result.Items = append(result.Items, rulerItems...)

			// Get event results (without individual counters)
			eventItems := byEventWithoutCounters(db, searchTerms, config, input)
			result.Items = append(result.Items, eventItems...)

			// Add unified counters across all results
			totalCount := len(result.Items)
			for i := range result.Items {
				if result.Items[i].Subtitle != "" {
					result.Items[i].Subtitle = fmt.Sprintf("%s/%s %s", formatNumber(i+1), formatNumber(totalCount), result.Items[i].Subtitle)
				} else {
					result.Items[i].Subtitle = fmt.Sprintf("%s/%s", formatNumber(i+1), formatNumber(totalCount))
				}
			}

			// If no results found, show "No results" message
			if len(result.Items) == 0 {
				result.Items = append(result.Items, AlfredItem{
					Title:    "No results here 🫤",
					Subtitle: "Try a different query",
					Arg:      "",
					Mods: map[string]AlfredMod{
						"cmd+alt": {
							Valid:    true,
							Arg:      input,
							Subtitle: "Go back to main search",
							Variables: map[string]string{
								"mySource":      "",
								"myRulerID":     "",
								"mytitleProg":   "",
								"myTitle":       "",
								"restoredQuery": input,
							},
						},
					},
					Icon: map[string]string{
						"path": "icons/hopeless.png",
					},
				})
			}

			// Output JSON for Alfred
			jsonOut, err := json.Marshal(result)
			if err != nil {
				logMsg("Error creating JSON output: %v", err)
				return
			}
			fmt.Println(string(jsonOut))
		} else {
			// Search by ruler only
			byRuler(db, searchTerms, "searchRuler", config, input)
		}
	}

	duration := time.Since(startTime)
	logMsg("\nScript duration: %s", formatDuration(duration))
}

// Check if the term is a number, BC year, or a range
func isNumberLike(term string) bool {
	pattern := `^-?\d*\**$|^-?\d*\**--?\d*\**$`
	matched, err := regexp.MatchString(pattern, term)
	if err != nil {
		logMsg("Regexp error: %v", err)
		return false
	}
	if matched {
		logMsg("Matching term: %s", term)
	}
	return matched
}

// Extract start and end years from a range term
func extractRange(term string) (start, end string) {
	pattern := `^(-?\d+)-(-?\d+)$|^-?(\d+)$`
	re := regexp.MustCompile(pattern)
	matches := re.FindStringSubmatch(term)

	logMsg("Extracting range")

	if len(matches) > 0 {
		if matches[1] != "" && matches[2] != "" {
			// Year range
			return matches[1], matches[2]
		} else if matches[3] != "" {
			// Single year
			return matches[3], ""
		}
	}
	return "", ""
}

// PeriodInfo holds information about a single period
type PeriodInfo struct {
	Period     string
	Notes      string
	Title      string
	StartYear  int
	EndYear    int
	ProgrTitle int
}

// Query for rulers by name or properties
func byRuler(db *sql.DB, searchStringList interface{}, queryType string, config Config, originalQuery ...string) {
	var currentProg int // Declare currentProg at function level for listLineage use

	// Get the original query for storing/restoring
	var origQuery string
	if len(originalQuery) > 0 {
		origQuery = originalQuery[0]
	}

	if queryType == "searchRuler" {
		// Convert searchStringList to []string if it's not already
		var terms []string
		switch v := searchStringList.(type) {
		case []string:
			terms = v
		case string:
			terms = []string{v}
		default:
			terms = []string{}
		}

		// Build the SQL conditions for text search
		conditions := []string{}
		for _, s := range terms {
			condition := fmt.Sprintf(`(ru.name LIKE '%%%s%%' OR 
				ru.personal_name LIKE '%%%s%%' OR 
				ru.epithet LIKE '%%%s%%' OR 
				ru.notes LIKE '%%%s%%' OR 
				t.title LIKE '%%%s%%')`, s, s, s, s, s)
			conditions = append(conditions, condition)
		}
		textSQLString := strings.Join(conditions, " AND ")

		// TODO: searchRuler functionality needs to be implemented
		_ = textSQLString

	} else if queryType == "listLineage" {
		// For listLineage, we need to find the correct progression number for the specific title
		// First, get the progression number for the current ruler and title
		myRulerID, _ := strconv.Atoi(config.MyRulerID)

		// Query to get the progression number for this ruler and title
		progQuery := fmt.Sprintf(`
			SELECT per.progrTitle
			FROM byPeriod per
			JOIN titles t ON per.titleID = t.titleID
			WHERE per.rulerID = %d AND t.title = '%s'
			ORDER BY per.progrTitle ASC
			LIMIT 1`, myRulerID, config.MyTitle)

		err := db.QueryRow(progQuery).Scan(&currentProg)
		if err != nil {
			logMsg("Error getting progression number: %v", err)
			return
		}

		minProg := currentProg - 3
		if minProg < 1 {
			minProg = 1
		}

		// Classic lineage logic: get all periods for the title, ordered by progression
		result := AlfredResult{Items: []AlfredItem{}}

		query := fmt.Sprintf(`
			SELECT 
				ru.*,
				per.*,
				t.title AS title,
				t.maxCount as titleCount,
				t.titlePlural as titlePlural
			FROM
				rulers ru
			JOIN 
				byPeriod per ON ru.rulerID = per.rulerID
			JOIN 
				titles t ON per.titleID = t.titleID
			WHERE
				t.title = '%s'
			ORDER BY per.progrTitle ASC
			;`, config.MyTitle)

		rows, err := db.Query(query)
		if err != nil {
			logMsg("Error querying periods: %v", err)
			return
		}
		defer rows.Close()

		// Keep all periods by progression order (don't filter by ruler ID)
		var lineageRows []RulerRow
		for rows.Next() {
			var r RulerRow
			err := rows.Scan(
				&r.RulerID, &r.Name, &r.PersonalName, &r.Epithet, &r.Wikipedia, &r.Notes, &r.Biography,
				&r.PeriodID, &r.RulerID, &r.TitleID, &r.ProgrTitle, &r.Period, &r.StartYear, &r.EndYear, &r.Notes,
				&r.Title, &r.TitleCount, &r.TitlePlural,
			)
			if err != nil {
				logMsg("Error scanning row: %v", err)
				continue
			}
			lineageRows = append(lineageRows, r)
		}

		// Find the index of the current ruler
		myRulerID, _ = strconv.Atoi(config.MyRulerID)
		myProg, _ := strconv.Atoi(config.MyTitleProg)
		currentIdx := -1
		for i, r := range lineageRows {
			if r.RulerID == myRulerID && r.ProgrTitle == myProg {
				currentIdx = i
				break
			}
		}
		if currentIdx == -1 {
			currentIdx = 0 // fallback
		}

		// Display a window of 3 before and 3 after
		startIdx := currentIdx - 3
		if startIdx < 0 {
			startIdx = 0
		}
		// Show all rulers from the current one onward (no upper limit)
		endIdx := len(lineageRows)

		for i := startIdx; i < endIdx; i++ {
			r := lineageRows[i]
			// Mark all occurrences of the same ruler
			rulerStar := ""
			if r.RulerID == myRulerID {
				rulerStar = "🌟"
			}
			myTitle := fmt.Sprintf("%s (%s) %s", r.Name, r.Period, rulerStar)
			// Build subtitle with global counter (ProgrTitle/TitleCount)
			counterPrefix := fmt.Sprintf("%s/%s", formatNumber(r.ProgrTitle), formatNumber(r.TitleCount))
			var subtitleString string
			if r.Biography.Valid && r.Biography.String != "" {
				subtitleString = fmt.Sprintf("%s %s", counterPrefix, r.Biography.String)
			} else {
				var notesPart string
				if r.Notes.Valid && r.Notes.String != "" && r.Notes.String != "," {
					notesPart = r.Notes.String
				}
				if r.PersonalName.Valid && r.PersonalName.String != "" {
					subtitleString = fmt.Sprintf("%s %s, %s %s", counterPrefix, r.PersonalName.String, r.Title, notesPart)
				} else {
					subtitleString = fmt.Sprintf("%s %s %s", counterPrefix, r.Title, notesPart)
				}
			}
			wikilink := r.Name
			if r.Wikipedia.Valid && r.Wikipedia.String != "" {
				wikilink = r.Wikipedia.String
			} else {
				wikilink = fmt.Sprintf("https://en.wikipedia.org/wiki/%s", r.Name)
			}
			endYear := strconv.Itoa(r.EndYear)
			startYear := strconv.Itoa(r.StartYear)
			iconPath := fmt.Sprintf("icons/%s.png", r.Title)
			if _, err := os.Stat(iconPath); os.IsNotExist(err) {
				iconPath = "icons/crown.png"
			}
			item := AlfredItem{
				Title:    myTitle,
				Subtitle: subtitleString,
				Valid:    true,
				Arg:      wikilink,
				Mods: map[string]AlfredMod{
					"cmd": {
						Valid:    true,
						Arg:      endYear,
						Subtitle: fmt.Sprintf("travel to %s", endYear),
						Variables: map[string]string{
							"mySource": "",
						},
					},
					"ctrl": {
						Valid:    true,
						Arg:      startYear,
						Subtitle: fmt.Sprintf("travel to %s", startYear),
						Variables: map[string]string{
							"mySource": "",
						},
					},
					"alt": {
						Valid:    true,
						Arg:      getTitlePlural(r.TitlePlural, r.Title),
						Subtitle: fmt.Sprintf("Show all %s", getTitlePlural(r.TitlePlural, r.Title)),
						Variables: map[string]string{
							"mySource":      "ruler",
							"myRulerID":     strconv.Itoa(r.RulerID),
							"mytitleProg":   strconv.Itoa(r.ProgrTitle),
							"myTitle":       r.Title,
							"originalQuery": origQuery,
						},
					},
					"cmd+alt": {
						Valid:    true,
						Arg:      origQuery,
						Subtitle: "Go back to main search",
						Variables: map[string]string{
							"mySource":      "",
							"myRulerID":     "",
							"mytitleProg":   "",
							"myTitle":       "",
							"restoredQuery": origQuery,
						},
					},
					"shift": {
						Valid:    true,
						Arg:      fmt.Sprintf("%s: %s", myTitle, subtitleString),
						Subtitle: "Copy full info to clipboard",
					},
				},
				Icon: map[string]string{
					"path": iconPath,
				},
			}
			result.Items = append(result.Items, item)
		}

		// Output JSON for Alfred
		jsonOut, err := json.Marshal(result)
		if err != nil {
			logMsg("Error creating JSON output: %v", err)
			return
		}
		fmt.Println(string(jsonOut))
		return
	}
}

// Search rulers by year
func byYear(db *sql.DB, searchTerms []string, yearTerm string, config Config, originalQuery string) {
	var junctionString string
	if len(searchTerms) > 0 {
		junctionString = " AND "
	} else {
		junctionString = ""
	}

	// Process wildcards
	asteriskCount := len(yearTerm) - len(strings.TrimRight(yearTerm, "*"))
	prefix := yearTerm[:len(yearTerm)-asteriskCount]
	wildcards := strings.Repeat("_", asteriskCount)

	var yearSQLString string
	if strings.Count(yearTerm, "-") == 1 && !strings.HasPrefix(yearTerm, "-") {
		// A year range
		logMsg("Year range")
		parts := strings.Split(yearTerm, "-")
		yearSQLString = fmt.Sprintf("(y.year BETWEEN '%s' AND '%s')%s", parts[0], parts[1], junctionString)
	} else if strings.Count(yearTerm, "-") > 1 {
		// A year range including a negative
		start, end := extractRange(yearTerm)
		logMsg("Start: %s, end: %s", start, end)
		yearSQLString = fmt.Sprintf("(y.year BETWEEN '%s' AND '%s')%s", start, end, junctionString)
	} else {
		yearSQLString = fmt.Sprintf("(CAST(y.year as TEXT) LIKE '%s%s')%s", prefix, wildcards, junctionString)
	}

	// Build text search conditions
	textConditions := []string{}
	for _, s := range searchTerms {
		condition := fmt.Sprintf("((r.name LIKE '%%%s%%') OR (t.title LIKE '%%%s%%'))", s, s)
		textConditions = append(textConditions, condition)
	}
	textSQLString := strings.Join(textConditions, " AND ")

	query := fmt.Sprintf(`
		SELECT 
		r.*,
		per.*,
		t.title AS title,
		t.maxCount as titleCount,
		t.titlePlural as titlePlural,
		y.year AS year
		
		FROM
			byYear rt
		JOIN 
			byPeriod per ON rt.periodID = per.periodID
		JOIN 
			rulers r ON per.rulerID = r.rulerID
		JOIN 
			titles t ON per.titleID = t.titleID
		JOIN
			years y ON rt.yearID = y.yearID
		WHERE
			%s
			%s
		GROUP BY
				per.periodID
		ORDER BY 
			y.year
		;`, yearSQLString, textSQLString)

	queryStart := time.Now()
	rows, err := db.Query(query)
	queryDuration := time.Since(queryStart)
	logMsg("Query executed in %s", formatDuration(queryDuration))

	if err != nil {
		logMsg("Error querying database: %v", err)
		return
	}
	defer rows.Close()

	// Collect all results first to get total count
	var allRows []RulerRow
	for rows.Next() {
		var r RulerRow
		err := rows.Scan(
			&r.RulerID, &r.Name, &r.PersonalName, &r.Epithet, &r.Wikipedia, &r.Notes, &r.Biography,
			&r.PeriodID, &r.RulerID, &r.TitleID, &r.ProgrTitle, &r.Period, &r.StartYear, &r.EndYear, &r.Notes,
			&r.Title, &r.TitleCount, &r.TitlePlural, &r.Year,
		)
		if err != nil {
			logMsg("Error scanning row: %v", err)
			continue
		}
		allRows = append(allRows, r)
	}

	totalCount := len(allRows)
	result := AlfredResult{Items: []AlfredItem{}}

	// Process results
	for _, r := range allRows {
		var yearString string
		// Check if the year term contains an asterisk or is a range
		isRange, _ := regexp.MatchString(`-`, yearTerm)
		if asteriskCount > 0 || isRange {
			yearString = yearTerm
		} else {
			yearString = formatYear(int(r.Year.Int64))
		}

		epithetString := ""
		if r.Epithet.Valid && r.Epithet.String != "" {
			epithetString = fmt.Sprintf(" (%s)", r.Epithet.String)
		}

		myTitle := fmt.Sprintf("%s: %s%s (%s)", yearString, r.Name, epithetString, r.Period)

		var subtitleString string
		if r.PersonalName.Valid && r.PersonalName.String != "" {
			subtitleString = fmt.Sprintf("%s, %s (%s/%s) %s", r.PersonalName.String, r.Title, formatNumber(r.ProgrTitle), formatNumber(r.TitleCount), r.Notes.String)
		} else {
			subtitleString = fmt.Sprintf("%s (%s/%s) %s", r.Title, formatNumber(r.ProgrTitle), formatNumber(r.TitleCount), r.Notes.String)
		}

		wikilink := r.Name
		if r.Wikipedia.Valid && r.Wikipedia.String != "" {
			wikilink = r.Wikipedia.String
		} else {
			wikilink = fmt.Sprintf("https://en.wikipedia.org/wiki/%s", r.Name)
		}

		endYear := strconv.Itoa(r.EndYear)
		startYear := strconv.Itoa(r.StartYear)

		// Check if the icon file exists, use default crown if not
		iconPath := fmt.Sprintf("icons/%s.png", r.Title)
		if _, err := os.Stat(iconPath); os.IsNotExist(err) {
			iconPath = "icons/crown.png"
		}

		item := AlfredItem{
			Title:    myTitle,
			Subtitle: subtitleString,
			Valid:    true,
			Arg:      wikilink,
			Mods: map[string]AlfredMod{
				"cmd": {
					Valid:    true,
					Arg:      endYear,
					Subtitle: fmt.Sprintf("travel to %s", endYear),
					Variables: map[string]string{
						config.MySource: "",
					},
				},
				"ctrl": {
					Valid:    true,
					Arg:      startYear,
					Subtitle: fmt.Sprintf("travel to %s", startYear),
					Variables: map[string]string{
						config.MySource: "",
					},
				},
				"alt": {
					Valid:    true,
					Arg:      getTitlePlural(r.TitlePlural, r.Title),
					Subtitle: fmt.Sprintf("Show all %s", getTitlePlural(r.TitlePlural, r.Title)),
					Variables: map[string]string{
						"mySource":      "ruler",
						"myRulerID":     strconv.Itoa(r.RulerID),
						"mytitleProg":   strconv.Itoa(r.ProgrTitle),
						"myTitle":       r.Title,
						"originalQuery": originalQuery,
					},
				},
				"cmd+alt": {
					Valid:    true,
					Arg:      originalQuery,
					Subtitle: "Go back to main search",
					Variables: map[string]string{
						"mySource":      "",
						"myRulerID":     "",
						"mytitleProg":   "",
						"myTitle":       "",
						"restoredQuery": originalQuery,
					},
				},
				"shift": {
					Valid:    true,
					Arg:      fmt.Sprintf("%s: %s", myTitle, subtitleString),
					Subtitle: "Copy full info to clipboard",
				},
			},
			Icon: map[string]string{
				"path": iconPath,
			},
		}

		result.Items = append(result.Items, item)
	}

	// If ShowEvents is enabled, also get events for this year
	if config.ShowEvents {
		eventItems := getEventsByYearWithoutCounters(db, searchTerms, yearTerm, config, originalQuery)
		result.Items = append(result.Items, eventItems...)
	}

	// Add unified counters to all items (rulers + events)
	totalCount = len(result.Items)
	for i := range result.Items {
		if result.Items[i].Subtitle != "" {
			result.Items[i].Subtitle = fmt.Sprintf("%s/%s %s", formatNumber(i+1), formatNumber(totalCount), result.Items[i].Subtitle)
		} else {
			result.Items[i].Subtitle = fmt.Sprintf("%s/%s", formatNumber(i+1), formatNumber(totalCount))
		}
	}

	// If year term exists but no results found
	if yearTerm != "" && len(result.Items) == 0 {
		result.Items = append(result.Items, AlfredItem{
			Title:    "No results here 🫤",
			Subtitle: "Try a different query",
			Arg:      "",
			Mods: map[string]AlfredMod{
				"cmd+alt": {
					Valid:    true,
					Arg:      originalQuery,
					Subtitle: "Go back to main search",
					Variables: map[string]string{
						"mySource":      "",
						"myRulerID":     "",
						"mytitleProg":   "",
						"myTitle":       "",
						"restoredQuery": originalQuery,
					},
				},
			},
			Icon: map[string]string{
				"path": "icons/hopeless.png",
			},
		})
	}

	// Output JSON for Alfred
	jsonOut, err := json.Marshal(result)
	if err != nil {
		logMsg("Error creating JSON output: %v", err)
		return
	}
	fmt.Println(string(jsonOut))
}

// Search events by name
func byEvent(db *sql.DB, searchTerms []string, config Config, originalQuery string) []AlfredItem {
	// Build the SQL conditions for text search
	conditions := []string{}
	for _, s := range searchTerms {
		condition := fmt.Sprintf(`(e.eventName LIKE '%%%s%%' OR e.notes LIKE '%%%s%%')`, s, s)
		conditions = append(conditions, condition)
	}
	textSQLString := strings.Join(conditions, " AND ")

	query := fmt.Sprintf(`
		SELECT 
			e.eventID,
			e.eventName,
			e.startYear,
			e.endYear,
			e.notes,
			e.wikipedia
		FROM
			byEvents e
		WHERE
			%s
		ORDER BY
			e.startYear;`, textSQLString)

	queryStart := time.Now()
	rows, err := db.Query(query)
	queryDuration := time.Since(queryStart)
	logMsg("Event query executed in %s", formatDuration(queryDuration))

	if err != nil {
		logMsg("Error querying events: %v", err)
		return []AlfredItem{}
	}
	defer rows.Close()

	// Collect all events first to get total count
	var allEvents []EventRow
	for rows.Next() {
		var e EventRow
		err := rows.Scan(&e.EventID, &e.EventName, &e.StartYear, &e.EndYear, &e.Notes, &e.Wikipedia)
		if err != nil {
			logMsg("Error scanning event row: %v", err)
			continue
		}
		allEvents = append(allEvents, e)
	}

	totalCount := len(allEvents)
	var eventItems []AlfredItem

	// Process each event with counter
	for i, e := range allEvents {
		// Format the event title and subtitle
		var yearString string
		if e.StartYear == e.EndYear {
			yearString = formatYear(e.StartYear)
		} else {
			yearString = fmt.Sprintf("%s-%s", formatYear(e.StartYear), formatYear(e.EndYear))
		}

		myTitle := fmt.Sprintf("%s: %s", yearString, e.EventName)

		subtitleString := ""
		if e.Notes.Valid && e.Notes.String != "" {
			subtitleString = e.Notes.String
		}

		// Add counter to subtitle
		if subtitleString != "" {
			subtitleString = fmt.Sprintf("%s/%s %s", formatNumber(i+1), formatNumber(totalCount), subtitleString)
		} else {
			subtitleString = fmt.Sprintf("%s/%s", formatNumber(i+1), formatNumber(totalCount))
		}

		// Use the wikipedia link from database if available, otherwise create a basic search URL
		wikilink := e.EventName
		if e.Wikipedia.Valid && e.Wikipedia.String != "" {
			wikilink = e.Wikipedia.String
		} else {
			wikilink = fmt.Sprintf("https://en.wikipedia.org/wiki/%s", e.EventName)
		}

		endYear := strconv.Itoa(e.EndYear)
		startYear := strconv.Itoa(e.StartYear)

		item := AlfredItem{
			Title:    myTitle,
			Subtitle: subtitleString,
			Valid:    true,
			Arg:      wikilink,
			Mods: map[string]AlfredMod{
				"cmd": {
					Valid:    true,
					Arg:      endYear,
					Subtitle: fmt.Sprintf("travel to %s", endYear),
					Variables: map[string]string{
						"mySource": "",
					},
				},
				"ctrl": {
					Valid:    true,
					Arg:      startYear,
					Subtitle: fmt.Sprintf("travel to %s", startYear),
					Variables: map[string]string{
						"mySource": "",
					},
				},
				"cmd+alt": {
					Valid:    true,
					Arg:      originalQuery,
					Subtitle: "Go back to main search",
					Variables: map[string]string{
						"mySource":      "",
						"myRulerID":     "",
						"mytitleProg":   "",
						"myTitle":       "",
						"restoredQuery": originalQuery,
					},
				},
				"shift": {
					Valid:    true,
					Arg:      fmt.Sprintf("%s: %s", myTitle, subtitleString),
					Subtitle: "Copy full info to clipboard",
				},
			},
			Icon: map[string]string{
				"path": "icons/event.png",
			},
		}

		eventItems = append(eventItems, item)
	}

	return eventItems
}

// Helper function to get events by year without counters
func getEventsByYearWithoutCounters(db *sql.DB, searchTerms []string, yearTerm string, config Config, originalQuery string) []AlfredItem {
	var junctionString string
	if len(searchTerms) > 0 {
		junctionString = " AND "
	} else {
		junctionString = ""
	}

	// Process wildcards
	asteriskCount := len(yearTerm) - len(strings.TrimRight(yearTerm, "*"))
	prefix := yearTerm[:len(yearTerm)-asteriskCount]
	wildcards := strings.Repeat("_", asteriskCount)

	var yearSQLString string
	if strings.Count(yearTerm, "-") == 1 && !strings.HasPrefix(yearTerm, "-") {
		// A year range
		parts := strings.Split(yearTerm, "-")
		yearSQLString = fmt.Sprintf("(y.year BETWEEN '%s' AND '%s')%s", parts[0], parts[1], junctionString)
	} else if strings.Count(yearTerm, "-") > 1 {
		// A year range including a negative
		start, end := extractRange(yearTerm)
		yearSQLString = fmt.Sprintf("(y.year BETWEEN '%s' AND '%s')%s", start, end, junctionString)
	} else {
		yearSQLString = fmt.Sprintf("(CAST(y.year as TEXT) LIKE '%s%s')%s", prefix, wildcards, junctionString)
	}

	// Build text search conditions for events
	textConditions := []string{}
	for _, s := range searchTerms {
		condition := fmt.Sprintf("(e.eventName LIKE '%%%s%%' OR e.notes LIKE '%%%s%%')", s, s)
		textConditions = append(textConditions, condition)
	}
	textSQLString := strings.Join(textConditions, " AND ")

	query := fmt.Sprintf(`
		SELECT 
			e.eventID,
			e.eventName,
			e.startYear,
			e.endYear,
			e.notes,
			e.wikipedia,
			y.year AS year
		FROM
			byYear rt
		JOIN 
			byEvents e ON rt.eventID = e.eventID
		JOIN
			years y ON rt.yearID = y.yearID
		WHERE
			%s
			%s
		ORDER BY 
			y.year
		;`, yearSQLString, textSQLString)

	queryStart := time.Now()
	rows, err := db.Query(query)
	queryDuration := time.Since(queryStart)
	logMsg("Event by year query executed in %s", formatDuration(queryDuration))

	if err != nil {
		logMsg("Error querying events by year: %v", err)
		return []AlfredItem{}
	}
	defer rows.Close()

	var eventItems []AlfredItem

	for rows.Next() {
		var e EventRow
		err := rows.Scan(&e.EventID, &e.EventName, &e.StartYear, &e.EndYear, &e.Notes, &e.Wikipedia, &e.Year)
		if err != nil {
			logMsg("Error scanning event row: %v", err)
			continue
		}

		// Format the event title
		var yearString string
		// Check if the year term contains an asterisk or is a range
		isRange, _ := regexp.MatchString(`-`, yearTerm)
		if asteriskCount > 0 || isRange {
			yearString = yearTerm
		} else {
			yearString = formatYear(int(e.Year.Int64))
		}

		// Build period range string only if the event spans multiple years
		var rangeStr string
		if e.StartYear != e.EndYear {
			rangeStr = fmt.Sprintf(" (%s-%s)", formatYear(e.StartYear), formatYear(e.EndYear))
		}
		myTitle := fmt.Sprintf("%s: %s%s", yearString, e.EventName, rangeStr)

		subtitleString := ""
		if e.Notes.Valid && e.Notes.String != "" {
			subtitleString = e.Notes.String
		}

		// No counter added here - it will be added by the caller

		// Use the wikipedia link from database if available, otherwise create a basic search URL
		wikilink := e.EventName
		if e.Wikipedia.Valid && e.Wikipedia.String != "" {
			wikilink = e.Wikipedia.String
		} else {
			wikilink = fmt.Sprintf("https://en.wikipedia.org/wiki/%s", e.EventName)
		}

		endYear := strconv.Itoa(e.EndYear)
		startYear := strconv.Itoa(e.StartYear)

		item := AlfredItem{
			Title:    myTitle,
			Subtitle: subtitleString,
			Valid:    true,
			Arg:      wikilink,
			Mods: map[string]AlfredMod{
				"cmd": {
					Valid:    true,
					Arg:      endYear,
					Subtitle: fmt.Sprintf("travel to %s", endYear),
					Variables: map[string]string{
						"mySource": "",
					},
				},
				"ctrl": {
					Valid:    true,
					Arg:      startYear,
					Subtitle: fmt.Sprintf("travel to %s", startYear),
					Variables: map[string]string{
						"mySource": "",
					},
				},
				"cmd+alt": {
					Valid:    true,
					Arg:      originalQuery,
					Subtitle: "Go back to main search",
					Variables: map[string]string{
						"mySource":      "",
						"myRulerID":     "",
						"mytitleProg":   "",
						"myTitle":       "",
						"restoredQuery": originalQuery,
					},
				},
				"shift": {
					Valid:    true,
					Arg:      fmt.Sprintf("%s: %s", myTitle, subtitleString),
					Subtitle: "Copy full info to clipboard",
				},
			},
			Icon: map[string]string{
				"path": "icons/event.png",
			},
		}

		eventItems = append(eventItems, item)
	}

	return eventItems
}

// Helper function to get ruler results without printing
func getRulerResults(db *sql.DB, searchTerms []string, config Config, originalQuery string) []AlfredItem {
	// Build the SQL conditions for text search
	conditions := []string{}
	for _, s := range searchTerms {
		condition := fmt.Sprintf(`(ru.name LIKE '%%%s%%' OR 
			ru.personal_name LIKE '%%%s%%' OR 
			ru.epithet LIKE '%%%s%%' OR 
			ru.notes LIKE '%%%s%%' OR 
			t.title LIKE '%%%s%%')`, s, s, s, s, s)
		conditions = append(conditions, condition)
	}
	textSQLString := strings.Join(conditions, " AND ")

	query := fmt.Sprintf(`
		SELECT 
			ru.*,
			per.*,
			t.title AS title,
			t.titlePlural as titlePlural
		FROM
			rulers ru
		JOIN 
			byPeriod per ON ru.rulerID = per.rulerID
		JOIN 
			titles t ON per.titleID = t.titleID
		WHERE
			%s
		ORDER BY
			ru.rulerID, per.startYear;`, textSQLString)

	queryStart := time.Now()
	rows, err := db.Query(query)
	queryDuration := time.Since(queryStart)
	logMsg("Ruler query executed in %s", formatDuration(queryDuration))

	if err != nil {
		logMsg("Error querying database: %v", err)
		return []AlfredItem{}
	}
	defer rows.Close()

	// Group periods by ruler
	rulerPeriods := make(map[int][]PeriodInfo)
	rulerData := make(map[int]RulerRow)

	for rows.Next() {
		var r RulerRow
		err := rows.Scan(
			&r.RulerID, &r.Name, &r.PersonalName, &r.Epithet, &r.Wikipedia, &r.Notes, &r.Biography,
			&r.PeriodID, &r.RulerID, &r.TitleID, &r.ProgrTitle, &r.Period, &r.StartYear, &r.EndYear, &r.Notes,
			&r.Title, &r.TitlePlural,
		)
		if err != nil {
			logMsg("Error scanning row: %v", err)
			continue
		}

		// Store ruler data
		rulerData[r.RulerID] = r

		// Collect period info
		period := PeriodInfo{
			Period:     r.Period,
			Notes:      "",
			Title:      r.Title,
			StartYear:  r.StartYear,
			EndYear:    r.EndYear,
			ProgrTitle: r.ProgrTitle,
		}
		if r.Notes.Valid {
			period.Notes = r.Notes.String
		}

		rulerPeriods[r.RulerID] = append(rulerPeriods[r.RulerID], period)
	}

	var rulerItems []AlfredItem

	// Process each ruler
	for rulerID, periods := range rulerPeriods {
		r := rulerData[rulerID]

		// Calculate display strings
		epithetString := ""
		if r.Epithet.Valid && r.Epithet.String != "" {
			epithetString = fmt.Sprintf(" (%s)", r.Epithet.String)
		}

		myTitle := fmt.Sprintf("%s%s", r.Name, epithetString)

		// Use biography if available, otherwise format subtitle from periods
		var subtitleString string
		if r.Biography.Valid && r.Biography.String != "" {
			subtitleString = r.Biography.String
		} else {
			subtitleString = formatSubtitle(periods, r.PersonalName)
		}

		wikilink := r.Name
		if r.Wikipedia.Valid && r.Wikipedia.String != "" {
			wikilink = r.Wikipedia.String
		} else {
			wikilink = fmt.Sprintf("https://en.wikipedia.org/wiki/%s", r.Name)
		}

		// Determine the earliest start year and latest end year across all periods
		earliestStart := periods[0].StartYear
		latestEnd := periods[0].EndYear
		for _, p := range periods {
			if p.StartYear < earliestStart {
				earliestStart = p.StartYear
			}
			if p.EndYear > latestEnd {
				latestEnd = p.EndYear
			}
		}
		firstPeriod := periods[0]
		startYear := strconv.Itoa(earliestStart)
		endYear := strconv.Itoa(latestEnd)
		// Use the highest-ranked title for the icon
		highestRankedTitle := getHighestRankedTitle(periods)
		iconPath := fmt.Sprintf("icons/%s.png", highestRankedTitle)
		if _, err := os.Stat(iconPath); os.IsNotExist(err) {
			iconPath = "icons/crown.png"
		}

		item := AlfredItem{
			Title:    myTitle,
			Subtitle: subtitleString,
			Valid:    true,
			Arg:      wikilink,
			Mods: map[string]AlfredMod{
				"cmd": {
					Valid:    true,
					Arg:      endYear,
					Subtitle: fmt.Sprintf("travel to %s", endYear),
					Variables: map[string]string{
						"mySource": "",
					},
				},
				"ctrl": {
					Valid:    true,
					Arg:      startYear,
					Subtitle: fmt.Sprintf("travel to %s", startYear),
					Variables: map[string]string{
						"mySource": "",
					},
				},
				"alt": {
					Valid:    true,
					Arg:      getTitlePlural(r.TitlePlural, r.Title),
					Subtitle: fmt.Sprintf("Show all %s", getTitlePlural(r.TitlePlural, r.Title)),
					Variables: map[string]string{
						"mySource":      "ruler",
						"myRulerID":     strconv.Itoa(r.RulerID),
						"mytitleProg":   strconv.Itoa(firstPeriod.ProgrTitle),
						"myTitle":       highestRankedTitle,
						"originalQuery": originalQuery,
					},
				},
				"cmd+alt": {
					Valid:    true,
					Arg:      originalQuery,
					Subtitle: "Go back to main search",
					Variables: map[string]string{
						"mySource":      "",
						"myRulerID":     "",
						"mytitleProg":   "",
						"myTitle":       "",
						"restoredQuery": originalQuery,
					},
				},
				"shift": {
					Valid:    true,
					Arg:      fmt.Sprintf("%s: %s", myTitle, subtitleString),
					Subtitle: "Copy full info to clipboard",
				},
			},
			Icon: map[string]string{
				"path": iconPath,
			},
		}

		rulerItems = append(rulerItems, item)
	}

	// Add counters to all ruler items
	totalCount := len(rulerItems)
	for i := range rulerItems {
		if rulerItems[i].Subtitle != "" {
			rulerItems[i].Subtitle = fmt.Sprintf("%s/%s %s", formatNumber(i+1), formatNumber(totalCount), rulerItems[i].Subtitle)
		} else {
			rulerItems[i].Subtitle = fmt.Sprintf("%s/%s", formatNumber(i+1), formatNumber(totalCount))
		}
	}

	return rulerItems
}

// Helper function to get ruler results without counters
func getRulerResultsWithoutCounters(db *sql.DB, searchTerms []string, config Config, originalQuery string) []AlfredItem {
	// Build the SQL conditions for text search
	conditions := []string{}
	for _, s := range searchTerms {
		condition := fmt.Sprintf(`(ru.name LIKE '%%%s%%' OR 
			ru.personal_name LIKE '%%%s%%' OR 
			ru.epithet LIKE '%%%s%%' OR 
			ru.notes LIKE '%%%s%%' OR 
			t.title LIKE '%%%s%%')`, s, s, s, s, s)
		conditions = append(conditions, condition)
	}
	textSQLString := strings.Join(conditions, " AND ")

	query := fmt.Sprintf(`
		SELECT 
			ru.*,
			per.*,
			t.title AS title,
			t.titlePlural as titlePlural
		FROM
			rulers ru
		JOIN 
			byPeriod per ON ru.rulerID = per.rulerID
		JOIN 
			titles t ON per.titleID = t.titleID
		WHERE
			%s
		ORDER BY
			ru.rulerID, per.startYear;`, textSQLString)

	queryStart := time.Now()
	rows, err := db.Query(query)
	queryDuration := time.Since(queryStart)
	logMsg("Ruler query executed in %s", formatDuration(queryDuration))

	if err != nil {
		logMsg("Error querying database: %v", err)
		return []AlfredItem{}
	}
	defer rows.Close()

	// Group periods by ruler
	rulerPeriods := make(map[int][]PeriodInfo)
	rulerData := make(map[int]RulerRow)
	// Collect all biographies for each ruler
	rulerBios := make(map[int]string)

	for rows.Next() {
		var r RulerRow
		err := rows.Scan(
			&r.RulerID, &r.Name, &r.PersonalName, &r.Epithet, &r.Wikipedia, &r.Notes, &r.Biography,
			&r.PeriodID, &r.RulerID, &r.TitleID, &r.ProgrTitle, &r.Period, &r.StartYear, &r.EndYear, &r.Notes,
			&r.Title, &r.TitlePlural,
		)
		if err != nil {
			logMsg("Error scanning row: %v", err)
			continue
		}

		// Store ruler data
		rulerData[r.RulerID] = r

		// Collect period info
		period := PeriodInfo{
			Period:     r.Period,
			Notes:      "",
			Title:      r.Title,
			StartYear:  r.StartYear,
			EndYear:    r.EndYear,
			ProgrTitle: r.ProgrTitle,
		}
		if r.Notes.Valid {
			period.Notes = r.Notes.String
		}
		rulerPeriods[r.RulerID] = append(rulerPeriods[r.RulerID], period)

		// Collect the longest biography
		if r.Biography.Valid && r.Biography.String != "" {
			if len(r.Biography.String) > len(rulerBios[r.RulerID]) {
				rulerBios[r.RulerID] = r.Biography.String
			}
		}
	}

	var rulerItems []AlfredItem

	// Process each ruler
	for rulerID, periods := range rulerPeriods {
		r := rulerData[rulerID]

		// Calculate display strings
		epithetString := ""
		if r.Epithet.Valid && r.Epithet.String != "" {
			epithetString = fmt.Sprintf(" (%s)", r.Epithet.String)
		}

		myTitle := fmt.Sprintf("%s%s", r.Name, epithetString)

		// Use biography if available, otherwise format subtitle from periods
		var subtitleString string
		if r.Biography.Valid && r.Biography.String != "" {
			subtitleString = r.Biography.String
		} else {
			subtitleString = formatSubtitle(periods, r.PersonalName)
		}

		wikilink := r.Name
		if r.Wikipedia.Valid && r.Wikipedia.String != "" {
			wikilink = r.Wikipedia.String
		} else {
			wikilink = fmt.Sprintf("https://en.wikipedia.org/wiki/%s", r.Name)
		}

		// Determine the earliest start year and latest end year across all periods
		earliestStart := periods[0].StartYear
		latestEnd := periods[0].EndYear
		for _, p := range periods {
			if p.StartYear < earliestStart {
				earliestStart = p.StartYear
			}
			if p.EndYear > latestEnd {
				latestEnd = p.EndYear
			}
		}
		firstPeriod := periods[0]
		startYear := strconv.Itoa(earliestStart)
		endYear := strconv.Itoa(latestEnd)
		// Use the highest-ranked title for the icon
		highestRankedTitle := getHighestRankedTitle(periods)
		iconPath := fmt.Sprintf("icons/%s.png", highestRankedTitle)
		if _, err := os.Stat(iconPath); os.IsNotExist(err) {
			iconPath = "icons/crown.png"
		}

		// Get the correct TitlePlural for the highest-ranked title
		pluralQuery := fmt.Sprintf(`
			SELECT titlePlural
			FROM titles
			WHERE title = '%s'
			LIMIT 1`, highestRankedTitle)

		var correctTitlePlural sql.NullString
		err = db.QueryRow(pluralQuery).Scan(&correctTitlePlural)
		if err != nil {
			logMsg("Error getting title plural: %v", err)
			return []AlfredItem{}
		}

		item := AlfredItem{
			Title:    myTitle,
			Subtitle: subtitleString,
			Valid:    true,
			Arg:      wikilink,
			Mods: map[string]AlfredMod{
				"cmd": {
					Valid:    true,
					Arg:      endYear,
					Subtitle: fmt.Sprintf("travel to %s", endYear),
					Variables: map[string]string{
						"mySource": "",
					},
				},
				"ctrl": {
					Valid:    true,
					Arg:      startYear,
					Subtitle: fmt.Sprintf("travel to %s", startYear),
					Variables: map[string]string{
						"mySource": "",
					},
				},
				"alt": {
					Valid:    true,
					Arg:      getTitlePlural(correctTitlePlural, highestRankedTitle),
					Subtitle: fmt.Sprintf("Show all %s", getTitlePlural(correctTitlePlural, highestRankedTitle)),
					Variables: map[string]string{
						"mySource":      "ruler",
						"myRulerID":     strconv.Itoa(r.RulerID),
						"mytitleProg":   strconv.Itoa(firstPeriod.ProgrTitle),
						"myTitle":       highestRankedTitle,
						"originalQuery": originalQuery,
					},
				},
				"cmd+alt": {
					Valid:    true,
					Arg:      originalQuery,
					Subtitle: "Go back to main search",
					Variables: map[string]string{
						"mySource":      "",
						"myRulerID":     "",
						"mytitleProg":   "",
						"myTitle":       "",
						"restoredQuery": originalQuery,
					},
				},
				"shift": {
					Valid:    true,
					Arg:      fmt.Sprintf("%s: %s", myTitle, subtitleString),
					Subtitle: "Copy full info to clipboard",
				},
			},
			Icon: map[string]string{
				"path": iconPath,
			},
		}

		rulerItems = append(rulerItems, item)
	}

	// No counters added here - they will be added by the caller
	return rulerItems
}

// Helper function to get event results without counters
func byEventWithoutCounters(db *sql.DB, searchTerms []string, config Config, originalQuery string) []AlfredItem {
	// Build the SQL conditions for text search
	conditions := []string{}
	for _, s := range searchTerms {
		condition := fmt.Sprintf(`(e.eventName LIKE '%%%s%%' OR e.notes LIKE '%%%s%%')`, s, s)
		conditions = append(conditions, condition)
	}
	textSQLString := strings.Join(conditions, " AND ")

	query := fmt.Sprintf(`
		SELECT 
			e.eventID,
			e.eventName,
			e.startYear,
			e.endYear,
			e.notes,
			e.wikipedia
		FROM
			byEvents e
		WHERE
			%s
		ORDER BY
			e.startYear;`, textSQLString)

	queryStart := time.Now()
	rows, err := db.Query(query)
	queryDuration := time.Since(queryStart)
	logMsg("Event query executed in %s", formatDuration(queryDuration))

	if err != nil {
		logMsg("Error querying events: %v", err)
		return []AlfredItem{}
	}
	defer rows.Close()

	var eventItems []AlfredItem

	for rows.Next() {
		var e EventRow
		err := rows.Scan(&e.EventID, &e.EventName, &e.StartYear, &e.EndYear, &e.Notes, &e.Wikipedia)
		if err != nil {
			logMsg("Error scanning event row: %v", err)
			continue
		}

		// Format the event title and subtitle
		var yearString string
		if e.StartYear == e.EndYear {
			yearString = formatYear(e.StartYear)
		} else {
			yearString = fmt.Sprintf("%s-%s", formatYear(e.StartYear), formatYear(e.EndYear))
		}

		myTitle := fmt.Sprintf("%s: %s", yearString, e.EventName)

		subtitleString := ""
		if e.Notes.Valid && e.Notes.String != "" {
			subtitleString = e.Notes.String
		}

		// No counter added here - it will be added by the caller

		// Use the wikipedia link from database if available, otherwise create a basic search URL
		wikilink := e.EventName
		if e.Wikipedia.Valid && e.Wikipedia.String != "" {
			wikilink = e.Wikipedia.String
		} else {
			wikilink = fmt.Sprintf("https://en.wikipedia.org/wiki/%s", e.EventName)
		}

		endYear := strconv.Itoa(e.EndYear)
		startYear := strconv.Itoa(e.StartYear)

		item := AlfredItem{
			Title:    myTitle,
			Subtitle: subtitleString,
			Valid:    true,
			Arg:      wikilink,
			Mods: map[string]AlfredMod{
				"cmd": {
					Valid:    true,
					Arg:      endYear,
					Subtitle: fmt.Sprintf("travel to %s", endYear),
					Variables: map[string]string{
						"mySource": "",
					},
				},
				"ctrl": {
					Valid:    true,
					Arg:      startYear,
					Subtitle: fmt.Sprintf("travel to %s", startYear),
					Variables: map[string]string{
						"mySource": "",
					},
				},
				"cmd+alt": {
					Valid:    true,
					Arg:      originalQuery,
					Subtitle: "Go back to main search",
					Variables: map[string]string{
						"mySource":      "",
						"myRulerID":     "",
						"mytitleProg":   "",
						"myTitle":       "",
						"restoredQuery": originalQuery,
					},
				},
				"shift": {
					Valid:    true,
					Arg:      fmt.Sprintf("%s: %s", myTitle, subtitleString),
					Subtitle: "Copy full info to clipboard",
				},
			},
			Icon: map[string]string{
				"path": "icons/event.png",
			},
		}

		eventItems = append(eventItems, item)
	}

	return eventItems
}

// Helper function to get events by year
func getEventsByYear(db *sql.DB, searchTerms []string, yearTerm string, config Config, originalQuery string) []AlfredItem {
	var junctionString string
	if len(searchTerms) > 0 {
		junctionString = " AND "
	} else {
		junctionString = ""
	}

	// Process wildcards
	asteriskCount := len(yearTerm) - len(strings.TrimRight(yearTerm, "*"))
	prefix := yearTerm[:len(yearTerm)-asteriskCount]
	wildcards := strings.Repeat("_", asteriskCount)

	var yearSQLString string
	if strings.Count(yearTerm, "-") == 1 && !strings.HasPrefix(yearTerm, "-") {
		// A year range
		parts := strings.Split(yearTerm, "-")
		yearSQLString = fmt.Sprintf("(y.year BETWEEN '%s' AND '%s')%s", parts[0], parts[1], junctionString)
	} else if strings.Count(yearTerm, "-") > 1 {
		// A year range including a negative
		start, end := extractRange(yearTerm)
		yearSQLString = fmt.Sprintf("(y.year BETWEEN '%s' AND '%s')%s", start, end, junctionString)
	} else {
		yearSQLString = fmt.Sprintf("(CAST(y.year as TEXT) LIKE '%s%s')%s", prefix, wildcards, junctionString)
	}

	// Build text search conditions for events
	textConditions := []string{}
	for _, s := range searchTerms {
		condition := fmt.Sprintf("(e.eventName LIKE '%%%s%%' OR e.notes LIKE '%%%s%%')", s, s)
		textConditions = append(textConditions, condition)
	}
	textSQLString := strings.Join(textConditions, " AND ")

	query := fmt.Sprintf(`
		SELECT 
			e.eventID,
			e.eventName,
			e.startYear,
			e.endYear,
			e.notes,
			e.wikipedia,
			y.year AS year
		FROM
			byYear rt
		JOIN 
			byEvents e ON rt.eventID = e.eventID
		JOIN
			years y ON rt.yearID = y.yearID
		WHERE
			%s
			%s
		ORDER BY 
			y.year
		;`, yearSQLString, textSQLString)

	queryStart := time.Now()
	rows, err := db.Query(query)
	queryDuration := time.Since(queryStart)
	logMsg("Event by year query executed in %s", formatDuration(queryDuration))

	if err != nil {
		logMsg("Error querying events by year: %v", err)
		return []AlfredItem{}
	}
	defer rows.Close()

	// Collect all events first to get total count
	var allEvents []EventRow
	for rows.Next() {
		var e EventRow
		err := rows.Scan(&e.EventID, &e.EventName, &e.StartYear, &e.EndYear, &e.Notes, &e.Wikipedia, &e.Year)
		if err != nil {
			logMsg("Error scanning event row: %v", err)
			continue
		}
		allEvents = append(allEvents, e)
	}

	totalCount := len(allEvents)
	var eventItems []AlfredItem

	// Process each event with counter
	for i, e := range allEvents {
		// Format the event title
		var yearString string
		// Check if the year term contains an asterisk or is a range
		isRange, _ := regexp.MatchString(`-`, yearTerm)
		if asteriskCount > 0 || isRange {
			yearString = yearTerm
		} else {
			yearString = formatYear(int(e.Year.Int64))
		}

		// Build period range string only if the event spans multiple years
		var rangeStr string
		if e.StartYear != e.EndYear {
			rangeStr = fmt.Sprintf(" (%s-%s)", formatYear(e.StartYear), formatYear(e.EndYear))
		}
		myTitle := fmt.Sprintf("%s: %s%s", yearString, e.EventName, rangeStr)

		subtitleString := ""
		if e.Notes.Valid && e.Notes.String != "" {
			subtitleString = e.Notes.String
		}

		// Add counter to subtitle
		if subtitleString != "" {
			subtitleString = fmt.Sprintf("%s/%s %s", formatNumber(i+1), formatNumber(totalCount), subtitleString)
		} else {
			subtitleString = fmt.Sprintf("%s/%s", formatNumber(i+1), formatNumber(totalCount))
		}

		// Use the wikipedia link from database if available, otherwise create a basic search URL
		wikilink := e.EventName
		if e.Wikipedia.Valid && e.Wikipedia.String != "" {
			wikilink = e.Wikipedia.String
		} else {
			wikilink = fmt.Sprintf("https://en.wikipedia.org/wiki/%s", e.EventName)
		}

		endYear := strconv.Itoa(e.EndYear)
		startYear := strconv.Itoa(e.StartYear)

		item := AlfredItem{
			Title:    myTitle,
			Subtitle: subtitleString,
			Valid:    true,
			Arg:      wikilink,
			Mods: map[string]AlfredMod{
				"cmd": {
					Valid:    true,
					Arg:      endYear,
					Subtitle: fmt.Sprintf("travel to %s", endYear),
					Variables: map[string]string{
						"mySource": "",
					},
				},
				"ctrl": {
					Valid:    true,
					Arg:      startYear,
					Subtitle: fmt.Sprintf("travel to %s", startYear),
					Variables: map[string]string{
						"mySource": "",
					},
				},
				"cmd+alt": {
					Valid:    true,
					Arg:      originalQuery,
					Subtitle: "Go back to main search",
					Variables: map[string]string{
						"mySource":      "",
						"myRulerID":     "",
						"mytitleProg":   "",
						"myTitle":       "",
						"restoredQuery": originalQuery,
					},
				},
				"shift": {
					Valid:    true,
					Arg:      fmt.Sprintf("%s: %s", myTitle, subtitleString),
					Subtitle: "Copy full info to clipboard",
				},
			},
			Icon: map[string]string{
				"path": "icons/event.png",
			},
		}

		eventItems = append(eventItems, item)
	}

	return eventItems
}
