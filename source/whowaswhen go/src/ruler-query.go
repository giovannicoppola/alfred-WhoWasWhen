package main

import (
	"database/sql"
	"encoding/json"
	"fmt"
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
	return Config{
		MySource:    os.Getenv("mySource"),
		MyRulerID:   os.Getenv("myRulerID"),
		MyTitle:     os.Getenv("myTitle"),
		MyTitleProg: os.Getenv("mytitleProg"),
		DBPath:      filepath.Join(dataFolder, "whoWasWho.db"),
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

// Helper function to get plural title with fallback
func getTitlePlural(titlePlural sql.NullString, title string) string {
	if titlePlural.Valid && titlePlural.String != "" {
		return titlePlural.String
	}
	return title + "s"
}

func main() {
	startTime := time.Now()

	// Get configuration
	config := getConfig()

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
		// Search by ruler
		byRuler(db, searchTerms, "searchRuler", config, input)
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

// Query for rulers by name or properties
func byRuler(db *sql.DB, searchStringList interface{}, queryType string, config Config, originalQuery ...string) {
	var query string

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

		query = fmt.Sprintf(`
			SELECT 
				ru.*,
				per.*,
				t.title AS title,
				t.titlePlural as titlePlural,
				GROUP_CONCAT(t.title || ' (' || per.period || ')', '; ') AS concatenated_titles,
				GROUP_CONCAT(per.notes) AS concatenated_notes
			FROM
				rulers ru
			JOIN 
				byPeriod per ON ru.rulerID = per.rulerID
			JOIN 
				titles t ON per.titleID = t.titleID
			WHERE
				%s
			GROUP BY
				ru.rulerID;`, textSQLString)

	} else if queryType == "listLineage" {
		myTitleProg, _ := strconv.Atoi(config.MyTitleProg)
		minProg := myTitleProg - 3
		if minProg < 1 {
			minProg = 1
		}

		query = fmt.Sprintf(`
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
				t.title = '%s' AND per.progrTitle > %d
			;`, config.MyTitle, minProg)
	}

	queryStart := time.Now()
	rows, err := db.Query(query)
	queryDuration := time.Since(queryStart)
	logMsg("Query executed in %s", formatDuration(queryDuration))

	if err != nil {
		logMsg("Error querying database: %v", err)
		return
	}
	defer rows.Close()

	result := AlfredResult{Items: []AlfredItem{}}

	for rows.Next() {
		var r RulerRow
		var err error

		if queryType == "searchRuler" {
			err = rows.Scan(
				&r.RulerID, &r.Name, &r.PersonalName, &r.Epithet, &r.Wikipedia, &r.Notes,
				&r.PeriodID, &r.RulerID, &r.TitleID, &r.ProgrTitle, &r.Period, &r.StartYear, &r.EndYear, &r.Notes,
				&r.Title, &r.TitlePlural, &r.ConcatenatedTitles, &r.ConcatenatedNotes,
			)
		} else {
			err = rows.Scan(
				&r.RulerID, &r.Name, &r.PersonalName, &r.Epithet, &r.Wikipedia, &r.Notes,
				&r.PeriodID, &r.RulerID, &r.TitleID, &r.ProgrTitle, &r.Period, &r.StartYear, &r.EndYear, &r.Notes,
				&r.Title, &r.TitleCount, &r.TitlePlural,
			)
		}

		if err != nil {
			logMsg("Error scanning row: %v", err)
			continue
		}

		// Calculate display strings
		rulerStar := ""
		myRulerID, _ := strconv.Atoi(config.MyRulerID)
		if r.RulerID == myRulerID {
			rulerStar = "🌟"
		}

		epithetString := ""
		if r.Epithet.Valid && r.Epithet.String != "" {
			epithetString = fmt.Sprintf(" (%s)", r.Epithet.String)
		}

		var myTitle, subtitleString string
		if queryType == "searchRuler" {
			notesString := ""
			if r.ConcatenatedNotes.Valid && r.ConcatenatedNotes.String != "" {
				notesString = fmt.Sprintf(" – %s", r.ConcatenatedNotes.String)
			}
			myTitle = fmt.Sprintf("%s%s", r.Name, epithetString)

			if r.PersonalName.Valid && r.PersonalName.String != "" {
				subtitleString = fmt.Sprintf("%s, %s%s", r.PersonalName.String, r.ConcatenatedTitles.String, notesString)
			} else {
				subtitleString = fmt.Sprintf("%s%s", r.ConcatenatedTitles.String, notesString)
			}
		} else {
			myTitle = fmt.Sprintf("%s (%s) %s", r.Name, r.Period, rulerStar)

			if r.PersonalName.Valid && r.PersonalName.String != "" {
				subtitleString = fmt.Sprintf("(%d/%d) %s, %s (%s) – %s", r.ProgrTitle, r.TitleCount, r.PersonalName.String, r.Title, r.Period, r.Notes.String)
			} else {
				subtitleString = fmt.Sprintf("(%d/%d) %s – %s", r.ProgrTitle, r.TitleCount, r.Title, r.Notes.String)
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
					Arg:      "{ruler['period']}",
					Subtitle: "Copy {ruler['period']} to clipboard",
				},
			},
			Icon: map[string]string{
				"path": iconPath,
			},
		}

		result.Items = append(result.Items, item)
	}

	// If we have search terms but no results, show "No results" message
	// Check if searchStringList is actually a []string before type assertion
	var hasSearchTerms bool
	if searchStringList != nil {
		switch v := searchStringList.(type) {
		case []string:
			hasSearchTerms = len(v) > 0
		case string:
			hasSearchTerms = v != ""
		default:
			hasSearchTerms = false
		}
	}

	if hasSearchTerms && len(result.Items) == 0 {
		result.Items = append(result.Items, AlfredItem{
			Title:    "No results here 🫤",
			Subtitle: "Try a different query",
			Arg:      "",
			Mods: map[string]AlfredMod{
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
			&r.RulerID, &r.Name, &r.PersonalName, &r.Epithet, &r.Wikipedia, &r.Notes,
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
	for i, r := range allRows {
		var yearString string
		// Check if the year term contains an asterisk or is a range
		isRange, _ := regexp.MatchString(`-`, yearTerm)
		if asteriskCount > 0 || isRange {
			yearString = yearTerm
		} else {
			yearString = strconv.FormatInt(r.Year.Int64, 10)
		}

		epithetString := ""
		if r.Epithet.Valid && r.Epithet.String != "" {
			epithetString = fmt.Sprintf(" (%s)", r.Epithet.String)
		}

		myTitle := fmt.Sprintf("%s: %s%s (%s)", yearString, r.Name, epithetString, r.Period)

		var subtitleString string
		if r.PersonalName.Valid && r.PersonalName.String != "" {
			subtitleString = fmt.Sprintf("%d/%d %s, %s (%d/%d) %s", i+1, totalCount, r.PersonalName.String, r.Title, r.ProgrTitle, r.TitleCount, r.Notes.String)
		} else {
			subtitleString = fmt.Sprintf("%d/%d %s (%d/%d) %s", i+1, totalCount, r.Title, r.ProgrTitle, r.TitleCount, r.Notes.String)
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
					Arg:      "{ruler['period']}",
					Subtitle: "Copy {ruler['period']} to clipboard",
				},
			},
			Icon: map[string]string{
				"path": iconPath,
			},
		}

		result.Items = append(result.Items, item)
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
